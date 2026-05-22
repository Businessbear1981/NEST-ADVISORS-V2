-- ============================================================
-- NEST Advisors — Signal Intelligence Migration 002
-- PostgreSQL 15+ (Supabase)
--
-- Unified signal event intake + VectorAgent scoring snapshots.
-- Replaces the narrow market_signals table (which remains empty
-- and untouched for backward compat).
-- ============================================================

-- ============================================================
-- 1. signal_events — unified signal intake
-- ============================================================
CREATE TABLE signal_events (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Classification
  signal_type     text NOT NULL,
  category        text NOT NULL,
  source          text NOT NULL,

  -- Numeric value (nullable — not all signals have one)
  value           numeric(16,6),
  direction       text CHECK (direction IN ('bullish','bearish','neutral','positive','negative')),
  confidence      numeric(4,2) CHECK (confidence BETWEEN 0 AND 1),
  severity        text NOT NULL DEFAULT 'info'
                    CHECK (severity IN ('info','low','medium','high','critical')),

  -- Geographic (nullable)
  state           text,
  county          text,
  market          text,

  -- Entity / Deal linking (nullable)
  deal_id         uuid REFERENCES deals(id) ON DELETE SET NULL,
  entity_name     text,

  -- Lifecycle
  status          text NOT NULL DEFAULT 'new'
                    CHECK (status IN ('new','reviewed','actionable','acted_on','archived','dismissed')),

  -- Deduplication — external reference ID (EDGAR accession, FRED series+date, etc.)
  source_ref      text,

  -- Flexible payload for type-specific structured data
  payload         jsonb DEFAULT '{}'::jsonb,

  -- Timestamps
  captured_at     timestamptz NOT NULL DEFAULT NOW(),
  processed_at    timestamptz,
  created_at      timestamptz NOT NULL DEFAULT NOW(),
  updated_at      timestamptz NOT NULL DEFAULT NOW()
);

ALTER TABLE signal_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY signal_events_admin ON signal_events FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_signal_events_type        ON signal_events (signal_type);
CREATE INDEX idx_signal_events_category    ON signal_events (category);
CREATE INDEX idx_signal_events_status      ON signal_events (status);
CREATE INDEX idx_signal_events_deal_id     ON signal_events (deal_id);
CREATE INDEX idx_signal_events_captured_at ON signal_events (captured_at);
CREATE INDEX idx_signal_events_geo         ON signal_events (state, county);
CREATE UNIQUE INDEX idx_signal_events_dedup ON signal_events (source, source_ref)
  WHERE source_ref IS NOT NULL;

CREATE TRIGGER trg_signal_events_updated_at BEFORE UPDATE ON signal_events
  FOR EACH ROW EXECUTE FUNCTION nest_set_updated_at();


-- ============================================================
-- 2. vector_snapshots — VectorAgent scoring runs
-- ============================================================
CREATE TABLE vector_snapshots (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id           uuid REFERENCES deals(id) ON DELETE SET NULL,
  composite_score   numeric(5,2) NOT NULL CHECK (composite_score BETWEEN 0 AND 100),
  recommendation    text NOT NULL,
  signals_used      jsonb NOT NULL,
  put_risk_level    text,
  reasoning         jsonb,
  estimated_savings numeric(16,2),
  created_at        timestamptz NOT NULL DEFAULT NOW()
);

ALTER TABLE vector_snapshots ENABLE ROW LEVEL SECURITY;
CREATE POLICY vector_snapshots_admin ON vector_snapshots FOR ALL USING (true) WITH CHECK (true);

CREATE INDEX idx_vector_snapshots_deal_id    ON vector_snapshots (deal_id);
CREATE INDEX idx_vector_snapshots_created_at ON vector_snapshots (created_at);
CREATE INDEX idx_vector_snapshots_score      ON vector_snapshots (composite_score);
