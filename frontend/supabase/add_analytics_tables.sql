-- Add Advanced Analytics Tables for Agent SaaS v5.0

-- 1. analysis_runs: The snapshot of each audit cycle
CREATE TABLE IF NOT EXISTS analysis_runs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id TEXT NOT NULL, -- Simplified for local testing without formal tenants table
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  raw_data_snapshot JSONB, 
  coherence_score FLOAT, 
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. financial_metrics: ERP vs SII Triangulation Data
CREATE TABLE IF NOT EXISTS financial_metrics (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  run_id UUID REFERENCES analysis_runs(id),
  metric_name TEXT, -- 'Revenue', 'Operating_Cost', 'Net_Profit'
  erp_value NUMERIC,
  sii_value NUMERIC,
  delta NUMERIC,
  currency TEXT DEFAULT 'CLP',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. risk_inventory: Cross-agent risk tracking
CREATE TABLE IF NOT EXISTS risk_inventory (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  run_id UUID REFERENCES analysis_runs(id),
  agent_type TEXT, -- 'Financial', 'Legal', 'HR', 'Director'
  risk_level TEXT, -- 'Low', 'Medium', 'High', 'Critical'
  description TEXT,
  impact_estimate NUMERIC,
  status TEXT DEFAULT 'active', -- 'active', 'mitigated', 'ignored'
  mitigation_date TIMESTAMP,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. savings_tracker: ROI counter for the Dashboard
CREATE TABLE IF NOT EXISTS savings_tracker (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id TEXT NOT NULL,
  run_id UUID REFERENCES analysis_runs(id),
  saving_type TEXT, -- 'Bank_Arbitrage', 'Tax_Correction', 'Contract_Optimization'
  amount_saved NUMERIC NOT NULL,
  description TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS (Simplified for MVP)
ALTER TABLE analysis_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE financial_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_inventory ENABLE ROW LEVEL SECURITY;
ALTER TABLE savings_tracker ENABLE ROW LEVEL SECURITY;

-- Dynamic Policies
CREATE POLICY "Allow public select for MVP" ON analysis_runs FOR SELECT USING (true);
CREATE POLICY "Allow public select for MVP" ON financial_metrics FOR SELECT USING (true);
CREATE POLICY "Allow public select for MVP" ON risk_inventory FOR SELECT USING (true);
CREATE POLICY "Allow public select for MVP" ON savings_tracker FOR SELECT USING (true);
