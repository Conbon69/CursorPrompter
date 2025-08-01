-- Daily Usage Table for FastAPI App
-- Run this in your Supabase SQL Editor

-- Table for tracking daily usage per user
CREATE TABLE IF NOT EXISTS daily_usage (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT NOT NULL,
    date DATE NOT NULL,
    count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(email, date)
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_daily_usage_email_date ON daily_usage(email, date);
CREATE INDEX IF NOT EXISTS idx_daily_usage_date ON daily_usage(date);

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to automatically update updated_at
CREATE TRIGGER update_daily_usage_updated_at 
    BEFORE UPDATE ON daily_usage 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Function to increment usage count
CREATE OR REPLACE FUNCTION increment_daily_usage(user_email TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    INSERT INTO daily_usage (email, date, count)
    VALUES (user_email, CURRENT_DATE, 1)
    ON CONFLICT (email, date)
    DO UPDATE SET count = daily_usage.count + 1;
    
    RETURN TRUE;
EXCEPTION
    WHEN OTHERS THEN
        RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- Function to get daily usage count
CREATE OR REPLACE FUNCTION get_daily_usage(user_email TEXT)
RETURNS INTEGER AS $$
DECLARE
    usage_count INTEGER;
BEGIN
    SELECT count INTO usage_count
    FROM daily_usage
    WHERE email = user_email AND date = CURRENT_DATE;
    
    RETURN COALESCE(usage_count, 0);
END;
$$ LANGUAGE plpgsql; 