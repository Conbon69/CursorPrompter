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
from main import run_pipeline

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
from fastapi_db_helpers import get_daily_usage_safe, increment_daily_usage_safe

app = FastAPI(title="Reddit SaaS Idea Finder", version="1.0.0")

# Note: This FastAPI app runs on port 8000
# The Streamlit version runs on port 8501

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory="templates")

# Quota management
FREE_LIMIT = 2
VERIFIED_LIMIT = 15

# Session management
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
SESSION_COOKIE_NAME = "user_session"
SESSION_EXPIRY_DAYS = 30

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

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Show the main form for subreddit input with quota status"""
    user_email = get_user_email_from_request(request)
    can_scrape, current_usage, limit = can_user_scrape(user_email)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user_email": user_email,
        "can_scrape": can_scrape,
        "current_usage": current_usage,
        "limit": limit,
        "is_verified": is_email_verified(user_email) if user_email else False
    })

@app.post("/scrape", response_class=HTMLResponse)
async def scrape(
    request: Request,
    subreddits: str = Form(...),
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
    
    # Parse subreddits (comma-separated)
    subreddit_list = [s.strip() for s in subreddits.split(",") if s.strip()]
    
    if not subreddit_list:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "user_email": user_email,
            "can_scrape": can_scrape,
            "current_usage": current_usage,
            "limit": limit,
            "is_verified": is_email_verified(user_email) if user_email else False,
            "error": "Please enter at least one subreddit"
        })
    
    try:
        # Run the pipeline
        results, report = run_pipeline(
            subs=subreddit_list,
            post_lim=posts_per_subreddit,
            cmnt_lim=comments_per_post
        )
        
        # Increment usage
        increment_daily_usage(user_email)
        
        # Prepare results for template
        formatted_results = []
        for result in results:
            formatted_results.append({
                "title": result["reddit"]["title"],
                "url": result["reddit"]["url"],
                "subreddit": result["reddit"]["subreddit"],
                "analysis": result["analysis"],
                "solution": result["solution"],
                "playbook_prompts": result["cursor_playbook"]
            })
        
        return templates.TemplateResponse("results.html", {
            "request": request,
            "results": formatted_results,
            "report": report,
            "subreddits": subreddit_list,
            "posts_per_subreddit": posts_per_subreddit,
            "comments_per_post": comments_per_post,
            "user_email": user_email,
            "current_usage": current_usage + 1,
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
                # Check if we're in development mode
                is_development = "onboarding@resend.dev" in "Acme <onboarding@resend.dev>"
                
                if is_development:
                    return templates.TemplateResponse("verify.html", {
                        "request": request,
                        "success": f"✅ Verification record created successfully! (Development Mode)",
                        "verification_url": verification_url,
                        "email": email,
                        "show_manual_link": True,
                        "email_info": "🔧 Development mode: Email simulation successful. Use the verification link below."
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

if __name__ == "__main__":
    print("🚀 Starting FastAPI server...")
    print("📍 Server will be available at: http://localhost:8000")
    print("🌐 Open your browser and navigate to: http://localhost:8000")
    print("⏹️  Press Ctrl+C to stop the server")
    print("-" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8000) 