
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
from typing import List, Dict

import praw
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

# -------------------- 1. Credentials & clients ------------------------------
load_dotenv()  # pulls REDDIT_* and OPENAI_* from .env if present

# Try to get credentials from Streamlit secrets first, then environment variables
try:
    import streamlit as st
    reddit = praw.Reddit(
        client_id=st.secrets.get("REDDIT_CLIENT_ID") or os.getenv("REDDIT_CLIENT_ID"),
        client_secret=st.secrets.get("REDDIT_CLIENT_SECRET") or os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=st.secrets.get("REDDIT_USER_AGENT") or os.getenv("REDDIT_USER_AGENT", "reddit-scraper/0.3"),
    )
    client = OpenAI(
        api_key=st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY"),
        organization=st.secrets.get("OPENAI_ORG") or os.getenv("OPENAI_ORG") or None,
    )
except:
    # Fallback to environment variables only
    reddit = praw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        user_agent=os.getenv("REDDIT_USER_AGENT", "reddit-scraper/0.3"),
    )
    client = OpenAI(
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
• MVP should be buildable in ≈2 weeks.

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
You are pair‑programming inside **Cursor**.

Create an ordered list of prompts the developer can paste into Cursor, one by
one, to build the MVP below.  Each prompt can build off of the previous one.

### Required sequence
0. **Context prompt** – Explain the problem, target market, and the chosen MVP
   in ≤ 120 words. Finish with:  
   > “Respond ‘Ready’ if you understand and will wait for detailed tasks.”

1. **Project bootstrap**  
   * Git repo init, README stub, MIT license  
   * Basic tooling: lint / format / .env.example

2. **Data model & schema** – full schema with migrations (e.g. Prisma, Alembic,
   or Mongoose).

3. **Core backend logic & endpoints** – implement the 1‑3 MVP features with
   unit‑test stubs.

4. **Minimal UI or CLI** – only what’s needed to demo the features locally.

5. **Automated tests** – unit + one happy‑path integration test.

6. **Local run instructions** – how to start the dev server, seed sample data,
   and test the flow.

Return **JSON only** with one key `prompts` whose value is the array of prompt
strings.
"""


# -------------------- 3. Helper: OpenAI → JSON ------------------------------
def oai_json(prompt: str, *, max_tokens: int = 25000) -> dict:
    """Call Chat Completions and force‑parse JSON."""
    try:
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
    for submission in reddit.subreddit(name).new(limit=batch_size):
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
    subs: List[str], post_lim: int, cmnt_lim: int, delay: float = 1.2
) -> (List[dict], list):
    results = []
    report = []

    # Load already seen IDs from scraper.db if it exists
    seen_ids = set()
    db_path = Path("scraper.db")
    if db_path.exists():
        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT post_id FROM scraped_posts")
        seen_ids = {row[0] for row in cur.fetchall()}
        conn.close()

    for sub in subs:
        print(f"\n### r/{sub}")
        # Fetch enough posts to get post_lim new ones
        posts = scrape_subreddit(sub, post_lim, cmnt_lim, already_seen_ids=seen_ids)
        for post in posts:
            seen_ids.add(post["id"])
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
    return results, report

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
