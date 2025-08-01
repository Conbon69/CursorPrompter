#!/usr/bin/env python3
"""
Check Supabase setup and required tables
"""

import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

def check_supabase_setup():
    """Check if Supabase is properly configured and tables exist"""
    
    print("🔍 Checking Supabase Setup...")
    
    # Check environment variables
    sb_url = os.getenv("SUPABASE_URL")
    sb_key = os.getenv("SUPABASE_ANON_KEY")
    
    print(f"SUPABASE_URL: {'✅ Set' if sb_url else '❌ Missing'}")
    print(f"SUPABASE_ANON_KEY: {'✅ Set' if sb_key else '❌ Missing'}")
    
    if not sb_url or not sb_key:
        print("❌ Supabase credentials not found in environment variables")
        return False
    
    try:
        # Create Supabase client
        sb = create_client(sb_url, sb_key)
        print("✅ Supabase client created successfully")
        
        # Check required tables
        required_tables = [
            "pending_verifications",
            "verified_users", 
            "daily_usage"
        ]
        
        for table in required_tables:
            try:
                # Try to select from table
                response = sb.table(table).select("count", count="exact").limit(1).execute()
                print(f"✅ Table '{table}' exists")
            except Exception as e:
                print(f"❌ Table '{table}' not found: {e}")
        
        # Check if we can insert/read from tables
        print("\n🔍 Testing table operations...")
        
        # Test pending_verifications
        try:
            test_data = {
                "email": "test@example.com",
                "token": "test-token-123",
                "expires_at": "2024-12-31T23:59:59Z"
            }
            response = sb.table("pending_verifications").insert(test_data).execute()
            print("✅ Can insert into pending_verifications")
            
            # Clean up test data
            sb.table("pending_verifications").delete().eq("token", "test-token-123").execute()
            print("✅ Can delete from pending_verifications")
        except Exception as e:
            print(f"❌ Error with pending_verifications: {e}")
        
        # Test verified_users
        try:
            response = sb.table("verified_users").select("*").limit(1).execute()
            print("✅ Can read from verified_users")
        except Exception as e:
            print(f"❌ Error with verified_users: {e}")
        
        # Test daily_usage
        try:
            response = sb.table("daily_usage").select("*").limit(1).execute()
            print("✅ Can read from daily_usage")
        except Exception as e:
            print(f"❌ Error with daily_usage: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error connecting to Supabase: {e}")
        return False

if __name__ == "__main__":
    check_supabase_setup() 