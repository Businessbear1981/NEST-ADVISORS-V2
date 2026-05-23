"""
NEST Signal Intelligence Service — unified signal ingestion, normalization,
deduplication, and VectorAgent scoring.

All signal data flows through this module regardless of source (FRED, EDGAR,
webhooks, manual entry). Persists to Supabase signal_events table.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from services.database import db

log = logging.getLogger(__name__)

# Valid enum values matching DB CHECK constraints
SIGNAL_TYPES = frozenset({
    "rate_change", "yield_curve", "market_snapshot",
    "permit_filed", "ucc_filing", "land_transfer",
    "edgar_filing", "emma_filing", "corporate_action",
    "construction_activity", "developer_activity",
    "webhook_event", "manual",
})

CATEGORIES = frozenset({
    "macro_market", "deal_sourcing", "regulatory",
    "property", "entity",
})

DIRECTIONS = frozenset({"bullish", "bearish", "neutral", "positive", "negative"})
SEVERITIES = frozenset({"info", "low", "medium", "high", "critical"})
STATUSES = frozenset({"new", "reviewed", "actionable", "acted_on", "archived", "dismissed"})


@dataclass
class SignalEvent:
    """Normalized signal event ready for persistence."""
    signal_type: str
    category: str
    source: str
    value: Optional[float] = None
    direction: Optional[str] = None
    confidence: Optional[float] = None
    severity: str = "info"
    state: Optional[str] = None
    county: Optional[str] = None
    market: Optional[str] = None
    deal_id: Optional[str] = None
    entity_name: Optional[str] = None
    status: str = "new"
    source_ref: Optional[str] = None
    payload: dict = field(default_factory=dict)
    captured_at: Optional[str] = None

    def to_row(self) -> dict:
        """Convert to a dict suitable for Supabase insert."""
        row = {}
        for k, v in asdict(self).items():
            if v is not None:
                row[k] = v
        if "captured_at" not in row:
            row["captured_at"] = datetime.utcnow().isoformat()
        return row


def ingest(event: SignalEvent) -> Optional[dict]:
    """Ingest a single signal event into Supabase.
    Returns the persisted row or None on failure."""
    row = event.to_row()

    if event.source_ref:
        result = db.upsert_signal_event(row)
    else:
        result = db.save_signal_event(row)

    if result:
        persisted = result[0] if isinstance(result, list) else result
        log.info("Signal ingested: %s/%s [%s]", event.source, event.signal_type, event.source_ref or "no-ref")
        return persisted

    log.warning("Signal ingestion failed: %s/%s", event.source, event.signal_type)
    return None


def ingest_batch(events: list[SignalEvent]) -> list[dict]:
    """Ingest multiple signal events. Returns list of persisted rows."""
    if not events:
        return []

    has_refs = [e for e in events if e.source_ref]
    no_refs = [e for e in events if not e.source_ref]

    results = []

    if no_refs:
        rows = [e.to_row() for e in no_refs]
        batch_result = db.save_signal_events_batch(rows)
        if batch_result:
            results.extend(batch_result if isinstance(batch_result, list) else [batch_result])

    for event in has_refs:
        r = ingest(event)
        if r:
            results.append(r)

    log.info("Batch ingested %d/%d signals", len(results), len(events))
    return results


def query(category: str = None, signal_type: str = None, source: str = None,
          status: str = None, state: str = None, deal_id: str = None,
          since_ts: str = None, limit: int = 100) -> list[dict]:
    """Query persisted signals with optional filters.
    since_ts: ISO8601 timestamp — only return signals captured after this time."""
    params = {}
    if category:
        params["category"] = f"eq.{category}"
    if signal_type:
        params["signal_type"] = f"eq.{signal_type}"
    if source:
        params["source"] = f"eq.{source}"
    if status:
        params["status"] = f"eq.{status}"
    if state:
        params["state"] = f"eq.{state}"
    if deal_id:
        params["deal_id"] = f"eq.{deal_id}"
    if since_ts:
        params["captured_at"] = f"gt.{since_ts}"
    return db.query_signals(params, limit=limit)


def save_vector_snapshot(
    composite_score: float,
    recommendation: str,
    signals_used: dict,
    deal_id: str = None,
    put_risk_level: str = None,
    reasoning: list = None,
    estimated_savings: float = None,
) -> Optional[dict]:
    """Persist a VectorAgent scoring run."""
    row = {
        "composite_score": composite_score,
        "recommendation": recommendation,
        "signals_used": signals_used,
    }
    if deal_id:
        row["deal_id"] = deal_id
    if put_risk_level:
        row["put_risk_level"] = put_risk_level
    if reasoning:
        row["reasoning"] = reasoning
    if estimated_savings is not None:
        row["estimated_savings"] = estimated_savings

    result = db.save_vector_snapshot(row)
    if result:
        persisted = result[0] if isinstance(result, list) else result
        log.info("Vector snapshot saved: score=%.1f rec=%s", composite_score, recommendation)
        return persisted
    return None


# ---------------------------------------------------------------------------
# FRED signal normalizer — converts raw FRED data into SignalEvents
# ---------------------------------------------------------------------------

FRED_SERIES_MAP = {
    "treasury_10yr": {"signal_type": "rate_change", "source_ref_prefix": "DGS10"},
    "treasury_5yr": {"signal_type": "rate_change", "source_ref_prefix": "DGS5"},
    "treasury_2yr": {"signal_type": "rate_change", "source_ref_prefix": "DGS2"},
    "treasury_30yr": {"signal_type": "rate_change", "source_ref_prefix": "DGS30"},
    "sofr": {"signal_type": "rate_change", "source_ref_prefix": "SOFR"},
    "ig_spread": {"signal_type": "rate_change", "source_ref_prefix": "BAMLC0A4CBBBEY"},
    "hy_spread": {"signal_type": "rate_change", "source_ref_prefix": "BAMLH0A0HYM2EY"},
    "fed_funds": {"signal_type": "rate_change", "source_ref_prefix": "FEDFUNDS"},
    "mortgage_30yr": {"signal_type": "rate_change", "source_ref_prefix": "MORTGAGE30US"},
}


def normalize_fred_snapshot(snapshot: dict) -> list[SignalEvent]:
    """Convert a FREDPlugin.get_bond_desk_snapshot() result into SignalEvents."""
    if not snapshot or not snapshot.get("success"):
        return []

    rates = snapshot.get("rates", {})
    source_tag = snapshot.get("source", "fred")
    ts = snapshot.get("timestamp", datetime.utcnow().isoformat())
    date_tag = datetime.utcnow().strftime("%Y-%m-%d")

    events = []
    for rate_key, meta in FRED_SERIES_MAP.items():
        val = rates.get(rate_key)
        if val is None:
            continue

        direction = None
        if rate_key in ("ig_spread", "hy_spread"):
            direction = "bearish" if val > 2.0 else "bullish" if val < 1.0 else "neutral"
        elif "treasury" in rate_key or rate_key == "sofr":
            pass

        events.append(SignalEvent(
            signal_type=meta["signal_type"],
            category="macro_market",
            source="fred",
            value=float(val),
            direction=direction,
            confidence=0.95 if source_tag == "live" else 0.5,
            severity="info",
            source_ref=f"{meta['source_ref_prefix']}_{date_tag}",
            payload={"rate_key": rate_key, "fred_source": source_tag},
            captured_at=ts,
        ))

    curve_spread = rates.get("yield_curve_spread_bps")
    if curve_spread is not None:
        inverted = rates.get("curve_inverted", False)
        events.append(SignalEvent(
            signal_type="yield_curve",
            category="macro_market",
            source="fred",
            value=float(curve_spread),
            direction="bearish" if inverted else "bullish",
            confidence=0.95 if source_tag == "live" else 0.5,
            severity="high" if inverted else "info",
            source_ref=f"YIELD_CURVE_{date_tag}",
            payload={
                "spread_bps": curve_spread,
                "inverted": inverted,
                "fred_source": source_tag,
            },
            captured_at=ts,
        ))

    return events


def normalize_webhook(source: str, event_type: str, payload: dict) -> SignalEvent:
    """Convert an inbound webhook into a SignalEvent."""
    category_map = {
        "permit": "deal_sourcing",
        "ucc": "deal_sourcing",
        "land_transfer": "deal_sourcing",
        "edgar": "regulatory",
        "emma": "regulatory",
        "market": "macro_market",
        "property": "property",
    }

    type_map = {
        "permit": "permit_filed",
        "ucc": "ucc_filing",
        "land_transfer": "land_transfer",
        "edgar": "edgar_filing",
        "emma": "emma_filing",
    }

    category = category_map.get(event_type, "entity")
    signal_type = type_map.get(event_type, "webhook_event")

    return SignalEvent(
        signal_type=signal_type,
        category=category,
        source=f"webhook_{source}",
        value=payload.get("amount") or payload.get("value"),
        direction=payload.get("direction"),
        confidence=payload.get("confidence"),
        severity=payload.get("severity", "info"),
        state=payload.get("state"),
        county=payload.get("county"),
        market=payload.get("market"),
        deal_id=payload.get("deal_id"),
        entity_name=payload.get("entity") or payload.get("entity_name"),
        source_ref=payload.get("ref_id") or payload.get("source_ref"),
        payload=payload,
    )
