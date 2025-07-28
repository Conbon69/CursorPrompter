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

# Helper function for copying text to clipboard
def copy_to_clipboard(text, key_prefix="copy"):
    """Copy text to clipboard using JavaScript injection"""
    try:
        # Escape the text for JavaScript
        escaped_text = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
        
        # Create JavaScript code to copy to clipboard
        js_code = f"""
        <script>
        function copyToClipboard() {{
            const text = "{escaped_text}";
            if (navigator.clipboard && window.isSecureContext) {{
                navigator.clipboard.writeText(text).then(function() {{
                    console.log('Copied to clipboard successfully');
                }}).catch(function(err) {{
                    console.error('Failed to copy: ', err);
                    fallbackCopy();
                }});
            }} else {{
                fallbackCopy();
            }}
            
            function fallbackCopy() {{
                const textArea = document.createElement('textarea');
                textArea.value = text;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                textArea.style.top = '-999999px';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                try {{
                    document.execCommand('copy');
                    console.log('Fallback copy successful');
                }} catch (err) {{
                    console.error('Fallback copy failed: ', err);
                }}
                document.body.removeChild(textArea);
            }}
        }}
        copyToClipboard();
        </script>
        """
        
        # Inject the JavaScript
        st.components.v1.html(js_code, height=0)
        st.success("✅ Copied to clipboard!")
        
    except Exception as e:
        # Fallback: show the text in a code block
        st.code(text, language="text")
        st.info("📋 Click the copy button in the code block above to copy the text.")

# === 1. import the pipeline and new verification system ================================
from main import run_pipeline  # same dir
from email_verification import (
    handle_verification_flow, 
    get_current_user_email, 
    is_user_verified, 
    sign_out_verified_user,
    create_verification_record,
    send_verification_email,
    debug_supabase_connection,
    is_email_verified,
    update_last_login
)
from db_helpers import (
    save_scraped_result_new, 
    get_all_scraped_results_new, 
    save_to_session_state, 
    get_session_results, 
    mark_post_scraped_new, 
    is_post_already_scraped_new
)

# Handle magic link authentication (will be called after UI setup)

# === 1.5. Quota management ===================================================
FREE_LIMIT = 2
VERIFIED_LIMIT = 15
usage_key = f"usage_{date.today()}"
st.session_state.setdefault(usage_key, 0)

def can_scrape():
    is_verified = is_user_verified()
    limit = VERIFIED_LIMIT if is_verified else FREE_LIMIT
    used = st.session_state[usage_key]
    if used >= limit:
        if not is_verified:
            st.error(f"Daily limit reached ({FREE_LIMIT}). Please verify your email for more scrapes!")
            if st.button("🔐 Verify Email Now", use_container_width=True):
                st.session_state.show_verification = True
                st.rerun()
            return False
        else:
            st.warning(f"Daily limit reached ({VERIFIED_LIMIT}). Come back tomorrow!")
            return False
    return True

def show_quota_status():
    """Display current quota usage in the sidebar"""
    is_verified = is_user_verified()
    limit = VERIFIED_LIMIT if is_verified else FREE_LIMIT
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
    return is_post_already_scraped_new(post_id)

def mark_scraped(conn, post_id: str):
    mark_post_scraped_new(post_id)

# === 3. Streamlit UI =========================================================
st.set_page_config(
    page_title="Reddit → SaaS Idea Finder", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# === 3.5. Restore user email from URL parameters for persistence ===
# Check for email in URL parameters and restore to session state if not already set
params = st.query_params
if "email" in params and "user_email" not in st.session_state:
    email_from_url = params["email"]
    # Verify the email is actually verified in our database
    if is_email_verified(email_from_url):
        st.session_state["user_email"] = email_from_url
        st.session_state["is_verified"] = True
        st.success(f"✅ Welcome back, {email_from_url}!")

st.sidebar.header("Scrape controls")

# Handle verification flow first
handle_verification_flow()

# Authentication status and verification button
user_email = get_current_user_email()
if user_email:
    st.sidebar.success(f"✅ Verified as {user_email}")
    if st.sidebar.button("🚪 Sign Out", use_container_width=True):
        sign_out_verified_user()
else:
    st.sidebar.info("👤 Anonymous user (2 scrapes/day)")
    if st.sidebar.button("🔐 Verify Email", use_container_width=True):
        st.session_state.show_verification = True

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

# === 2. Authentication Section ===
st.markdown("---")
st.subheader("🔐 Authentication")

# Check if user is already verified
if is_user_verified():
    user_email = get_current_user_email()
    st.success(f"✅ Signed in as: {user_email}")
    if st.button("🚪 Sign Out"):
        sign_out_verified_user()
        st.rerun()
else:
    # Show authentication options
    auth_option = st.radio(
        "Choose authentication method:",
        ["📧 Verify Email (New Users)", "🔑 Sign In (Verified Users)"],
        index=0
    )
    
    if auth_option == "📧 Verify Email (New Users)":
        # Email verification flow
        with st.form("email_verification_form"):
            email = st.text_input("Email", placeholder="your@email.com")
            submit_button = st.form_submit_button("Send Verification Email")
            
            if submit_button and email:
                try:
                    st.info(f"🔍 Creating verification for {email}...")
                    
                    # Create verification record
                    token = create_verification_record(email)
                    
                    if token:
                        # Get the current app URL dynamically
                        try:
                            # Try to get current URL from Streamlit
                            app_url = st.get_option("server.baseUrlPath") or "http://localhost:8501"
                            if "localhost" in app_url or "127.0.0.1" in app_url:
                                # We're running locally
                                app_url = "http://localhost:8501"
                            else:
                                # We're on Streamlit Cloud
                                app_url = "https://cursorprompter-1.streamlit.app"
                        except:
                            # Fallback
                            app_url = "http://localhost:8501"
                        
                        # Send verification email (placeholder for now)
                        send_verification_email(email, token, app_url)
                        
                        st.success("✅ Verification email sent! Check your inbox and click the link to verify.")
                        st.info("After clicking the verification link, you'll be redirected back here and automatically verified.")
                        
                    else:
                        st.error("❌ Failed to create verification record")
                        
                except Exception as e:
                    st.error(f"❌ Error sending verification email: {e}")
    
    elif auth_option == "🔑 Sign In (Verified Users)":
        # Simple sign-in for verified users
        with st.form("sign_in_form"):
            email = st.text_input("Email", placeholder="your@email.com")
            sign_in_button = st.form_submit_button("Sign In")
            
            if sign_in_button and email:
                with st.spinner("Checking verification status..."):
                    if is_email_verified(email):
                        # User is verified, sign them in
                        st.session_state["user_email"] = email
                        st.session_state["is_verified"] = True
                        update_last_login(email)
                        
                        # Store email in URL parameters for persistence
                        st.query_params["email"] = email
                        
                        st.success(f"✅ Welcome back, {email}!")
                        st.rerun()
                    else:
                        st.error("❌ Email not verified. Please use the 'Verify Email' option first.")
                        st.info("💡 If you've verified this email before, make sure you're using the exact same email address.")

# Debug section (temporary)
st.sidebar.markdown("---")
st.sidebar.markdown("**🔧 Debug Tools**")
if st.sidebar.button("🔍 Test Supabase Connection", use_container_width=True):
    st.sidebar.markdown("---")
    st.sidebar.markdown("**🔍 Supabase Debug Results**")
    debug_supabase_connection()

st.sidebar.markdown("---")
url_to_analyze = st.sidebar.text_input("Analyze a Reddit post by URL", value="", placeholder="https://reddit.com/r/...")
analyze_url_btn = st.sidebar.button("Analyze URL", use_container_width=True)

st.title("💡 Reddit → SaaS Idea Finder")

# Load existing results from database or session
user_email = get_current_user_email()

if user_email:
    # Verified user - load from Supabase
    results = get_all_scraped_results_new()
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
        
        # Download button for verified users
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

# --- Display Cursor playbook prompts for selected record ---
if results and len(results) > 0:
    st.markdown("---")
    st.subheader("📝 View Cursor Playbook Prompts")
    # Let user select a record by index or title
    options = [
        f"{i}: {result['reddit']['title'][:60]}"
        for i, result in enumerate(results)
    ]
    selected = st.selectbox("Select a record to view its playbook prompts:", options, index=0)
    idx = int(selected.split(":")[0])
    result = results[idx]
    playbook = result.get("cursor_playbook", [])
    reddit_info = result["reddit"]
    analysis_info = result["analysis"]
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
            # Create a row with the prompt text and copy button
            col1, col2 = st.columns([0.9, 0.1])
            with col1:
                st.markdown(f"{i}. {prompt}")
            with col2:
                if st.button("📋", key=f"copy_{i}", help=f"Copy prompt {i} to clipboard"):
                    copy_to_clipboard(prompt, f"prompt_{i}")
        
        # Copy all prompts button
        if st.button("📋 Copy All Prompts", key="copy_all_prompts", help="Copy all prompts to clipboard"):
            copy_to_clipboard("\n\n".join(prompt_strings), "all_prompts")
        
        st.markdown("**Code Block (copy all):**")
        st.code("\n\n".join(prompt_strings), language="text")
    else:
        st.info("No playbook prompts found for this record.")

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
            is_verified = is_user_verified()
            for record in new_records:
                if is_verified:
                    # Verified user - save to Supabase
                    save_scraped_result_new(record)
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
    
    # Create progress containers for URL analysis
    url_progress_container = st.container()
    url_status_container = st.container()
    
    with url_progress_container:
        url_progress_bar = st.progress(0)
        url_status_text = st.empty()
    
    with url_status_container:
        # Extract post ID from URL
        url_status_text.text("🔍 Extracting post ID from URL...")
        url_progress_bar.progress(10)
        
        match = re.search(r"comments/([a-z0-9]+)/", url_to_analyze)
        if not match:
            st.error("Could not extract post ID from URL. Please check the format.")
        else:
            post_id = match.group(1)
            
            # Fetch post using PRAW
            url_status_text.text("📡 Fetching Reddit post data...")
            url_progress_bar.progress(20)
            
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
                
                url_status_text.text("🧠 Analyzing post content...")
                url_progress_bar.progress(40)
                
                from main import build_context, oai_json, ANALYSIS_PROMPT, SOLUTION_PROMPT, CURSOR_PLAYBOOK_PROMPT
                context = build_context(post, max_comments=10)
                analysis = oai_json(ANALYSIS_PROMPT.format(content=context))
                
                if not analysis:
                    url_progress_bar.progress(100)
                    url_status_text.text("❌ OpenAI error during analysis step.")
                    st.error("OpenAI error during analysis step.")
                elif not analysis.get("is_viable"):
                    url_progress_bar.progress(100)
                    url_status_text.text("⏭️ Post not viable - skipping further analysis.")
                    st.warning("This post was not found to be a viable problem or opportunity.")
                    st.json(analysis)
                else:
                    url_status_text.text("💡 Generating solution...")
                    url_progress_bar.progress(60)
                    
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
                    
                    url_status_text.text("📝 Creating Cursor playbook...")
                    url_progress_bar.progress(80)
                    
                    playbook = oai_json(
                        CURSOR_PLAYBOOK_PROMPT.format(
                            problem=problem_desc,
                            market=analysis.get("target_market", ""),
                            solution=sol.get("solution_description", ""),
                        )
                    )
                    
                    url_progress_bar.progress(100)
                    url_status_text.text("✅ Analysis completed!")
                    
                    # Display results
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
                    
                    # Analysis section with copy button
                    col1, col2 = st.columns([0.9, 0.1])
                    with col1:
                        st.markdown("**Analysis:**")
                    with col2:
                        if st.button("📋", key="url_analysis_copy", help="Copy analysis to clipboard"):
                            analysis_text = json.dumps(analysis, indent=2, ensure_ascii=False)
                            copy_to_clipboard(analysis_text, "url_analysis")
                    st.json(analysis)
                    
                    # Solution section with copy button
                    col1, col2 = st.columns([0.9, 0.1])
                    with col1:
                        st.markdown("**Solution:**")
                    with col2:
                        if st.button("📋", key="url_solution_copy", help="Copy solution to clipboard"):
                            solution_text = json.dumps(sol, indent=2, ensure_ascii=False)
                            copy_to_clipboard(solution_text, "url_solution")
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
                            # Create a row with the prompt text and copy button
                            col1, col2 = st.columns([0.9, 0.1])
                            with col1:
                                st.markdown(f"{i}. {prompt}")
                            with col2:
                                if st.button("📋", key=f"url_copy_{i}", help=f"Copy prompt {i} to clipboard"):
                                    copy_to_clipboard(prompt, f"url_prompt_{i}")
                        
                        # Copy all prompts button for URL analysis
                        if st.button("📋 Copy All Prompts", key="url_copy_all_prompts", help="Copy all prompts to clipboard"):
                            all_prompts_text = "\n\n".join(prompt_strings)
                            copy_to_clipboard(all_prompts_text, "url_all_prompts")
                        
                        st.markdown("**Code Block (copy all):**")
                        st.code("\n\n".join(prompt_strings), language="text")
                    else:
                        st.info("No playbook prompts found for this post.")
                        
            except Exception as e:
                url_progress_bar.progress(100)
                url_status_text.text("❌ Error analyzing post.")
                st.error(f"Error analyzing post: {e}")
    
    # Clear URL analysis progress after a short delay
    import time
    time.sleep(2)
    url_progress_container.empty()
    url_status_container.empty()

