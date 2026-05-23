"""Signal Intelligence routes — unified signal query + FRED/EDGAR poll triggers.

GET   /api/signals/query              — query persisted signals with filters + cursor
GET   /api/signals/latest             — most recent signal event
GET   /api/signals/stats              — signal counts by category/type
GET   /api/signals/related            — related signals for correlation panel
PATCH /api/signals/<id>/status        — update signal lifecycle status
POST  /api/signals/poll/fred          — pull live FRED rates, normalize, persist, score
POST  /api/signals/poll/edgar         — pull EDGAR filings, normalize, persist
GET   /api/signals/alerts             — query signal alerts (cluster, escalation, convergence)
PATCH /api/signals/alerts/<id>/status — acknowledge/resolve signal alerts
GET   /api/signals/vector/latest      — latest VectorAgent snapshot
GET   /api/signals/vector/history     — scoring history
"""
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timedelta
from services.auth import require_auth

signals_bp = Blueprint("signals", __name__)

VALID_STATUSES = ("new", "reviewed", "actionable", "acted_on", "dismissed")


def _ts():
    return datetime.utcnow().isoformat()


def _ok(data, code=200):
    return jsonify({"success": True, "data": data, "error": None, "timestamp": _ts()}), code


def _err(msg, code=400):
    return jsonify({"success": False, "data": None, "error": msg, "timestamp": _ts()}), code


@signals_bp.route("/query", methods=["GET"])
def query_signals():
    """Query persisted signal events with optional filters.
    Supports cursor-based polling via ?since_ts=ISO8601 — returns only signals
    with captured_at > since_ts."""
    from services import signal_service

    since_ts = request.args.get("since_ts")

    results = signal_service.query(
        category=request.args.get("category"),
        signal_type=request.args.get("signal_type"),
        source=request.args.get("source"),
        status=request.args.get("status"),
        state=request.args.get("state"),
        deal_id=request.args.get("deal_id"),
        since_ts=since_ts,
        limit=request.args.get("limit", 100, type=int),
    )
    return _ok({"signals": results, "count": len(results)})


@signals_bp.route("/latest", methods=["GET"])
def latest_signal():
    """Get the most recent signal event."""
    from services.database import db

    signal_type = request.args.get("signal_type")
    source = request.args.get("source")
    result = db.get_latest_signal(signal_type=signal_type, source=source)
    if result:
        return _ok(result)
    return _err("No signals found", 404)


@signals_bp.route("/stats", methods=["GET"])
def signal_stats():
    """Aggregate counts of signals by category and type."""
    from services.database import db

    all_signals = db.query_signals(limit=1000)
    by_category = {}
    by_type = {}
    by_source = {}
    for s in all_signals:
        cat = s.get("category", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1
        st = s.get("signal_type", "unknown")
        by_type[st] = by_type.get(st, 0) + 1
        src = s.get("source", "unknown")
        by_source[src] = by_source.get(src, 0) + 1

    return _ok({
        "total": len(all_signals),
        "by_category": by_category,
        "by_type": by_type,
        "by_source": by_source,
    })


@signals_bp.route("/related", methods=["GET"])
def related_signals():
    """Find signals correlated to a given signal — same entity, market, or state
    within a 30-day window. Used by the Correlation Panel."""
    from services.database import db

    signal_id = request.args.get("signal_id")
    entity = request.args.get("entity")
    market = request.args.get("market")
    state = request.args.get("state")
    exclude_id = request.args.get("exclude_id", signal_id)

    if not any([entity, market, state]):
        return _err("At least one of entity, market, or state is required")

    cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
    all_related = []
    seen_ids = {exclude_id} if exclude_id else set()

    for field, value in [("entity_name", entity), ("market", market), ("state", state)]:
        if not value:
            continue
        params = {
            field: f"eq.{value}",
            "captured_at": f"gte.{cutoff}",
            "order": "captured_at.desc",
            "limit": "10",
        }
        rows = db.select("signal_events", params) or []
        if isinstance(rows, list):
            for r in rows:
                rid = r.get("id")
                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    r["_match_field"] = field
                    all_related.append(r)

    all_related.sort(key=lambda s: s.get("captured_at", ""), reverse=True)

    return _ok({
        "related": all_related[:15],
        "count": len(all_related),
        "query": {"entity": entity, "market": market, "state": state, "window_days": 30},
    })


@signals_bp.route("/<signal_id>/status", methods=["PATCH"])
def update_signal_status(signal_id):
    """Update signal lifecycle status: new → reviewed → actionable → acted_on → dismissed."""
    from services.database import db

    body = request.get_json(silent=True) or {}
    new_status = body.get("status")

    if new_status not in VALID_STATUSES:
        return _err(f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}")

    result = db.update(
        "signal_events",
        {"id": f"eq.{signal_id}"},
        {"status": new_status},
    )

    if not result:
        return _err("Signal not found or update failed", 404)

    updated = result[0] if isinstance(result, list) and result else result
    return _ok(updated)


@signals_bp.route("/poll/fred", methods=["POST"])
def poll_fred():
    """Pull live FRED rates, normalize into SignalEvents, persist to Supabase,
    run VectorAgent scoring, and save the snapshot."""
    from services import signal_service
    from services.data_connectors import FREDPlugin

    fred = FREDPlugin()
    snapshot = fred.get_bond_desk_snapshot()
    if not snapshot or not snapshot.get("success"):
        return _err("FRED data unavailable", 503)

    events = signal_service.normalize_fred_snapshot(snapshot)
    if not events:
        return _err("No signals produced from FRED data", 422)

    persisted = signal_service.ingest_batch(events)

    # Run VectorAgent scoring against latest rates
    vector_result = None
    try:
        vector_agent = current_app.config.get("VECTOR")
        if vector_agent:
            rates = snapshot.get("rates", {})
            vector_signals = {
                "treasury_10yr": rates.get("treasury_10yr", 4.35),
                "treasury_change_bps": rates.get("treasury_change_bps", 0),
                "sofr": rates.get("sofr", 5.31),
                "credit_spread_ig": round(rates.get("ig_spread", 1.12) * 100),
                "credit_spread_hy": round(rates.get("hy_spread", 3.45) * 100),
                "vix": rates.get("vix", 18.5),
                "refi_market_access": 72,
                "deal_dscr": 1.85,
                "deal_occupancy": 93,
                "covenant_status": "compliant",
                "months_since_origination": 14,
                "hft_return_ytd": 21.3,
                "b_tranche_coverage": 1.15,
                "lc_capacity_ratio": 0.85,
            }
            score = vector_agent.score_signals(vector_signals)
            rec = vector_agent.recommend(vector_signals, {
                "bond_face_value": 231_000_000,
                "current_coupon_pct": 7.0,
                "years_to_maturity": 10,
            })
            put_risk = vector_agent.check_put_risk(vector_signals, {})

            vector_snapshot = signal_service.save_vector_snapshot(
                composite_score=score,
                recommendation=rec.get("recommendation", "MONITOR").lower(),
                signals_used=vector_signals,
                put_risk_level=put_risk.get("put_risk_level"),
                reasoning=rec.get("reasoning"),
                estimated_savings=rec.get("estimated_savings_usd"),
            )
            vector_result = {
                "composite_score": score,
                "recommendation": rec.get("recommendation"),
                "put_risk_level": put_risk.get("put_risk_level"),
                "reasoning": rec.get("reasoning"),
                "estimated_savings_usd": rec.get("estimated_savings_usd"),
                "snapshot_id": vector_snapshot.get("id") if vector_snapshot else None,
            }
    except Exception as e:
        vector_result = {"error": str(e)}

    return _ok({
        "fred_source": snapshot.get("source"),
        "signals_ingested": len(persisted),
        "signal_ids": [s.get("id") for s in persisted],
        "vector": vector_result,
    }, 201)


@signals_bp.route("/poll/edgar", methods=["POST"])
def poll_edgar():
    """Pull recent EDGAR filings matching NEST target criteria,
    normalize into SignalEvents, and persist to Supabase."""
    from services import signal_service
    from services.edgar_connector import poll_recent_filings

    days_back = request.args.get("days", 7, type=int)
    limit = request.args.get("limit", 40, type=int)

    try:
        filings = poll_recent_filings(days_back=days_back, limit=limit)
    except Exception as e:
        return _err(f"EDGAR API unavailable: {str(e)}", 503)

    if not filings:
        return _ok({"filings_found": 0, "signals_ingested": 0, "signal_ids": []})

    events = signal_service.normalize_edgar_batch(filings)
    if not events:
        return _ok({"filings_found": len(filings), "signals_ingested": 0, "signal_ids": []})

    persisted = signal_service.ingest_batch(events)

    return _ok({
        "filings_found": len(filings),
        "signals_ingested": len(persisted),
        "signal_ids": [s.get("id") for s in persisted],
        "filings_summary": [
            {
                "entity": f.get("entity_name", ""),
                "form_type": f.get("form_type", ""),
                "state": f.get("state"),
                "amount": f.get("offering_amount"),
            }
            for f in filings[:10]
        ],
    }, 201)


@signals_bp.route("/alerts", methods=["GET"])
def query_alerts():
    """Query signal alerts with optional status filter."""
    from services.database import db

    status = request.args.get("status")
    alert_type = request.args.get("alert_type")
    limit = request.args.get("limit", 50, type=int)

    params = {}
    if status:
        params["status"] = f"eq.{status}"
    if alert_type:
        params["alert_type"] = f"eq.{alert_type}"

    alerts = db.query_signal_alerts(params, limit=limit)
    return _ok({"alerts": alerts, "count": len(alerts)})


@signals_bp.route("/alerts/<alert_id>/status", methods=["PATCH"])
def update_alert_status(alert_id):
    """Update alert status: new → acknowledged → resolved."""
    from services.database import db

    VALID_ALERT_STATUSES = ("new", "acknowledged", "resolved")
    body = request.get_json(silent=True) or {}
    new_status = body.get("status")

    if new_status not in VALID_ALERT_STATUSES:
        return _err(f"Invalid status. Must be one of: {', '.join(VALID_ALERT_STATUSES)}")

    update_data = {"status": new_status}
    if new_status == "resolved":
        update_data["resolved_at"] = datetime.utcnow().isoformat()

    result = db.update_signal_alert(alert_id, update_data)

    if not result:
        return _err("Alert not found or update failed", 404)

    updated = result[0] if isinstance(result, list) and result else result
    return _ok(updated)


@signals_bp.route("/vector/latest", methods=["GET"])
def vector_latest():
    """Get the most recent VectorAgent scoring snapshot."""
    from services.database import db

    deal_id = request.args.get("deal_id")
    result = db.get_latest_vector_snapshot(deal_id=deal_id)
    if result:
        return _ok(result)
    return _err("No vector snapshots found", 404)


@signals_bp.route("/vector/history", methods=["GET"])
def vector_history():
    """VectorAgent scoring history."""
    from services.database import db

    limit = request.args.get("limit", 50, type=int)
    params = {}
    deal_id = request.args.get("deal_id")
    if deal_id:
        params["deal_id"] = f"eq.{deal_id}"
    results = db.query_vector_snapshots(params, limit=limit)
    return _ok({"snapshots": results, "count": len(results)})
