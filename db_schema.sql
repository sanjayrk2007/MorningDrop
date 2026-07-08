-- ============================================================
--  Morning Drop Subscriber Table Schema
--  Run this in the Supabase SQL Editor to set up database.
-- ============================================================

CREATE TABLE IF NOT EXISTS subscribers (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    preferences JSONB DEFAULT '{"all": true}'::jsonb
);

-- Enable Row Level Security (RLS)
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;

-- Allow anonymous inserts (for the signup landing page)
CREATE POLICY "Allow public signups" ON subscribers
    FOR INSERT 
    TO anon
    WITH CHECK (is_active = true);

-- Allow authenticated service-role to read/write all data (for the GitHub Action runner)
CREATE POLICY "Allow service-role full access" ON subscribers
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
