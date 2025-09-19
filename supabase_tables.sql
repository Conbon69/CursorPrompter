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

-- Billing: subscriptions table (RLS-enabled)
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    plan TEXT NOT NULL CHECK (plan IN ('free','starter')),
    status TEXT NOT NULL,
    current_period_end TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_subscriptions_email ON subscriptions(email);
CREATE INDEX IF NOT EXISTS idx_subscriptions_customer ON subscriptions(customer_id);

-- Basic RLS policies: users can read their own record by email; service role can write
DROP POLICY IF EXISTS subscriptions_read_own ON subscriptions;
CREATE POLICY subscriptions_read_own ON subscriptions
FOR SELECT USING (auth.jwt() ->> 'email' = email);

-- Update updated_at on write
CREATE OR REPLACE FUNCTION update_subscriptions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_subscriptions_updated_at ON subscriptions;
CREATE TRIGGER trg_update_subscriptions_updated_at
BEFORE UPDATE ON subscriptions
FOR EACH ROW
EXECUTE FUNCTION update_subscriptions_updated_at();

-- Upgrade interest leads (no-RLS, server writes only)
CREATE TABLE IF NOT EXISTS upgrade_interests (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT,
    path TEXT,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE upgrade_interests DISABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_upgrade_interests_email ON upgrade_interests(email);