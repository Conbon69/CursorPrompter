#!/usr/bin/env python3
"""
Script to create the required Supabase tables for the email verification system
"""

import os
import streamlit as st
from supabase import create_client

def create_verification_tables():
    """Create the required tables in Supabase"""
    
    # Get Supabase credentials
    try:
        SB_URL = st.secrets["SUPABASE_URL"]
        SB_KEY = st.secrets["SUPABASE_ANON_KEY"]
    except:
        SB_URL = os.getenv("SUPABASE_URL")
        SB_KEY = os.getenv("SUPABASE_ANON_KEY")
    
    if not SB_URL or not SB_KEY:
        st.error("❌ Supabase credentials not found")
        st.write("Please set SUPABASE_URL and SUPABASE_ANON_KEY in your environment or Streamlit secrets")
        return False
    
    try:
        # Create Supabase client
        sb = create_client(SB_URL, SB_KEY)
        st.success("✅ Supabase client created")
        
        # Create pending_verifications table
        st.info("🔨 Creating pending_verifications table...")
        
        # Note: We can't create tables directly with the Python client
        # You need to run the SQL manually in Supabase dashboard
        
        st.warning("⚠️ Table creation requires manual SQL execution")
        st.info("Please run the following SQL in your Supabase SQL Editor:")
        
        sql_code = """
-- Table for pending email verifications
CREATE TABLE IF NOT EXISTS pending_verifications (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '10 minutes')
);

-- Table for verified users
CREATE TABLE IF NOT EXISTS verified_users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    verified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_pending_verifications_token ON pending_verifications(token);
CREATE INDEX IF NOT EXISTS idx_pending_verifications_email ON pending_verifications(email);
CREATE INDEX IF NOT EXISTS idx_pending_verifications_expires_at ON pending_verifications(expires_at);
CREATE INDEX IF NOT EXISTS idx_verified_users_email ON verified_users(email);
        """
        
        st.code(sql_code, language="sql")
        
        # Test if tables exist after creation
        st.info("🔍 Testing table existence...")
        
        try:
            # Test pending_verifications table
            response = sb.table("pending_verifications").select("count", count="exact").limit(1).execute()
            st.success("✅ pending_verifications table exists")
        except Exception as e:
            st.error(f"❌ pending_verifications table not found: {e}")
            return False
        
        try:
            # Test verified_users table
            response = sb.table("verified_users").select("count", count="exact").limit(1).execute()
            st.success("✅ verified_users table exists")
        except Exception as e:
            st.error(f"❌ verified_users table not found: {e}")
            return False
        
        st.success("🎉 All tables created and verified successfully!")
        return True
        
    except Exception as e:
        st.error(f"❌ Error creating tables: {e}")
        return False

# Streamlit interface
st.title("🔨 Create Supabase Tables")
st.markdown("This tool helps you create the required tables for the email verification system.")

if st.button("🔨 Create Tables", use_container_width=True):
    create_verification_tables()

st.markdown("---")
st.markdown("### 📋 Instructions:")
st.markdown("1. Click the button above to get the SQL code")
st.markdown("2. Copy the SQL code")
st.markdown("3. Go to your Supabase dashboard → SQL Editor")
st.markdown("4. Paste and run the SQL")
st.markdown("5. Come back and test the connection") 