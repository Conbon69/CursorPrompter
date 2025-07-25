"""
db_helpers.py - Supabase database operations for storing scraped results
"""

import json
from datetime import datetime
from typing import List, Dict, Optional
import streamlit as st
from supabase import create_client

# Get Supabase client from auth module
_sb_client = None

def get_supabase_client():
    """Get Supabase client, fallback to None if not configured"""
    global _sb_client
    
    # If we already have a client, return it
    if _sb_client:
        return _sb_client
    
    # Try to import and create client
    try:
        from auth import sb
        if sb:
            _sb_client = sb
            return _sb_client
    except Exception:
        pass
    
    # If we get here, no client is available
    return None

def create_tables_if_not_exist():
    """Create necessary tables in Supabase if they don't exist"""
    # Note: In Supabase, you typically create tables via the dashboard
    # This function is for reference - tables should be created manually
    pass

def save_scraped_result(result: Dict) -> bool:
    """Save a scraped result to Supabase database"""
    client = get_supabase_client()
    if not client:
        st.error("Supabase not configured. Data will not be saved.")
        return False
    
    try:
        # Get user ID using the new helper function
        from auth_manual import get_user_id
        user_id = get_user_id()
        
        # Prepare the data for insertion
        data = {
            "uuid": result["meta"]["uuid"],
            "scraped_at": result["meta"]["scraped_at"],
            "subreddit": result["reddit"]["subreddit"],
            "reddit_url": result["reddit"]["url"],
            "reddit_title": result["reddit"]["title"],
            "reddit_id": result["reddit"]["id"],
            "analysis": json.dumps(result["analysis"]),
            "solution": json.dumps(result["solution"]),
            "cursor_playbook": json.dumps(result["cursor_playbook"]),
            "user_id": user_id
        }
        
        # Insert into scraped_results table
        response = client.table("scraped_results").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Error saving to database: {e}")
        return False

def get_all_scraped_results() -> List[Dict]:
    """Get all scraped results from Supabase database"""
    client = get_supabase_client()
    if not client:
        return []
    
    try:
        # Get user ID using the new helper function
        from auth_manual import get_user_id
        user_id = get_user_id()
        
        if user_id == "anonymous":
            # Anonymous users can only see their own results (stored in session)
            return []
        
        response = client.table("scraped_results").select("*").eq("user_id", user_id).order("scraped_at", desc=True).execute()
        
        # Convert back to the original format
        results = []
        for row in response.data:
            result = {
                "meta": {
                    "uuid": row["uuid"],
                    "scraped_at": row["scraped_at"]
                },
                "reddit": {
                    "subreddit": row["subreddit"],
                    "url": row["reddit_url"],
                    "title": row["reddit_title"],
                    "id": row["reddit_id"]
                },
                "analysis": json.loads(row["analysis"]),
                "solution": json.loads(row["solution"]),
                "cursor_playbook": json.loads(row["cursor_playbook"])
            }
            results.append(result)
        
        return results
    except Exception as e:
        st.error(f"Error loading from database: {e}")
        return []

def save_to_session_state(result: Dict):
    """Save result to session state for anonymous users"""
    if "session_results" not in st.session_state:
        st.session_state.session_results = []
    
    st.session_state.session_results.append(result)

def get_session_results() -> List[Dict]:
    """Get results from session state for anonymous users"""
    return st.session_state.get("session_results", [])

def mark_post_scraped(post_id: str):
    """Mark a post as scraped in Supabase"""
    client = get_supabase_client()
    if not client:
        return
    
    try:
        # Get user ID using the new helper function
        from auth_manual import get_user_id
        user_id = get_user_id()
        
        data = {
            "post_id": post_id,
            "scraped_at": datetime.utcnow().isoformat(),
            "user_id": user_id
        }
        client.table("scraped_posts").insert(data).execute()
    except Exception as e:
        # If table doesn't exist, just continue
        pass

def is_post_already_scraped(post_id: str) -> bool:
    """Check if a post has already been scraped"""
    client = get_supabase_client()
    if not client:
        return False
    
    try:
        # Get user ID using the new helper function
        from auth_manual import get_user_id
        user_id = get_user_id()
        
        response = client.table("scraped_posts").select("post_id").eq("post_id", post_id).eq("user_id", user_id).execute()
        return len(response.data) > 0
    except Exception as e:
        return False 