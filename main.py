
# Set up Reddit API credentials






"""
standalone_reddit_scraper.py   •   v2.3
Scrape Reddit → filter for real problems → generate
• tight, domain‑specific MVPs (1‑3 features, no generic CRUD apps)
• Cursor playbooks to build them.

CLI usage ───────────────────────────────────────────────
python standalone_reddit_scraper.py \
    --subreddits consulting startups \
    --posts-per-subreddit 4 \
    --comments-per-post 15 \
    --output results.jsonl
"""
# -------------------- 0. Std‑lib & third‑party imports -----------------------
import argparse
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import praw
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

# -------------------- 1. Credentials & clients ------------------------------
load_dotenv()  # pulls REDDIT_* and OPENAI_* from .env if present

def get_reddit_client():
    """Get Reddit client with credentials from Streamlit secrets or environment variables"""
    try:
        import streamlit as st
        return praw.Reddit(
            client_id=st.secrets.get("REDDIT_CLIENT_ID") or os.getenv("REDDIT_CLIENT_ID"),
            client_secret=st.secrets.get("REDDIT_CLIENT_SECRET") or os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent=st.secrets.get("REDDIT_USER_AGENT") or os.getenv("REDDIT_USER_AGENT", "reddit-scraper/0.3"),
        )
    except:
        # Fallback to environment variables only
        return praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent=os.getenv("REDDIT_USER_AGENT", "reddit-scraper/0.3"),
        )

def get_openai_client():
    """Get OpenAI client with credentials from Streamlit secrets or environment variables"""
    try:
        import streamlit as st
        return OpenAI(
            api_key=st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY"),
            organization=st.secrets.get("OPENAI_ORG") or os.getenv("OPENAI_ORG") or None,
        )
    except:
        # Fallback to environment variables only
        return OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            organization=os.getenv("OPENAI_ORG") or None,
        )

MODEL = "o4-mini"
TEMPERATURE = 0.45  # a touch more variety

# -------------------- 2. Prompt templates -----------------------------------
ANALYSIS_PROMPT = """\
Identify whether the following Reddit discussion surfaces either:
- a *viable* **software problem** (a pain point that could be solved with software),
- or a **business opportunity** (an approach, product, or service that is working, being paid for, or could be replicated).

Consider a post viable if it describes a problem, a need, a workaround, a paid solution, or a business opportunity—even if the problem is not fully described or if the market is niche. Be generous in your assessment.

Return JSON:
- is_viable: boolean
- is_opportunity: boolean  # true if a business opportunity is present
- problem_description      # or opportunity description
- target_market
- confidence_score (0‑1)

TEXT
----
{content}
"""

SOLUTION_PROMPT = """\
You are a senior software architect and business analyst.

**Constraints**
• If the post describes a problem, propose a software solution (as before).
• If the post describes a business opportunity, propose how to replicate or address that opportunity with a new product, service, or SaaS.
• Provide 1–3 features *specific* to the problem, need, or opportunity & target market.
• Explicitly **DO NOT** propose a generic CRUD task manager / kanban / to‑do app.  
• MVP should be buildable in ≈a few days using AI coding tools like Cursor's agent mode.

Problem or Opportunity
----------------------
{problem}

Target market
-------------
{market}

Context excerpt (for specificity)
---------------------------------
{context}

Return JSON:
- solution_description
- tech_stack              (array)
- mvp_features            (array, max 3)
- est_development_time
"""

CURSOR_PLAYBOOK_PROMPT = """\
You are pair-programming inside **Cursor**.

Goal: Produce a paste-ready playbook for Cursor. For each step (0–6) below, output the EXACT text the developer should paste into Cursor. Do not include labels like "Step 1:" or meta-instructions like "write a summary". No headings, explanations, or numbering—only the final prompt strings.

Hard requirements:
- Return JSON only in the shape: {{"prompts": ["...", "...", "..."]}}
- Provide exactly 7 prompts (indices 0..6 correspond to the steps below)
- Each prompt must be a complete instruction the developer can paste as-is (except prompt 0, which must be a summary)
- Each prompt should not include code, but instructions for Cursor to write the code

### Required sequence
0. Context prompt – Summarize the problem, target market, and proposed solution in one unlabeled paragraph (≤120 words); use only the inputs provided; no headings, bullets, or code; end with exactly: "Respond 'Ready' if you understand and will wait for detailed tasks."
1) Project bootstrap – Initialize repo and minimal stack; give shell commands and expected files; keep stack tiny (Python 3.11 + FastAPI + SQLite OR Node 20 + Express + SQLite); include run commands.
2) Data model & schema – Only if persistence is truly required; otherwise state that no DB is needed. If needed, use a single-file SQLite DB or a single JSON file with one table/collection and a tiny seed.
3) Core backend logic & endpoints – Implement exactly the 1–3 MVP features; provide clear validation and error handling; include curl examples with expected responses; include unit-test stubs.
4) Minimal UI or CLI – Provide only what’s required to demo locally (one server-rendered HTML page with a simple form OR a single CLI). No CSS frameworks or auth.
5) Automated tests – One unit test per feature plus one happy-path integration test; include the command to run tests and the expected passing output line.
6) Local run instructions – How to start, (optionally) seed data, and validate the flow; include copy-paste commands and a short Acceptance Checklist (3–5 bullets); no cloud dependencies.

Example format (do not reuse content; illustration of structure only):
{{"prompts": [
  "<final text for step 0 ending with Respond 'Ready'...>",
  "<final text for step 1...>",
  "<final text for step 2...>",
  "<final text for step 3...>",
  "<final text for step 4...>",
  "<final text for step 5...>",
  "<final text for step 6...>"
]}}

### Problem Context
{problem}

### Target Market
{market}

### Solution Description
{solution}

Return JSON only with the key `prompts` as specified above.
"""


#CURSOR_PLAYBOOK_PROMPT = """\
#You are pair‑programming inside **Cursor**.

#Create an ordered list of prompts the developer can paste into Cursor, one by
#one, to build the MVP below.  Each prompt can build off of the previous one.

### Required sequence
#0. **Context prompt** – Explain the problem, target market, and the chosen MVP
#   in ≤ 120 words. Finish with:  
#   > "Respond 'Ready' if you understand and will wait for detailed tasks."
#
#1. **Project bootstrap**  
#   * Git repo init, README stub, MIT license  
#   * Basic tooling: lint / format / .env.example
#
#2. **Data model & schema** – full schema with migrations (e.g. Prisma, Alembic,
 #  or Mongoose).
#
#3. **Core backend logic & endpoints** – implement the 1‑3 MVP features with
 #  unit‑test stubs.

#4. **Minimal UI or CLI** – only what's needed to demo the features locally.
#
#5. **Automated tests** – unit + one happy‑path integration test.

#6. **Local run instructions** – how to start the dev server, seed sample data,
#   and test the flow.

### Problem Context
# {problem}

### Target Market
#{market}

### Solution Description
#{solution}

#Return **JSON only** with one key `prompts` whose value is the array of prompt
#strings.
#"""


# -------------------- 3. Helper: OpenAI → JSON ------------------------------
def oai_json(prompt: str, *, max_tokens: int = 25000) -> dict:
    """Call Chat Completions and force‑parse JSON."""
    try:
        client = get_openai_client()
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "Return JSON only."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=max_tokens,
        )
        print(resp)
        content = resp.choices[0].message.content
        if not content:
            print("[OpenAI] Empty response received. Full response:", resp)
            return {}
        return json.loads(content)
    except (OpenAIError, json.JSONDecodeError) as e:
        print(f"[OpenAI] {e}")
        return {}

# -------------------- 4. Reddit scraping ------------------------------------
def build_context(post, max_comments=10):
    context = f"Title: {post['title']}\n\nBody: {post['body']}\n\n"
    comments = post["comments"][:max_comments]
    if comments:
        context += "Top Comments:\n" + "\n".join(comments)
    return context

def scrape_subreddit(name: str, post_limit: int, max_comments: int, already_seen_ids=None) -> List[Dict]:
    # Fetch a large batch to ensure we can find enough new posts
    batch_size = max(50, post_limit * 3)
    items = []
    seen = set(already_seen_ids or [])
    reddit_client = get_reddit_client()
    for submission in reddit_client.subreddit(name).top(time_filter="week", limit=batch_size):
        if submission.id in seen:
            continue
        submission.comments.replace_more(limit=0)
        items.append(
            {
                "id": submission.id,
                "subreddit": name,
                "url": f"https://reddit.com{submission.permalink}",
                "title": submission.title,
                "body": submission.selftext or "",
                "comments": [c.body for c in submission.comments.list()[:max_comments]],
            }
        )
        if len(items) >= post_limit:
            break
    return items

# -------------------- 5. Main pipeline --------------------------------------
def run_pipeline(
    subs: List[str],
    post_lim: int,
    cmnt_lim: int,
    delay: float = 1.2,
    skip_reddit_ids: Optional[List[str]] = None,
) -> Tuple[List[dict], list]:
    results = []
    report = []

    # Load already seen IDs from scraper.db if it exists.
    # Merge with per-user skip_reddit_ids from the web app (do not overwrite).
    seen_ids = set(skip_reddit_ids or [])
    db_path = Path("scraper.db")
    if db_path.exists():
        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        try:
            cur.execute("SELECT post_id FROM scraped_posts")
            fetched_ids = {row[0] for row in cur.fetchall()}
            seen_ids = seen_ids.union(fetched_ids)
        except Exception:
            # table may not exist yet; keep existing seen_ids
            pass
        conn.close()

    # Prepare a writer connection to persist newly processed post IDs
    write_conn = None
    write_cur = None
    try:
        import sqlite3 as _sqlite3
        write_conn = _sqlite3.connect(db_path)
        write_cur = write_conn.cursor()
        write_cur.execute(
            "CREATE TABLE IF NOT EXISTS scraped_posts (post_id TEXT PRIMARY KEY, created_at TEXT)"
        )
    except Exception:
        write_conn = None
        write_cur = None

    for sub in subs:
        print(f"\n### r/{sub}")
        # Fetch enough posts to get post_lim new ones
        posts = scrape_subreddit(sub, post_lim, cmnt_lim, already_seen_ids=seen_ids)
        for post in posts:
            seen_ids.add(post["id"])
            # Persist this post id to avoid reprocessing in future runs
            try:
                if write_cur is not None:
                    write_cur.execute(
                        "INSERT OR IGNORE INTO scraped_posts (post_id, created_at) VALUES (?, ?)",
                        (post["id"], datetime.utcnow().isoformat()),
                    )
            except Exception:
                pass
            # Build structured context with more content
            full_text = build_context(post, max_comments=10)
            if len(full_text) > 400000:
                full_text = full_text[:400000]

            post_report = {
                "title": post["title"],
                "url": post["url"],
                "status": "",
                "details": ""
            }

            # 1. Viability analysis
            analysis = oai_json(ANALYSIS_PROMPT.format(content=full_text))
            if not analysis:
                msg = f"OpenAI error (analysis step)"
                print(f"   ✗ {msg}: {post['title'][:70]}")
                post_report["status"] = "Error"
                post_report["details"] = msg
                report.append(post_report)
                time.sleep(delay)
                continue
            if not analysis.get("is_viable"):
                msg = "Not viable"
                print(f"   ✗ {msg}: {post['title'][:70]}")
                post_report["status"] = "Not viable"
                post_report["details"] = analysis.get("problem_description", "")
                report.append(post_report)
                time.sleep(delay)
                continue

            # 2. MVP solution (use market + structured context)
            problem_desc = analysis.get("problem_description", "")
            if not problem_desc:
                # Fallback: use opportunity_description if available
                problem_desc = analysis.get("opportunity_description", "")
            if not problem_desc:
                # Final fallback: use a generic description
                problem_desc = "A viable business opportunity identified from Reddit discussion"
                
            sol = oai_json(
                SOLUTION_PROMPT.format(
                    problem=problem_desc,
                    market=analysis.get("target_market", ""),
                    context=full_text,
                )
            )
            if not sol:
                msg = f"OpenAI error (solution step)"
                print(f"   ✗ {msg}: {post['title'][:70]}")
                post_report["status"] = "Error"
                post_report["details"] = msg
                report.append(post_report)
                time.sleep(delay)
                continue

            # 3. Cursor playbook
            playbook = oai_json(
                CURSOR_PLAYBOOK_PROMPT.format(
                    problem=problem_desc,
                    market=analysis.get("target_market", ""),
                    solution=sol.get("solution_description", ""),
                )
            )
            if not playbook:
                msg = f"OpenAI error (playbook step)"
                print(f"   ✗ {msg}: {post['title'][:70]}")
                post_report["status"] = "Error"
                post_report["details"] = msg
                report.append(post_report)
                time.sleep(delay)
                continue

            results.append(
                {
                    "meta": {
                        "uuid": str(uuid.uuid4()),
                        "scraped_at": datetime.utcnow().isoformat(),
                    },
                    "reddit": {
                        "subreddit": sub,
                        "url": post["url"],
                        "title": post["title"],
                        "id": post["id"],
                    },
                    "analysis": analysis,
                    "solution": sol,
                    "cursor_playbook": playbook.get("prompts", []),
                }
            )
            post_report["status"] = "Added"
            post_report["details"] = analysis.get("problem_description", "")
            print(f"   ✓ Added: {post['title'][:70]}")
            report.append(post_report)
            time.sleep(delay)
    try:
        if write_conn is not None:
            write_conn.commit()
            write_conn.close()
    except Exception:
        pass
    return results, report

# -------------------- 5b. Manual idea pipeline -------------------------------
def run_manual_idea_pipeline(idea_text: str) -> Tuple[List[dict], list]:
    """Generate analysis, solution, and Cursor playbook from a manually provided idea.

    Returns (results, report) with the same shape as run_pipeline so the web app can
    persist and render without any special-casing.
    """
    idea = (idea_text or "").strip()
    if not idea:
        return [], [{"title": "Manual idea", "url": None, "status": "Error", "details": "Empty idea"}]

    # Derive a compact title from the first sentence/line
    try:
        first_line = idea.splitlines()[0].strip()
    except Exception:
        first_line = idea[:120]
    title = (first_line[:120] or "Manual Idea").rstrip()

    report = {"title": title, "url": None, "status": "", "details": ""}

    # Treat the provided text as the full context
    full_text = idea if len(idea) <= 400000 else idea[:400000]

    # 1) Viability analysis – for manual entries, we still run analysis for structure,
    # but we do not reject non-viable; we proceed to generate solution/playbook anyway.
    analysis = oai_json(ANALYSIS_PROMPT.format(content=full_text)) or {}

    # 2) MVP solution – prefer problem/opportunity description when available
    problem_desc = (
        analysis.get("problem_description")
        or analysis.get("opportunity_description")
        or title
    )
    sol = oai_json(
        SOLUTION_PROMPT.format(
            problem=problem_desc,
            market=analysis.get("target_market", ""),
            context=full_text,
        )
    ) or {}

    # 3) Cursor playbook
    playbook = oai_json(
        CURSOR_PLAYBOOK_PROMPT.format(
            problem=problem_desc,
            market=analysis.get("target_market", ""),
            solution=sol.get("solution_description", ""),
        )
    ) or {}

    result = {
        "meta": {
            "uuid": str(uuid.uuid4()),
            "scraped_at": datetime.utcnow().isoformat(),
        },
        "reddit": {
            "subreddit": "manual",
            "url": None,
            "title": title,
            "id": None,
        },
        "analysis": analysis,
        "solution": sol,
        "cursor_playbook": playbook.get("prompts", []),
    }
    report["status"] = "Added"
    report["details"] = problem_desc
    return [result], [report]

# -------------------- 6. CLI entrypoint -------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-s", "--subreddits", nargs="+", default=["consulting"])
    ap.add_argument("-p", "--posts-per-subreddit", type=int, default=3)
    ap.add_argument("-c", "--comments-per-post", type=int, default=10)
    ap.add_argument("-o", "--output", default="results.jsonl")
    cfg = ap.parse_args()

    rows, report = run_pipeline(
        cfg.subreddits, cfg.posts_per_subreddit, cfg.comments_per_post
    )
    if not rows:
        print("\nNo viable opportunities found.")
        return

    out_path = Path(cfg.output).expanduser()
    with out_path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nSaved {len(rows)} entries → {out_path}")

if __name__ == "__main__":
    main()
