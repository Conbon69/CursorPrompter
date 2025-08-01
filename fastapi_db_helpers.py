"""
FastAPI Database Helpers for quota management
"""

import os
from datetime import date, datetime
from typing import Optional
from supabase import create_client

# Get Supabase client
try:
    import streamlit as st
    SB_URL = st.secrets["SUPABASE_URL"]
    SB_KEY = st.secrets["SUPABASE_ANON_KEY"]
except:
    SB_URL = os.getenv("SUPABASE_URL")
    SB_KEY = os.getenv("SUPABASE_ANON_KEY")

if SB_URL and SB_KEY:
    sb = create_client(SB_URL, SB_KEY)
else:
    sb = None

def get_daily_usage(email: Optional[str]) -> int:
    """Get daily usage count for user from Supabase"""
    if not sb or not email:
        return 0
    
    try:
        today = date.today().isoformat()
        
        # Query the usage table (you'll need to create this)
        response = sb.table("daily_usage").select("count").eq("email", email).eq("date", today).execute()
        
        if response.data:
            return response.data[0].get("count", 0)
        return 0
        
    except Exception as e:
        print(f"Error getting daily usage: {e}")
        return 0

def increment_daily_usage(email: Optional[str]) -> bool:
    """Increment daily usage count for user in Supabase"""
    if not sb or not email:
        return False
    
    try:
        today = date.today().isoformat()
        
        # Try to update existing record
        response = sb.table("daily_usage").update({"count": "count + 1"}).eq("email", email).eq("date", today).execute()
        
        if not response.data:
            # Create new record if none exists
            response = sb.table("daily_usage").insert({
                "email": email,
                "date": today,
                "count": 1
            }).execute()
        
        return True
        
    except Exception as e:
        print(f"Error incrementing daily usage: {e}")
        return False

def create_usage_table():
    """Create the daily_usage table in Supabase"""
    if not sb:
        return False
    
    try:
        # This would be run in Supabase SQL Editor
        sql = """
        CREATE TABLE IF NOT EXISTS daily_usage (
            id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
            email TEXT NOT NULL,
            date DATE NOT NULL,
            count INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(email, date)
        );
        
        CREATE INDEX IF NOT EXISTS idx_daily_usage_email_date ON daily_usage(email, date);
        """
        
        print("Run this SQL in your Supabase SQL Editor:")
        print(sql)
        return True
        
    except Exception as e:
        print(f"Error creating usage table: {e}")
        return False

# Fallback in-memory storage for development
_usage_store = {}

def get_daily_usage_fallback(email: Optional[str]) -> int:
    """Fallback in-memory usage tracking for development"""
    if not email:
        return 0
    
    today = date.today().isoformat()
    key = f"{email}_{today}"
    return _usage_store.get(key, 0)

def increment_daily_usage_fallback(email: Optional[str]) -> bool:
    """Fallback in-memory usage tracking for development"""
    if not email:
        return False
    
    today = date.today().isoformat()
    key = f"{email}_{today}"
    _usage_store[key] = _usage_store.get(key, 0) + 1
    return True

# Use fallback if Supabase is not configured
def get_daily_usage_safe(email: Optional[str]) -> int:
    """Get daily usage with fallback"""
    if sb:
        return get_daily_usage(email)
    else:
        return get_daily_usage_fallback(email)

def increment_daily_usage_safe(email: Optional[str]) -> bool:
    """Increment daily usage with fallback"""
    if sb:
        return increment_daily_usage(email)
    else:
        return increment_daily_usage_fallback(email) 