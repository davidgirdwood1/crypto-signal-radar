CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS raw_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source TEXT NOT NULL,
  source_event_type TEXT NOT NULL,
  external_id TEXT,
  chain_id TEXT,
  token_address TEXT,
  symbol TEXT,
  name TEXT,
  url TEXT,
  description TEXT,
  raw_payload JSONB NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  unique_hash TEXT UNIQUE NOT NULL,
  processing_status TEXT DEFAULT 'new'
);

CREATE TABLE IF NOT EXISTS classified_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  raw_event_id UUID REFERENCES raw_events(id),
  source TEXT NOT NULL,
  symbol TEXT,
  name TEXT,
  classification TEXT NOT NULL,
  sentiment TEXT NOT NULL,
  risk_score INTEGER NOT NULL,
  confidence NUMERIC NOT NULL,
  summary TEXT NOT NULL,
  reasoning TEXT NOT NULL,
  suggested_action TEXT NOT NULL,
  affected_assets JSONB DEFAULT '[]',
  model_name TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  model_latency_ms INTEGER,
  raw_model_response JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  raw_event_id UUID REFERENCES raw_events(id),
  model_name TEXT NOT NULL,
  prompt_version TEXT NOT NULL,
  input_tokens INTEGER,
  output_tokens INTEGER,
  latency_ms INTEGER,
  status TEXT NOT NULL,
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS worker_heartbeats (
  worker_name TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  last_seen_at TIMESTAMPTZ NOT NULL,
  details JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS dead_letters (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_topic TEXT NOT NULL,
  payload JSONB NOT NULL,
  error_message TEXT NOT NULL,
  retry_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_raw_events_observed_at ON raw_events (observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_events_status ON raw_events (processing_status);
CREATE INDEX IF NOT EXISTS idx_classified_events_created_at ON classified_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_classified_events_symbol ON classified_events (symbol);
CREATE INDEX IF NOT EXISTS idx_model_runs_created_at ON model_runs (created_at DESC);
