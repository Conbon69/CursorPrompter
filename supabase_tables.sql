-- Custom Email Verification System Tables
-- Run these in your Supabase SQL Editor

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

-- Function to clean up expired verifications (optional)
CREATE OR REPLACE FUNCTION cleanup_expired_verifications()
RETURNS void AS $$
BEGIN
    DELETE FROM pending_verifications WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- FIX FOR RLS ISSUE: Disable Row-Level Security on scraped_results table
-- This allows our custom authentication system to work properly
ALTER TABLE scraped_results DISABLE ROW LEVEL SECURITY;

-- Also disable RLS on scraped_posts table if it exists
ALTER TABLE scraped_posts DISABLE ROW LEVEL SECURITY;

-- Optional: Set up a cron job to clean up expired verifications every hour
-- SELECT cron.schedule('cleanup-expired-verifications', '0 * * * *', 'SELECT cleanup_expired_verifications();'); 