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
    """Increment daily usage count for user in Supabase (delegates to increment by 1)."""
    return increment_daily_usage_by(email, 1)

def increment_daily_usage_by(email: Optional[str], amount: int) -> bool:
    """Increment daily usage count for user in Supabase by a specified amount.

    Falls back to a no-op if invalid params. Prefer using the *_safe wrapper.
    """
    if not sb or not email:
        return False
    if amount <= 0:
        return True
    try:
        today = date.today().isoformat()
        # Read current value (atomic RPC would be ideal; this is sufficient for our use case)
        resp = sb.table("daily_usage").select("count").eq("email", email).eq("date", today).limit(1).execute()
        if resp.data:
            current = resp.data[0].get("count", 0) or 0
            new_count = int(current) + int(amount)
            sb.table("daily_usage").update({"count": new_count}).eq("email", email).eq("date", today).execute()
        else:
            sb.table("daily_usage").insert({"email": email, "date": today, "count": int(amount)}).execute()
        return True
    except Exception as e:
        print(f"Error incrementing daily usage by amount: {e}")
        return False

def get_month_start_str() -> str:
    """Return YYYY-MM-01 for current month."""
    today = date.today()
    return f"{today.year:04d}-{today.month:02d}-01"

def get_monthly_usage(email: Optional[str]) -> int:
    """Sum daily_usage counts for the current month for a user (Supabase)."""
    if not sb or not email:
        return 0
    try:
        month_start = get_month_start_str()
        today = date.today().isoformat()
        # Fetch all rows this month and sum counts client-side (sufficient for our scale)
        resp = (
            sb.table("daily_usage")
            .select("count,date")
            .eq("email", email)
            .gte("date", month_start)
            .lte("date", today)
            .execute()
        )
        rows = resp.data or []
        total = 0
        for r in rows:
            try:
                total += int(r.get("count") or 0)
            except Exception:
                continue
        return total
    except Exception as e:
        print(f"Error getting monthly usage: {e}")
        return 0

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
    """Fallback in-memory usage tracking for development (supports anonymous)."""
    anon_safe_email = email or "anonymous"
    today = date.today().isoformat()
    key = f"{anon_safe_email}_{today}"
    return _usage_store.get(key, 0)

def increment_daily_usage_fallback(email: Optional[str]) -> bool:
    """Fallback in-memory usage tracking for development (supports anonymous)."""
    anon_safe_email = email or "anonymous"
    today = date.today().isoformat()
    key = f"{anon_safe_email}_{today}"
    _usage_store[key] = _usage_store.get(key, 0) + 1
    return True

def increment_daily_usage_by_fallback(email: Optional[str], amount: int) -> bool:
    """Fallback in-memory usage tracking for development by a specific amount (supports anonymous)."""
    if amount <= 0:
        return True
    today = date.today().isoformat()
    anon_safe_email = email or "anonymous"
    key = f"{anon_safe_email}_{today}"
    _usage_store[key] = _usage_store.get(key, 0) + int(amount)
    return True

def get_monthly_usage_fallback(email: Optional[str]) -> int:
    """Sum fallback daily counters for the current month for this user (supports anonymous)."""
    from datetime import date as _date
    today = _date.today()
    month_prefix = f"{(email or 'anonymous')}_{today.year:04d}-{today.month:02d}-"
    total = 0
    for k, v in _usage_store.items():
        if isinstance(k, str) and k.startswith(month_prefix):
            try:
                total += int(v)
            except Exception:
                continue
    return total

# Use fallback if Supabase is not configured
def get_daily_usage_safe(email: Optional[str]) -> int:
    """Get daily usage with fallback. Anonymous users always use fallback to avoid DB writes."""
    if not sb or not email:
        return get_daily_usage_fallback(email)
    try:
        return get_daily_usage(email)
    except Exception:
        return get_daily_usage_fallback(email)

def increment_daily_usage_safe(email: Optional[str]) -> bool:
    """Increment daily usage with fallback. Anonymous users use fallback."""
    if not sb or not email:
        return increment_daily_usage_fallback(email)
    ok = False
    try:
        ok = increment_daily_usage(email)
    except Exception:
        ok = False
    if not ok:
        return increment_daily_usage_fallback(email)
    return True

def increment_daily_usage_by_safe(email: Optional[str], amount: int) -> bool:
    """Increment daily usage with fallback by a specific amount. Anonymous users use fallback."""
    if not sb or not email:
        return increment_daily_usage_by_fallback(email, amount)
    ok = False
    try:
        ok = increment_daily_usage_by(email, amount)
    except Exception:
        ok = False
    if not ok:
        return increment_daily_usage_by_fallback(email, amount)
    return True

def get_monthly_usage_safe(email: Optional[str]) -> int:
    """Get monthly usage with fallback. Anonymous users always use fallback."""
    if not sb or not email:
        return get_monthly_usage_fallback(email)
    try:
        return get_monthly_usage(email)
    except Exception:
        return get_monthly_usage_fallback(email)

# --- Plan helpers ---
FREE_PLAN_LIMIT = 30
STARTER_PLAN_LIMIT = 300

def get_user_plan(email: Optional[str]) -> str:
    """Return 'starter' if user has active starter subscription; else 'free'."""
    if not sb or not email:
        return 'free'
    try:
        resp = (
            sb.table('subscriptions')
            .select('plan,status,current_period_end')
            .eq('email', email)
            .order('updated_at', desc=True)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            return 'free'
        row = rows[0]
        status = (row.get('status') or '').lower()
        plan = (row.get('plan') or 'free').lower()
        if plan == 'starter' and status in ('active','trialing','past_due'):
            # Optionally, ensure current_period_end is in the future
            return 'starter'
        return 'free'
    except Exception:
        return 'free'

def get_plan_monthly_limit(plan: str) -> int:
    if plan == 'starter':
        return STARTER_PLAN_LIMIT
    return FREE_PLAN_LIMIT