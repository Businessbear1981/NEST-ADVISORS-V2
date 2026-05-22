"""Webhooks — inbound webhook receiver + signal persistence.

Inbound webhooks are normalized into SignalEvents and persisted to Supabase.
Also maintains in-memory log and NestChain audit trail for backward compat.
"""
from flask import Blueprint, request
from services.core import ok, err, ts
from blockchain.nest_chain import chain

webhooks_bp = Blueprint("webhooks", __name__)

_webhook_log = []


@webhooks_bp.post("/inbound")
def inbound():
    data = request.get_json(force=True)
    source = data.get("source", "unknown")
    event_type = data.get("event_type", "generic")
    payload = data.get("payload", {})

    entry = {
        "source": source,
        "event_type": event_type,
        "payload": payload,
        "received_at": ts(),
    }

    # Persist as signal event in Supabase
    try:
        from services import signal_service
        signal_event = signal_service.normalize_webhook(source, event_type, payload)
        persisted = signal_service.ingest(signal_event)
        if persisted:
            entry["signal_event_id"] = persisted.get("id")
            entry["persisted"] = True
        else:
            entry["persisted"] = False
    except Exception:
        entry["persisted"] = False

    _webhook_log.append(entry)
    chain.record_event(f"webhook_{source}", event_type, payload)
    return ok(entry)


@webhooks_bp.get("/log")
def webhook_log():
    limit = request.args.get("limit", 50, type=int)
    return ok(_webhook_log[-limit:])
