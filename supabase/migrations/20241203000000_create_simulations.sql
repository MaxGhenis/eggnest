-- Create simulations table
CREATE TABLE IF NOT EXISTS simulations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    name TEXT NOT NULL,
    input_params JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE simulations ENABLE ROW LEVEL SECURITY;

-- Users can only see their own simulations
CREATE POLICY "Users can view own simulations" ON simulations
    FOR SELECT USING (auth.uid() = user_id);

-- Users can insert their own simulations
CREATE POLICY "Users can insert own simulations" ON simulations
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Users can update their own simulations
CREATE POLICY "Users can update own simulations" ON simulations
    FOR UPDATE USING (auth.uid() = user_id);

-- Users can delete their own simulations
CREATE POLICY "Users can delete own simulations" ON simulations
    FOR DELETE USING (auth.uid() = user_id);

-- Create updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_simulations_updated_at
    BEFORE UPDATE ON simulations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create index for user lookups
CREATE INDEX IF NOT EXISTS idx_simulations_user_id ON simulations(user_id);
