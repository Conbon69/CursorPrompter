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
from db_helpers import save_scraped_result, get_all_scraped_results, save_to_session_state, get_session_results, mark_post_scraped, is_post_already_scraped
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
            st.error(f"Daily limit reached ({FREE_LIMIT}). Please sign in for more scrapes!")
            if st.button("🔐 Sign In Now", use_container_width=True):
                st.session_state.show_signup = True
                st.rerun()
            return False
        else:
            st.warning(f"Daily limit reached ({AUTH_LIMIT}). Come back tomorrow!")
            return False
    return True

def show_quota_status():
    """Display current quota usage in the sidebar"""
    is_auth = auth.current_user() is not None
    limit = AUTH_LIMIT if is_auth else FREE_LIMIT
    used = st.session_state[usage_key]
    remaining = max(0, limit - used)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**📊 Daily Quota**")
    st.sidebar.progress(used / limit)
    st.sidebar.markdown(f"**{used}/{limit}** scrapes used")
    st.sidebar.markdown(f"**{remaining}** remaining today")

# === 2. DB helpers ===========================================================
# Legacy SQLite functions (kept for backward compatibility)
DB_FILE = Path("scraper.db")
OUT_FILE = Path("results.jsonl")

def init_db():
    # This is now a no-op since we're using Supabase
    return None

def already_scraped(conn, post_id: str) -> bool:
    return is_post_already_scraped(post_id)

def mark_scraped(conn, post_id: str):
    mark_post_scraped(post_id)

# === 3. Streamlit UI =========================================================
st.set_page_config(
    page_title="Reddit → SaaS Idea Finder", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.sidebar.header("Scrape controls")

# Authentication status and login button
user = auth.current_user()
if user:
    st.sidebar.success(f"✅ Logged in as {user.get('email', 'User')}")
    if st.sidebar.button("🚪 Sign Out", use_container_width=True):
        auth.sign_out()
        st.rerun()
else:
    st.sidebar.info("👤 Anonymous user (2 scrapes/day)")
    if st.sidebar.button("🔐 Sign In", use_container_width=True):
        st.session_state.show_signup = True

subs = st.sidebar.text_input(
    "Subreddits (comma‑separated)", 
    value="vibecoding, smallbusiness",
    placeholder="ex: vibecoding, smallbusiness"
)
posts_per = st.sidebar.slider("Posts per subreddit", 1, 3, 2)
cmts_per = st.sidebar.slider("Comments per post", 1, 30, 15)
scrape_btn = st.sidebar.button("🚀 Scrape now", use_container_width=True)

# Show quota status
show_quota_status()

st.sidebar.markdown("---")
url_to_analyze = st.sidebar.text_input("Analyze a Reddit post by URL", value="", placeholder="https://reddit.com/r/...")
analyze_url_btn = st.sidebar.button("Analyze URL", use_container_width=True)

st.title("💡 Reddit → SaaS Idea Finder")

# Show signup form if requested
if st.session_state.get("show_signup", False):
    auth.require_signup()
    if st.button("← Back to Scraper"):
        st.session_state.show_signup = False
        st.rerun()
    st.stop()

# Load existing results from database or session
user = auth.current_user()
if user:
    # Authenticated user - load from Supabase
    results = get_all_scraped_results()
    if results:
        st.write(f"📊 Total records loaded: {len(results)}")
        # Convert to DataFrame for display
        df_data = []
        for result in results:
            df_data.append({
                "reddit": f"{result['reddit']['title'][:50]}...",
                "analysis": result['analysis'].get('problem_description', '')[:100] + "...",
                "solution": result['solution'].get('solution_description', '')[:100] + "..."
            })
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
        
        # Download button for authenticated users
        if st.button("⬇️ Download Results as JSON"):
            json_data = json.dumps(results, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 Download JSON",
                data=json_data,
                file_name="scraped_results.json",
                mime="application/json"
            )
    else:
        st.info("No previous results found. Start scraping to see your data!")
else:
    # Anonymous user - load from session state
    results = get_session_results()
    if results:
        st.write(f"📊 Session records: {len(results)} (will be lost on page refresh)")
        df_data = []
        for result in results:
            df_data.append({
                "reddit": f"{result['reddit']['title'][:50]}...",
                "analysis": result['analysis'].get('problem_description', '')[:100] + "...",
                "solution": result['solution'].get('solution_description', '')[:100] + "..."
            })
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No data yet – run your first scrape!")

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
        
        # Convert prompts to strings if they're dictionaries
        if prompts:
            prompt_strings = []
            for prompt in prompts:
                if isinstance(prompt, dict):
                    # If it's a dict, try to extract the text content
                    if "content" in prompt:
                        prompt_strings.append(str(prompt["content"]))
                    elif "text" in prompt:
                        prompt_strings.append(str(prompt["text"]))
                    else:
                        prompt_strings.append(str(prompt))
                else:
                    prompt_strings.append(str(prompt))
            
            st.markdown("**Numbered List:**")
            for i, prompt in enumerate(prompt_strings, 1):
                st.markdown(f"{i}. {prompt}")
            st.markdown("**Code Block (copy all):**")
            st.code("\n\n".join(prompt_strings), language="text")
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
            # Save to database or session state
            user = auth.current_user()
            for record in new_records:
                if user:
                    # Authenticated user - save to Supabase
                    save_scraped_result(record)
                else:
                    # Anonymous user - save to session state
                    save_to_session_state(record)
            
            st.success(f"Added {len(new_records)} new record(s)!")
            st.session_state[usage_key] += 1
        else:
            st.warning("Nothing new this time – you're up to date!")
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
                    prompts = playbook["prompts"]
                    # Convert prompts to strings if they're dictionaries
                    prompt_strings = []
                    for prompt in prompts:
                        if isinstance(prompt, dict):
                            if "content" in prompt:
                                prompt_strings.append(str(prompt["content"]))
                            elif "text" in prompt:
                                prompt_strings.append(str(prompt["text"]))
                            else:
                                prompt_strings.append(str(prompt))
                        else:
                            prompt_strings.append(str(prompt))
                    
                    for i, prompt in enumerate(prompt_strings, 1):
                        st.markdown(f"{i}. {prompt}")
                    st.markdown("**Code Block (copy all):**")
                    st.code("\n\n".join(prompt_strings), language="text")
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

