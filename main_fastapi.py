from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
import uvicorn
from typing import List, Optional
import json
from datetime import date, datetime, timedelta
import os
import secrets
from dotenv import load_dotenv
from starlette.concurrency import run_in_threadpool
from urllib.parse import quote_plus

# Load environment variables from .env file
load_dotenv()

# Debug: Check if environment variables are loaded
print("🔍 Environment Debug:")
print(f"RESEND_API_KEY set: {'✅ Yes' if os.getenv('RESEND_API_KEY') else '❌ No'}")
print(f"RESEND_API_KEY value: {os.getenv('RESEND_API_KEY', 'Not set')[:10] if os.getenv('RESEND_API_KEY') else 'Not set'}...")
print(f"Current working directory: {os.getcwd()}")
print(f".env file exists: {'✅ Yes' if os.path.exists('.env') else '❌ No'}")

# Debug: Check .env file contents
if os.path.exists('.env'):
    print("🔍 .env file contents:")
    try:
        with open('.env', 'r') as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    if 'RESEND_API_KEY' in line:
                        print(f"  Found RESEND_API_KEY line: {line[:20]}...")
                    else:
                        print(f"  Other line: {line[:50]}...")
    except Exception as e:
        print(f"  Error reading .env file: {e}")

# Try loading .env with explicit path
print("🔍 Trying explicit .env loading...")
load_dotenv('.env', override=True)
print(f"After explicit load - RESEND_API_KEY: {'✅ Set' if os.getenv('RESEND_API_KEY') else '❌ Still not set'}")

# Import the existing pipeline and auth systems
from main import run_pipeline, get_reddit_client

# Email verification functions are now imported from fastapi_email_verification.py

# Import standalone FastAPI email verification functions
from fastapi_email_verification import (
    create_verification_record,
    verify_token,
    is_email_verified,
    update_last_login,
    send_verification_email_fastapi
)

from db_helpers import (
    save_scraped_result_new, 
    get_all_scraped_results_new, 
    save_to_session_state, 
    get_session_results, 
    mark_post_scraped_new, 
    is_post_already_scraped_new
)
from fastapi_db_helpers import get_daily_usage_safe, increment_daily_usage_safe, increment_daily_usage_by_safe

app = FastAPI(title="LaunchCtrl", version="1.0.0")

# Note: This FastAPI app runs on port 8000
# The Streamlit version runs on port 8501

# Mount static files (ensure directory exists in environments where empty dirs aren't tracked)
try:
    if not os.path.isdir("static"):
        os.makedirs("static", exist_ok=True)
    if os.path.isdir("static"):
        app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    # Non-fatal: templates currently inline styles; continue without /static
    pass

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Human-friendly date formatting for templates
def pretty_date(value: Optional[str]) -> str:
    try:
        if not value:
            return ""
        from datetime import datetime
        s = str(value)
        # Normalize common ISO formats
        s = s.replace('Z', '+00:00')
        try:
            dt = datetime.fromisoformat(s)
        except Exception:
            # Last resort: keep raw string
            return str(value)
        hour_12 = (dt.hour % 12) or 12
        am_pm = 'am' if dt.hour < 12 else 'pm'
        month_abbr = dt.strftime('%b')
        return f"{hour_12}:{dt.minute:02d}{am_pm} on {dt.day}-{month_abbr}-{dt.year}"
    except Exception:
        return str(value)

templates.env.filters["pretty_date"] = pretty_date

# Quota management
FREE_LIMIT = 2
VERIFIED_LIMIT = 15

# Session management
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
SESSION_COOKIE_NAME = "user_session"
SESSION_EXPIRY_DAYS = 30

# Simple local storage for ideas dashboard
RESULTS_FILE = "results.jsonl"
SELECTION_FILE = "selected_ideas.json"
SAVED_FILE = "saved_ideas.json"
FEEDBACK_FILE = "feedback.jsonl"

# Supabase client for feedback (separate from quota helpers; falls back if unset)
try:
    from supabase import create_client as _create_client_fb  # type: ignore
    _SB_URL_FB = os.getenv("SUPABASE_URL")
    _SB_KEY_FB = os.getenv("SUPABASE_ANON_KEY")
    sb_feedback = _create_client_fb(_SB_URL_FB, _SB_KEY_FB) if _SB_URL_FB and _SB_KEY_FB else None
except Exception:
    sb_feedback = None

def create_session_token(email: str) -> str:
    """Create a secure session token"""
    import jwt
    payload = {
        "email": email,
        "exp": datetime.utcnow() + timedelta(days=SESSION_EXPIRY_DAYS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_session_token(token: str) -> Optional[str]:
    """Verify and extract email from session token"""
    import jwt
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("email")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def get_user_email_from_request(request: Request) -> Optional[str]:
    """Get user email from session token in cookies"""
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if session_token:
        return verify_session_token(session_token)
    return None

def _selection_key(email: Optional[str]) -> str:
    return email or "anonymous"

def get_selected_idea_uuid(email: Optional[str]) -> Optional[str]:
    try:
        if not os.path.exists(SELECTION_FILE):
            return None
        with open(SELECTION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(_selection_key(email))
    except Exception:
        return None

def set_selected_idea_uuid(email: Optional[str], idea_uuid: str) -> None:
    try:
        data = {}
        if os.path.exists(SELECTION_FILE):
            with open(SELECTION_FILE, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f) or {}
                except Exception:
                    data = {}
        data[_selection_key(email)] = idea_uuid
        with open(SELECTION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _saved_key(email: Optional[str]) -> str:
    return email or "anonymous"

def _load_saved_map() -> dict:
    if not os.path.exists(SAVED_FILE):
        return {}
    try:
        with open(SAVED_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _write_saved_map(data: dict) -> None:
    try:
        with open(SAVED_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def is_saved(email: Optional[str], idea_uuid: Optional[str]) -> bool:
    if not idea_uuid:
        return False
    data = _load_saved_map()
    saved_list = data.get(_saved_key(email)) or []
    return idea_uuid in saved_list

def set_saved(email: Optional[str], idea_uuid: str, saved: bool) -> bool:
    try:
        data = _load_saved_map()
        key = _saved_key(email)
        saved_list = data.get(key) or []
        if saved and idea_uuid not in saved_list:
            saved_list.append(idea_uuid)
        if not saved and idea_uuid in saved_list:
            saved_list = [u for u in saved_list if u != idea_uuid]
        data[key] = saved_list
        _write_saved_map(data)
        return True
    except Exception:
        return False

def _append_feedback_to_file(obj: dict) -> None:
    try:
        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    except Exception:
        pass

def store_feedback(message: str, *, email: Optional[str], path: Optional[str], user_agent: Optional[str]) -> bool:
    """Store feedback in Supabase if configured; fallback to local JSONL.

    Truncates fields to conservative lengths to avoid abuse.
    """
    try:
        msg = (message or "").strip()
        if not msg:
            return False
        # Basic size limits
        msg = msg[:4000]
        em = (email or "").strip()[:320] if email else None
        p = (path or "").strip()[:512] if path else None
        ua = (user_agent or "").strip()[:512] if user_agent else None

        payload = {
            "message": msg,
            "email": em,
            "path": p,
            "user_agent": ua,
            "created_at": datetime.utcnow().isoformat(),
        }

        if sb_feedback:
            try:
                sb_feedback.table("feedback").insert(payload).execute()
                return True
            except Exception:
                # Fallback to file if DB write fails
                _append_feedback_to_file(payload)
                return True
        else:
            _append_feedback_to_file(payload)
            return True
    except Exception:
        return False

def append_results_to_file(results: List[dict], owner_email: Optional[str]) -> None:
    try:
        with open(RESULTS_FILE, "a", encoding="utf-8") as f:
            for r in results:
                # add owner email for optional filtering later
                if owner_email:
                    r = {**r, "owner_email": owner_email}
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    except Exception:
        pass

def load_recent_ideas(limit: int = 20, owner_email: Optional[str] = None, anonymous_only: bool = False) -> List[dict]:
    """Load recent ideas with optional ownership scoping.

    - If anonymous_only is True: include only rows without owner_email.
    - Else if owner_email is provided: include only rows where owner_email matches.
    - Else: include all rows.
    """
    if not os.path.exists(RESULTS_FILE):
        return []
    rows: List[dict] = []
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    # Apply ownership filtering
                    if anonymous_only:
                        if obj.get("owner_email"):
                            continue
                    elif owner_email is not None:
                        if obj.get("owner_email") != owner_email:
                            continue

                    meta = obj.get("meta", {})
                    reddit = obj.get("reddit", {})
                    analysis = obj.get("analysis", {})
                    solution = obj.get("solution", {})
                    # pick a human-friendly description
                    desc = analysis.get("problem_description") or analysis.get("opportunity_description") or ""
                    prompts_list = obj.get("cursor_playbook", []) or []
                    rows.append({
                        "uuid": meta.get("uuid"),
                        "created_at": meta.get("scraped_at"),
                        "title": reddit.get("title"),
                        "subreddit": reddit.get("subreddit"),
                        "url": reddit.get("url"),
                        "description": desc,
                        "solution_description": solution.get("solution_description", ""),
                        "prompts_count": len(prompts_list),
                    })
                except Exception:
                    continue
        # sort by created_at desc if available
        rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return rows[:limit]
    except Exception:
        return []

def load_filtered_ideas(owner_email: Optional[str] = None, anonymous_only: bool = False) -> List[dict]:
    """Load ideas with ownership scoping, without limiting or ordering.

    Intended for cases where the caller wants to perform custom sampling or ordering.
    """
    if not os.path.exists(RESULTS_FILE):
        return []
    rows: List[dict] = []
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if anonymous_only:
                        if obj.get("owner_email"):
                            continue
                    elif owner_email is not None:
                        if obj.get("owner_email") != owner_email:
                            continue
                    meta = obj.get("meta", {})
                    reddit = obj.get("reddit", {})
                    analysis = obj.get("analysis", {})
                    desc = analysis.get("problem_description") or analysis.get("opportunity_description") or ""
                    rows.append({
                        "uuid": meta.get("uuid"),
                        "created_at": meta.get("scraped_at"),
                        "title": reddit.get("title"),
                        "subreddit": reddit.get("subreddit"),
                        "url": reddit.get("url"),
                        "description": desc,
                    })
                except Exception:
                    continue
        return rows
    except Exception:
        return []

def load_idea_by_uuid(idea_uuid: str) -> Optional[dict]:
    if not idea_uuid or not os.path.exists(RESULTS_FILE):
        return None
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    meta = obj.get("meta", {})
                    if meta.get("uuid") == idea_uuid:
                        return obj
                except Exception:
                    continue
        return None
    except Exception:
        return None

def load_user_ideas(email: str, limit: int = 50) -> List[dict]:
    """Load recent ideas for a specific owner (scoped to authenticated user)."""
    items: List[dict] = []
    if not email or not os.path.exists(RESULTS_FILE):
        return items
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("owner_email") != email:
                    continue
                meta = obj.get("meta", {})
                reddit = obj.get("reddit", {})
                analysis = obj.get("analysis", {})
                solution = obj.get("solution", {})
                items.append({
                    "id": meta.get("uuid"),
                    "title": reddit.get("title"),
                    "subreddit": reddit.get("subreddit"),
                    "problem_text": analysis.get("problem_description") or analysis.get("opportunity_description") or "",
                    "idea_summary": solution.get("solution_description", ""),
                    "mvp_phases": solution.get("mvp_features", []),  # mapped from features
                    "prompts": obj.get("cursor_playbook", []),
                })
        # Return newest first by uuid time proxy (or just reverse read order)
        items = items[-limit:]
        items.reverse()
        return items
    except Exception:
        return []

def get_daily_usage(email: Optional[str]) -> int:
    """Get daily usage count for user"""
    return get_daily_usage_safe(email)

def increment_daily_usage(email: Optional[str]):
    """Increment daily usage count for user"""
    return increment_daily_usage_safe(email)

def can_user_scrape(email: Optional[str]) -> tuple[bool, int, int]:
    """Check if user can scrape and return current usage and limit"""
    if not email:
        # Anonymous user
        current_usage = get_daily_usage(None)
        return current_usage < FREE_LIMIT, current_usage, FREE_LIMIT
    
    # Check if user is verified
    if is_email_verified(email):
        current_usage = get_daily_usage(email)
        return current_usage < VERIFIED_LIMIT, current_usage, VERIFIED_LIMIT
    else:
        # Unverified user gets free limit
        current_usage = get_daily_usage(email)
        return current_usage < FREE_LIMIT, current_usage, FREE_LIMIT

def _check_subreddit_valid(name: str) -> tuple[bool, str]:
    """Return (is_valid, reason). Uses Reddit API; no local list required.

    Skips validation if Reddit credentials are not configured to avoid blocking tests/dev.
    """
    try:
        # Skip if credentials are missing
        if not (os.getenv("REDDIT_CLIENT_ID") and os.getenv("REDDIT_CLIENT_SECRET")):
            return True, ""
        reddit = get_reddit_client()
        sr = reddit.subreddit(name)
        try:
            # Force fetch; raises if not found/invalid/private
            sr._fetch()  # type: ignore[attr-defined]
            return True, ""
        except Exception as e:  # Map common errors to friendly messages
            try:
                from prawcore.exceptions import NotFound, Redirect, Forbidden, BadRequest  # type: ignore
                if isinstance(e, (NotFound, Redirect)):
                    return False, "Subreddit not found. Please check the spelling."
                if isinstance(e, Forbidden):
                    return False, "This subreddit is private or banned. Please choose another."
                if isinstance(e, BadRequest):
                    return False, "Invalid subreddit name. Use letters, numbers, or underscores."
            except Exception:
                pass
            return False, "Unable to validate subreddit. Please try again."
    except Exception:
        # If anything unexpected happens, do not block the user
        return True, ""

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Show the main form for subreddit input with quota status"""
    user_email = get_user_email_from_request(request)
    can_scrape, current_usage, limit = can_user_scrape(user_email)
    
    # Load recent ideas and current selection
    if user_email:
        ideas = load_recent_ideas(limit=50, owner_email=user_email)
    else:
        # Show a small random sample of anonymous ideas to unsigned users
        all_anon = load_filtered_ideas(anonymous_only=True)
        try:
            from random import sample as _sample
            k = 5
            ideas = _sample(all_anon, k) if len(all_anon) > k else all_anon
        except Exception:
            ideas = all_anon[:5]
    # Allow viewing a specific idea via query param
    qp_idea = request.query_params.get("idea")
    selected_uuid = qp_idea or get_selected_idea_uuid(user_email)
    selected_idea = load_idea_by_uuid(selected_uuid) if selected_uuid else None
    # Enforce visibility scope for selected idea
    if selected_idea is not None:
        idea_owner = selected_idea.get("owner_email")
        if user_email:
            if idea_owner != user_email:
                selected_idea = None
                selected_uuid = None
        else:
            if idea_owner:
                selected_idea = None
                selected_uuid = None

    # Optional error propagated via query param (for redirect flows)
    qp_error = request.query_params.get("error")

    return templates.TemplateResponse("index.html", {
        "request": request,
        "user_email": user_email,
        "can_scrape": can_scrape,
        "current_usage": current_usage,
        "limit": limit,
        "is_verified": is_email_verified(user_email) if user_email else False,
        "ideas": ideas,
        "selected_idea_uuid": selected_uuid,
        "selected_idea": selected_idea,
        "error": qp_error
    })

@app.post("/scrape", response_class=HTMLResponse)
async def scrape(
    request: Request,
    subreddit: str = Form(...),
    posts_per_subreddit: int = Form(default=2),
    comments_per_post: int = Form(default=15)
):
    """Run the scraping pipeline and display results with quota check"""
    
    user_email = get_user_email_from_request(request)
    can_scrape, current_usage, limit = can_user_scrape(user_email)
    
    if not can_scrape:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "user_email": user_email,
            "can_scrape": False,
            "current_usage": current_usage,
            "limit": limit,
            "is_verified": is_email_verified(user_email) if user_email else False,
            "error": f"Daily quota exceeded! You've used {current_usage}/{limit} scrapes today. Verify your email to get {VERIFIED_LIMIT} scrapes per day."
        })
    
    # Validate single subreddit input
    name = (subreddit or "").strip()
    if not name or "," in name:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "user_email": user_email,
            "can_scrape": can_scrape,
            "current_usage": current_usage,
            "limit": limit,
            "is_verified": is_email_verified(user_email) if user_email else False,
            "error": "Please enter a single subreddit name (no commas)"
        })
    # Validate subreddit existence without storing lists
    ok_sr, reason = _check_subreddit_valid(name)
    if not ok_sr:
        # Redirect back to home with error and prefilled subreddit
        err = reason or "Subreddit not found. Please try again."
        url = f"/?subreddit={quote_plus(name)}&error={quote_plus(err)}"
        return RedirectResponse(url=url, status_code=302)
    subreddit_list = [name]
    
    try:
        # Run the blocking pipeline off the event loop to avoid worker timeouts
        results, report = await run_in_threadpool(
            run_pipeline,
            subreddit_list,
            posts_per_subreddit,
            comments_per_post,
        )
        # Persist full results locally for the dashboard
        try:
            append_results_to_file(results, user_email)
        except Exception:
            pass
        
        # Increment usage by the number of posts added (avoid counting duplicates or errors)
        posts_processed = 0
        if isinstance(report, list):
            for item in report:
                try:
                    if (item or {}).get("status") == "Added":
                        posts_processed += 1
                except Exception:
                    continue
        try:
            increment_daily_usage_by_safe(user_email, posts_processed)
        except Exception:
            # Fallback to +1 if bulk increment fails
            increment_daily_usage_safe(user_email)
        
        # Prepare results for template
        formatted_results = []
        for result in results:
            formatted_results.append({
                "title": result["reddit"]["title"],
                "url": result["reddit"]["url"],
                "subreddit": result["reddit"]["subreddit"],
                "analysis": result["analysis"],
                "solution": result["solution"],
                "playbook_prompts": result["cursor_playbook"],
                "created_at": (result.get("meta") or {}).get("scraped_at")
            })
        
        return templates.TemplateResponse("results.html", {
            "request": request,
            "results": formatted_results,
            "report": report,
            "subreddits": subreddit_list,
            "posts_per_subreddit": posts_per_subreddit,
            "comments_per_post": comments_per_post,
            "user_email": user_email,
            "current_usage": current_usage + posts_processed,
            "limit": limit
        })
        
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "user_email": user_email,
            "can_scrape": can_scrape,
            "current_usage": current_usage,
            "limit": limit,
            "is_verified": is_email_verified(user_email) if user_email else False,
            "error": f"Error during scraping: {str(e)}"
        })

@app.post("/select")
async def select_idea(request: Request, idea_uuid: str = Form(...)):
    """Select an idea to work on; stored per user in a small JSON file."""
    try:
        user_email = get_user_email_from_request(request)
        if idea_uuid:
            set_selected_idea_uuid(user_email, idea_uuid)
        # Redirect to view the selected idea details immediately
        return RedirectResponse(url=f"/?idea={idea_uuid}", status_code=302)
    except Exception:
        return RedirectResponse(url="/", status_code=302)

@app.get("/ideas", response_class=HTMLResponse)
async def ideas_page(request: Request):
    """Ideas browser: two-column layout with list + detail view."""
    user_email = get_user_email_from_request(request)
    can_scrape, current_usage, limit = can_user_scrape(user_email)

    # Load list and selection
    if user_email:
        ideas = load_recent_ideas(limit=50, owner_email=user_email)
    else:
        ideas = load_recent_ideas(limit=50, anonymous_only=True)
    selected_uuid = request.query_params.get("idea")
    if not selected_uuid and ideas:
        selected_uuid = ideas[0].get("uuid")
    selected_idea = load_idea_by_uuid(selected_uuid) if selected_uuid else None
    # Enforce visibility scope for selected idea
    if selected_idea is not None:
        idea_owner = selected_idea.get("owner_email")
        if user_email:
            if idea_owner != user_email:
                selected_idea = None
                selected_uuid = None
        else:
            if idea_owner:
                selected_idea = None
                selected_uuid = None
    selected_is_saved = is_saved(user_email, selected_uuid) if selected_uuid else False

    return templates.TemplateResponse("ideas.html", {
        "request": request,
        "user_email": user_email,
        "can_scrape": can_scrape,
        "current_usage": current_usage,
        "limit": limit,
        "is_verified": is_email_verified(user_email) if user_email else False,
        "ideas": ideas,
        "selected_idea_uuid": selected_uuid,
        "selected_idea": selected_idea,
        "selected_is_saved": selected_is_saved,
    })

@app.post("/notify", response_class=HTMLResponse)
async def notify_interest(request: Request, email: str = Form(...)):
    """Capture interest for LaunchCtrl updates without leaving the page."""
    user_email = get_user_email_from_request(request)
    can_scrape, current_usage, limit = can_user_scrape(user_email)

    # Store via feedback sink with a special message tag
    try:
        store_feedback("notify_interest", email=email, path=str(request.base_url) + "notify", user_agent=request.headers.get("user-agent"))
        success_msg = "Thanks! We'll notify you about launch updates and early access."
    except Exception:
        success_msg = None

    # Rebuild the same context as index
    if user_email:
        ideas = load_recent_ideas(limit=50, owner_email=user_email)
    else:
        all_anon = load_filtered_ideas(anonymous_only=True)
        try:
            from random import sample as _sample
            k = 5
            ideas = _sample(all_anon, k) if len(all_anon) > k else all_anon
        except Exception:
            ideas = all_anon[:5]

    qp_idea = request.query_params.get("idea")
    selected_uuid = qp_idea or get_selected_idea_uuid(user_email)
    selected_idea = load_idea_by_uuid(selected_uuid) if selected_uuid else None
    if selected_idea is not None:
        idea_owner = selected_idea.get("owner_email")
        if user_email:
            if idea_owner != user_email:
                selected_idea = None
                selected_uuid = None
        else:
            if idea_owner:
                selected_idea = None
                selected_uuid = None

    return templates.TemplateResponse("index.html", {
        "request": request,
        "user_email": user_email,
        "can_scrape": can_scrape,
        "current_usage": current_usage,
        "limit": limit,
        "is_verified": is_email_verified(user_email) if user_email else False,
        "ideas": ideas,
        "selected_idea_uuid": selected_uuid,
        "selected_idea": selected_idea,
        "success": success_msg or None,
    })

@app.get("/feedback", response_class=HTMLResponse)
async def feedback_page(request: Request):
    """Feedback form page."""
    user_email = get_user_email_from_request(request)
    ref = request.query_params.get("from") or str(request.headers.get("referer") or "")
    return templates.TemplateResponse("feedback.html", {
        "request": request,
        "user_email": user_email,
        "from_path": ref,
    })

@app.post("/feedback", response_class=HTMLResponse)
async def feedback_submit(
    request: Request,
    message: str = Form(...),
    email: Optional[str] = Form(default=None),
    from_path: Optional[str] = Form(default=None),
):
    """Accept feedback submissions and store in Supabase or local file."""
    user_email = get_user_email_from_request(request)
    # Prefer signed-in email unless user explicitly entered one
    final_email = email or user_email
    ua = request.headers.get("user-agent")
    ok = store_feedback(message, email=final_email, path=from_path or str(request.base_url), user_agent=ua)
    return templates.TemplateResponse("feedback.html", {
        "request": request,
        "user_email": user_email,
        "from_path": from_path,
        "success": "Thanks for your feedback!" if ok else None,
        "error": None if ok else "Sorry, we couldn't record your feedback. Please try again.",
        "message": message,
        "email_value": final_email or "",
    })

@app.get("/api/ideas", response_class=JSONResponse)
async def api_get_ideas(request: Request):
    """Return the authenticated user's ideas as a simple list.

    Schema: [{ id, title, subreddit, problem_text, idea_summary, mvp_phases, prompts }]
    """
    user_email = get_user_email_from_request(request)
    if not user_email:
        raise HTTPException(status_code=401, detail="Unauthorized")
    data = load_user_ideas(user_email, limit=50)
    return JSONResponse(content=data)

@app.patch("/api/ideas/{idea_id}/status", response_class=JSONResponse)
async def api_toggle_idea_status(idea_id: str, request: Request):
    """Toggle or set saved status for an idea belonging to the authenticated user.

    Body (optional): { "status": "saved" | "new" }
    If body omitted, will toggle current status.
    """
    user_email = get_user_email_from_request(request)
    if not user_email:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Ensure idea belongs to user (best-effort check)
    idea = load_idea_by_uuid(idea_id)
    if not idea or idea.get("owner_email") != user_email:
        # Do not leak existence
        raise HTTPException(status_code=404, detail="Not found")

    # Parse desired status if provided
    desired_status = None
    try:
        payload = await request.json()
        if isinstance(payload, dict):
            s = payload.get("status")
            if s in ("saved", "new"):
                desired_status = s
    except Exception:
        pass

    current = is_saved(user_email, idea_id)
    new_state = (not current) if desired_status is None else (desired_status == "saved")
    ok = set_saved(user_email, idea_id, new_state)
    if not ok:
        raise HTTPException(status_code=500, detail="Unable to update status")

    return {"id": idea_id, "status": "saved" if new_state else "new"}

@app.get("/verify", response_class=HTMLResponse)
async def verify_email_page(request: Request):
    """Show email verification page"""
    return templates.TemplateResponse("verify.html", {"request": request})

@app.post("/verify", response_class=HTMLResponse)
async def verify_email(
    request: Request,
    email: str = Form(...)
):
    """Handle email verification request"""
    try:
        # Create verification record
        token = create_verification_record(email)
        if token:
            # Generate verification URL
            verification_url = f"{request.base_url}verify/confirm?token={token}"
            
            # Try to send verification email
            email_sent = send_verification_email_fastapi(email, token, str(request.base_url))
            
            if email_sent:
                # Determine if we're using the Resend sandbox sender
                from_email = os.getenv("RESEND_FROM_EMAIL", "Acme <onboarding@resend.dev>")
                is_development = "onboarding@resend.dev" in from_email
                
                if is_development:
                    # Sandbox sender may have delivery restrictions; also show manual link as fallback
                    return templates.TemplateResponse("verify.html", {
                        "request": request,
                        "success": f"✅ Verification email attempted to {email}.",
                        "verification_url": verification_url,
                        "email": email,
                        "show_manual_link": True,
                        "email_info": "ℹ️ Using Resend sandbox sender. If the email doesn't arrive, use the link below or configure RESEND_FROM_EMAIL with a verified domain."
                    })
                else:
                    return templates.TemplateResponse("verify.html", {
                        "request": request,
                        "success": f"✅ Verification email sent to {email}! Check your inbox and click the verification link.",
                        "email": email,
                        "show_manual_link": False
                    })
            else:
                # Fallback to manual link if email sending fails
                return templates.TemplateResponse("verify.html", {
                    "request": request,
                    "success": f"✅ Verification record created successfully!",
                    "verification_url": verification_url,
                    "email": email,
                    "show_manual_link": True,
                    "email_error": "Email sending failed, but you can use the manual link below."
                })
        else:
            return templates.TemplateResponse("verify.html", {
                "request": request,
                "error": "Failed to create verification record"
            })
    except Exception as e:
        return templates.TemplateResponse("verify.html", {
            "request": request,
            "error": f"Error: {str(e)}"
        })

@app.get("/verify/confirm", response_class=HTMLResponse)
async def confirm_verification(request: Request, token: str):
    """Confirm email verification"""
    try:
        success, email = verify_token(token)
        if success:
            # Update last login
            update_last_login(email)
            
            # Create session token
            session_token = create_session_token(email)
            
            # Set secure cookie
            response = RedirectResponse(url="/", status_code=302)
            response.set_cookie(
                key=SESSION_COOKIE_NAME,
                value=session_token,
                max_age=86400 * SESSION_EXPIRY_DAYS,  # 30 days
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="lax"
            )
            return response
        else:
            return templates.TemplateResponse("verify.html", {
                "request": request,
                "error": "Invalid or expired verification token"
            })
    except Exception as e:
        return templates.TemplateResponse("verify.html", {
            "request": request,
            "error": f"Error: {str(e)}"
        })

@app.get("/signin", response_class=HTMLResponse)
async def signin_page(request: Request):
    """Show signin page for verified users"""
    return templates.TemplateResponse("signin.html", {"request": request})

@app.post("/signin", response_class=HTMLResponse)
async def signin(
    request: Request,
    email: str = Form(...)
):
    """Handle signin for verified users"""
    try:
        # Check if user is verified
        if is_email_verified(email):
            # Update last login
            update_last_login(email)
            
            # Create session token
            session_token = create_session_token(email)
            
            # Set secure cookie
            response = RedirectResponse(url="/", status_code=302)
            response.set_cookie(
                key=SESSION_COOKIE_NAME,
                value=session_token,
                max_age=86400 * SESSION_EXPIRY_DAYS,  # 30 days
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="lax"
            )
            return response
        else:
            return templates.TemplateResponse("signin.html", {
                "request": request,
                "error": "Email not verified. Please verify your email first.",
                "email": email
            })
    except Exception as e:
        return templates.TemplateResponse("signin.html", {
            "request": request,
            "error": f"Error: {str(e)}"
        })

@app.get("/logout")
async def logout(request: Request):
    """Logout user"""
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return response

@app.get("/debug/email", response_class=JSONResponse)
async def debug_email(request: Request):
    """Diagnostics for email verification configuration and connectivity."""
    def mask(value: str, keep: int = 6) -> str:
        if not value:
            return ""
        return value[:keep] + ("…" if len(value) > keep else "")

    # Environment flags
    resend_api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("RESEND_FROM_EMAIL", "Acme <onboarding@resend.dev>")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")

    # Library availability
    try:
        import resend  # noqa: F401
        resend_installed = True
    except Exception:
        resend_installed = False

    # Supabase connectivity and table checks
    supabase_client_created = False
    pending_table_ok = False
    verified_table_ok = False
    supabase_error = None
    try:
        if supabase_url and supabase_key:
            from supabase import create_client
            sb = create_client(supabase_url, supabase_key)
            supabase_client_created = sb is not None
            if sb:
                try:
                    sb.table("pending_verifications").select("count", count="exact").limit(1).execute()
                    pending_table_ok = True
                except Exception as e:
                    supabase_error = f"pending_verifications: {e}"
                try:
                    sb.table("verified_users").select("count", count="exact").limit(1).execute()
                    verified_table_ok = True
                except Exception as e:
                    supabase_error = (supabase_error or "") + f"; verified_users: {e}"
    except Exception as e:
        supabase_error = str(e)

    # Example verification URL
    base_url = str(request.base_url)
    example_token = "<token>"
    verification_url_example = f"{base_url}verify/confirm?token={example_token}"

    return {
        "resend": {
            "installed": resend_installed,
            "has_api_key": bool(resend_api_key),
            "api_key_prefix": mask(resend_api_key or ""),
            "from_email": from_email,
            "using_sandbox_sender": "onboarding@resend.dev" in from_email,
        },
        "supabase": {
            "has_url": bool(supabase_url),
            "has_anon_key": bool(supabase_key),
            "client_created": supabase_client_created,
            "pending_verifications_table": pending_table_ok,
            "verified_users_table": verified_table_ok,
            "error": supabase_error,
        },
        "app": {
            "base_url": base_url,
            "verification_url_example": verification_url_example,
        },
    }

if __name__ == "__main__":
    print("🚀 Starting FastAPI server...")
    print("📍 Server will be available at: http://localhost:8000")
    print("🌐 Open your browser and navigate to: http://localhost:8000")
    print("⏹️  Press Ctrl+C to stop the server")
    print("-" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8000) 