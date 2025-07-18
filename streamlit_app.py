"""
gui_reddit_scraper.py
---------------------
Streamlit front‑end for the standalone_reddit_scraper.py pipeline.
"""

import json
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, date

import pandas as pd
import streamlit as st

# === 1. import the pipeline you wrote earlier ================================
from main import run_pipeline  # same dir
import auth
auth.handle_magic_link()

# === 1.5. Quota management ===================================================
FREE_LIMIT = 2
AUTH_LIMIT = 15
usage_key = f"usage_{date.today()}"
st.session_state.setdefault(usage_key, 0)

def can_scrape():
    is_auth = auth.current_user() is not None
    limit = AUTH_LIMIT if is_auth else FREE_LIMIT
    used = st.session_state[usage_key]
    if used >= limit:
        if not is_auth:
            auth.require_signup()
        else:
            st.warning("Daily limit reached (15). Come back tomorrow!")
        return False
    return True

# === 2. DB helpers ===========================================================
DB_FILE = Path("scraper.db")
OUT_FILE = Path("results.jsonl")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS scraped_posts (
               post_id TEXT PRIMARY KEY,
               scraped_at TEXT
           )"""
    )
    conn.commit()
    return conn

def already_scraped(conn, post_id: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM scraped_posts WHERE post_id=?", (post_id,))
    return cur.fetchone() is not None

def mark_scraped(conn, post_id: str):
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO scraped_posts VALUES (?,?)",
        (post_id, datetime.utcnow().isoformat()),
    )
    conn.commit()

# === 3. Streamlit UI =========================================================
st.set_page_config(page_title="Reddit → SaaS Idea Finder", layout="wide")

st.sidebar.header("Scrape controls")
subs = st.sidebar.text_input(
    "Subreddits (comma‑separated)", value="consulting, smallbusiness"
)
posts_per = st.sidebar.slider("Posts per subreddit", 1, 15, 5)
cmts_per = st.sidebar.slider("Comments per post", 1, 50, 15)
scrape_btn = st.sidebar.button("🚀 Scrape now")

st.sidebar.markdown("---")
url_to_analyze = st.sidebar.text_input("Analyze a Reddit post by URL", value="")
analyze_url_btn = st.sidebar.button("Analyze URL")

st.title("💡 Reddit → SaaS Idea Finder")

# Load existing JSONL (if any) for quick display
if OUT_FILE.exists():
    df = pd.read_json(OUT_FILE, lines=True)
    st.write(f"📊 Total records loaded: {len(df)}")
    # Use map instead of applymap for pandas DataFrame
    st.dataframe(df[["reddit", "analysis", "solution"]].map(str), use_container_width=True)
    st.download_button(
        label="⬇️ Download full JSONL",
        data=OUT_FILE.read_bytes(),
        file_name="results.jsonl",
        mime="application/json",
    )

    # --- New: Display Cursor playbook prompts for selected record ---
    st.markdown("---")
    st.subheader("📝 View Cursor Playbook Prompts")
    if len(df) > 0:
        # Let user select a record by index or title
        options = [
            f"{i}: {row['reddit'].get('title', row['reddit'].get('url', 'No title'))[:60]}"
            for i, row in df.iterrows()
        ]
        selected = st.selectbox("Select a record to view its playbook prompts:", options, index=0)
        idx = int(selected.split(":")[0])
        playbook = df.iloc[idx].get("cursor_playbook", [])
        reddit_info = df.iloc[idx]["reddit"]
        analysis_info = df.iloc[idx]["analysis"]
        st.markdown(f"**Post Title:** [{reddit_info.get('title', 'No title')}]({reddit_info.get('url', '#')})")
        st.markdown(f"**Summary:** {analysis_info.get('problem_description', '')}")
        if isinstance(playbook, dict) and "prompts" in playbook:
            prompts = playbook["prompts"]
        else:
            prompts = playbook if isinstance(playbook, list) else []
        if prompts:
            st.markdown("**Numbered List:**")
            for i, prompt in enumerate(prompts, 1):
                st.markdown(f"{i}. {prompt}")
            st.markdown("**Code Block (copy all):**")
            st.code("\n\n".join(prompts), language="text")
        else:
            st.info("No playbook prompts found for this record.")
    else:
        st.info("No records to display prompts for.")
else:
    st.info("No data yet – run your first scrape!")

# === 4. Run scrape on click ==================================================
if scrape_btn:
    if not can_scrape():
        st.stop()
    
    conn = init_db()
    subreddit_list = [s.strip() for s in subs.split(",") if s.strip()]
    progress_feed = st.empty()
    with st.spinner("Scraping Reddit and calling GPT…"):
        new_records = []
        # Live feed list
        feed_lines = []
        # Custom duplicate filter: we wrap run_pipeline and filter its output
        results, report = run_pipeline(
            subreddit_list, posts_per, cmts_per, delay=1.2
        )
        for rec in results:
            post_id = rec["reddit"].get("id")
            if not post_id:
                # fallback to URL extraction if id is missing
                post_id = rec["reddit"]["url"].split("/")[-3]
            print(f"Checking post_id: {post_id} for title: {rec['reddit'].get('title')}")
            if already_scraped(conn, post_id):
                continue
            mark_scraped(conn, post_id)
            new_records.append(rec)
        # Show report table after scraping
        if report:
            report_df = pd.DataFrame(report)
            st.markdown("### Scrape Report")
            filter_option = st.radio(
                "Show:",
                ("All", "Viable only", "Not viable only"),
                index=0,
                horizontal=True
            )
            if filter_option == "Viable only":
                filtered_df = report_df[report_df["status"] == "Added"]
            elif filter_option == "Not viable only":
                filtered_df = report_df[report_df["status"] == "Not viable"]
            else:
                filtered_df = report_df
            st.dataframe(filtered_df[["title", "url", "status", "details"]], use_container_width=True)
        if new_records:
            # append to JSONL
            with OUT_FILE.open("a", encoding="utf-8") as f:
                for row in new_records:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            st.success(f"Added {len(new_records)} new record(s)!")
            st.session_state[usage_key] += 1
        else:
            st.warning("Nothing new this time – you’re up to date!")
    # refresh table after scrape (works on all Streamlit versions)
    if hasattr(st, "rerun"):
        st.rerun()                       # Streamlit ≥ 1.25
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()          # older releases
    # else: very old version – quietly skip the refresh

# === 5. Analyze Reddit Post by URL ===
if analyze_url_btn and url_to_analyze:
    from praw.models import Submission
    import re
    st.markdown("---")
    st.subheader("🔎 Analysis for Pasted Reddit Post URL")
    # Extract post ID from URL
    match = re.search(r"comments/([a-z0-9]+)/", url_to_analyze)
    if not match:
        st.error("Could not extract post ID from URL. Please check the format.")
    else:
        post_id = match.group(1)
        # Fetch post using PRAW
        reddit = None
        try:
            from main import get_reddit_client
            reddit = get_reddit_client()
        except Exception:
            import praw
            import os
            reddit = praw.Reddit(
                client_id=os.getenv("REDDIT_CLIENT_ID"),
                client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
                user_agent=os.getenv("REDDIT_USER_AGENT", "reddit-scraper/0.3"),
            )
        try:
            submission = reddit.submission(id=post_id)
            submission.comments.replace_more(limit=0)
            post = {
                "id": submission.id,
                "subreddit": str(submission.subreddit),
                "url": f"https://reddit.com{submission.permalink}",
                "title": submission.title,
                "body": submission.selftext or "",
                "comments": [c.body for c in submission.comments.list()[:15]],
            }
            from main import build_context, oai_json, ANALYSIS_PROMPT, SOLUTION_PROMPT, CURSOR_PLAYBOOK_PROMPT
            context = build_context(post, max_comments=10)
            analysis = oai_json(ANALYSIS_PROMPT.format(content=context))
            if not analysis:
                st.error("OpenAI error during analysis step.")
            elif not analysis.get("is_viable"):
                st.warning("This post was not found to be a viable problem or opportunity.")
                st.json(analysis)
            else:
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
                        context=context,
                    )
                )
                playbook = oai_json(
                    CURSOR_PLAYBOOK_PROMPT.format(
                        problem=problem_desc,
                        market=analysis.get("target_market", ""),
                        solution=sol.get("solution_description", ""),
                    )
                )
                st.markdown(f"**Post Title:** [{post['title']}]({post['url']})")
                problem_desc = analysis.get('problem_description', '')
                if not problem_desc:
                    problem_desc = analysis.get('opportunity_description', '')
                if not problem_desc:
                    problem_desc = 'A viable business opportunity identified from Reddit discussion'
                st.markdown(f"**Summary:** {problem_desc}")
                st.markdown(f"**Target Market:** {analysis.get('target_market', '')}")
                st.markdown(f"**Confidence Score:** {analysis.get('confidence_score', '')}")
                st.markdown(f"**Opportunity:** {'Yes' if analysis.get('is_opportunity') else 'No'}")
                st.markdown("**Solution:**")
                st.json(sol)
                if playbook and playbook.get("prompts"):
                    st.markdown("**Cursor Playbook Prompts:**")
                    for i, prompt in enumerate(playbook["prompts"], 1):
                        st.markdown(f"{i}. {prompt}")
                    st.markdown("**Code Block (copy all):**")
                    st.code("\n\n".join(playbook["prompts"]), language="text")
                else:
                    st.info("No playbook prompts found for this post.")
                # Save to results.jsonl and scraper.db
                OUT_FILE = Path("results.jsonl")
                DB_FILE = Path("scraper.db")
                # Prepare record in the same format as batch scraping
                record = {
                    "meta": {
                        "uuid": str(uuid.uuid4()),
                        "scraped_at": datetime.utcnow().isoformat(),
                    },
                    "reddit": {
                        "subreddit": post["subreddit"],
                        "url": post["url"],
                        "title": post["title"],
                        "id": post["id"],
                    },
                    "analysis": analysis,
                    "solution": sol,
                    "cursor_playbook": playbook.get("prompts", []),
                }
                with OUT_FILE.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                # Add to scraper.db
                conn = sqlite3.connect(DB_FILE)
                cur = conn.cursor()
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS scraped_posts (post_id TEXT PRIMARY KEY, scraped_at TEXT)"
                )
                cur.execute(
                    "INSERT OR IGNORE INTO scraped_posts VALUES (?,?)",
                    (post["id"], datetime.utcnow().isoformat()),
                )
                conn.commit()
                conn.close()
                st.success("This post has been added to your main results and database!")
        except Exception as e:
            st.error(f"Error fetching or analyzing post: {e}")

