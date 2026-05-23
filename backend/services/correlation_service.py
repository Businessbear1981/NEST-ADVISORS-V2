"""
NEST Correlation Engine — detects signal clusters, severity escalations,
and entity convergences by querying recent signal_events after each ingestion.

No LLM required — pure pattern matching on entity_name, market, and state
within time windows. LLM narrative can be layered on top once API keys arrive.
"""
import logging
from datetime import datetime, timedelta

from services.database import db

log = logging.getLogger(__name__)

CLUSTER_WINDOW_DAYS = 30
ENTITY_WINDOW_DAYS = 7
CLUSTER_THRESHOLD = 3


def check_correlations(signal: dict) -> list[dict]:
    """Run all correlation checks against a newly ingested signal.

    Returns a list of created alert dicts (may be empty).
    """
    alerts_created = []

    cluster = _check_cluster(signal)
    if cluster:
        alerts_created.append(cluster)

    escalation = _check_severity_escalation(signal)
    if escalation:
        alerts_created.append(escalation)

    convergence = _check_entity_convergence(signal)
    if convergence:
        alerts_created.append(convergence)

    return alerts_created


def _check_cluster(signal: dict) -> dict | None:
    """If 3+ signals share the same state or market in the last 30 days,
    create a cluster_detected alert."""
    state = signal.get("state")
    market = signal.get("market")

    if not state and not market:
        return None

    cutoff = (datetime.utcnow() - timedelta(days=CLUSTER_WINDOW_DAYS)).isoformat()
    related_ids: set[str] = set()
    related_signals: list[dict] = []

    for field, value in [("state", state), ("market", market)]:
        if not value:
            continue
        rows = db.select("signal_events", {
            field: f"eq.{value}",
            "captured_at": f"gte.{cutoff}",
            "order": "captured_at.desc",
            "limit": "20",
        })
        if isinstance(rows, list):
            for r in rows:
                rid = r.get("id")
                if rid and rid not in related_ids:
                    related_ids.add(rid)
                    related_signals.append(r)

    if len(related_signals) < CLUSTER_THRESHOLD:
        return None

    location = state or market or "Unknown"
    existing = _find_existing_alert(
        alert_type="cluster_detected",
        state=state,
        market=market,
    )
    if existing:
        _update_alert_signals(existing["id"], list(related_ids))
        return None

    highest_sev = _highest_severity(related_signals)
    alert_data = {
        "alert_type": "cluster_detected",
        "title": f"Cluster detected: {location} — {len(related_signals)} converging signals",
        "description": f"{len(related_signals)} signals converging in {location} within {CLUSTER_WINDOW_DAYS}-day window.",
        "severity": highest_sev,
        "signal_ids": list(related_ids),
        "entity_name": signal.get("entity_name"),
        "market": market,
        "state": state,
        "status": "new",
    }
    result = db.insert("signal_alerts", alert_data)
    if result:
        persisted = result[0] if isinstance(result, list) else result
        log.info("Cluster alert created: %s (%d signals)", location, len(related_signals))
        return persisted

    return None


def _check_severity_escalation(signal: dict) -> dict | None:
    """If a high/critical signal matches existing signals in the same region,
    create a severity_escalation alert."""
    severity = signal.get("severity", "info")
    if severity not in ("high", "critical"):
        return None

    state = signal.get("state")
    entity = signal.get("entity_name")
    if not state and not entity:
        return None

    cutoff = (datetime.utcnow() - timedelta(days=CLUSTER_WINDOW_DAYS)).isoformat()
    match_field = "entity_name" if entity else "state"
    match_value = entity or state

    rows = db.select("signal_events", {
        match_field: f"eq.{match_value}",
        "captured_at": f"gte.{cutoff}",
        "order": "captured_at.desc",
        "limit": "10",
    })

    if not isinstance(rows, list) or len(rows) < 2:
        return None

    signal_ids = [r.get("id") for r in rows if r.get("id")]

    existing = _find_existing_alert(
        alert_type="severity_escalation",
        entity_name=entity,
        state=state,
    )
    if existing:
        return None

    alert_data = {
        "alert_type": "severity_escalation",
        "title": f"Severity escalation: {match_value} — {severity} signal with {len(rows)} related",
        "description": f"New {severity}-severity signal for {match_value} correlates with {len(rows)} existing signals.",
        "severity": severity,
        "signal_ids": signal_ids,
        "entity_name": entity,
        "state": state,
        "status": "new",
    }
    result = db.insert("signal_alerts", alert_data)
    if result:
        persisted = result[0] if isinstance(result, list) else result
        log.info("Severity escalation alert: %s (%s)", match_value, severity)
        return persisted

    return None


def _check_entity_convergence(signal: dict) -> dict | None:
    """If 2+ signals share the same entity_name within 7 days,
    create an entity_convergence alert."""
    entity = signal.get("entity_name")
    if not entity:
        return None

    cutoff = (datetime.utcnow() - timedelta(days=ENTITY_WINDOW_DAYS)).isoformat()
    rows = db.select("signal_events", {
        "entity_name": f"eq.{entity}",
        "captured_at": f"gte.{cutoff}",
        "order": "captured_at.desc",
        "limit": "10",
    })

    if not isinstance(rows, list) or len(rows) < 2:
        return None

    existing = _find_existing_alert(
        alert_type="entity_convergence",
        entity_name=entity,
    )
    if existing:
        _update_alert_signals(existing["id"], [r.get("id") for r in rows if r.get("id")])
        return None

    signal_ids = [r.get("id") for r in rows if r.get("id")]
    alert_data = {
        "alert_type": "entity_convergence",
        "title": f"Entity convergence: {entity} — {len(rows)} signals in {ENTITY_WINDOW_DAYS} days",
        "description": f"Multiple signals for {entity} detected within {ENTITY_WINDOW_DAYS}-day window.",
        "severity": _highest_severity(rows),
        "signal_ids": signal_ids,
        "entity_name": entity,
        "state": signal.get("state"),
        "market": signal.get("market"),
        "status": "new",
    }
    result = db.insert("signal_alerts", alert_data)
    if result:
        persisted = result[0] if isinstance(result, list) else result
        log.info("Entity convergence alert: %s (%d signals)", entity, len(rows))
        return persisted

    return None


def _find_existing_alert(
    alert_type: str,
    entity_name: str | None = None,
    state: str | None = None,
    market: str | None = None,
) -> dict | None:
    """Check if an unresolved alert of the same type/scope already exists."""
    params: dict = {
        "alert_type": f"eq.{alert_type}",
        "status": f"neq.resolved",
        "order": "created_at.desc",
        "limit": "1",
    }
    if entity_name:
        params["entity_name"] = f"eq.{entity_name}"
    if state:
        params["state"] = f"eq.{state}"
    if market:
        params["market"] = f"eq.{market}"

    rows = db.select("signal_alerts", params)
    if isinstance(rows, list) and rows:
        return rows[0]
    return None


def _update_alert_signals(alert_id: str, signal_ids: list[str]) -> None:
    """Update an existing alert's signal_ids array."""
    db.update(
        "signal_alerts",
        {"id": f"eq.{alert_id}"},
        {"signal_ids": signal_ids, "updated_at": datetime.utcnow().isoformat()},
    )


def _highest_severity(signals: list[dict]) -> str:
    """Return the highest severity found in a list of signals."""
    order = ["critical", "high", "medium", "low", "info"]
    for sev in order:
        if any(s.get("severity") == sev for s in signals):
            return sev
    return "medium"
