"""Signal Intelligence routes — unified signal query + FRED poll trigger.

GET  /api/signals/query       — query persisted signals with filters
GET  /api/signals/latest      — most recent signal event
GET  /api/signals/stats       — signal counts by category/type
POST /api/signals/poll/fred   — pull live FRED rates, normalize, persist, score
GET  /api/signals/vector/latest  — latest VectorAgent snapshot
GET  /api/signals/vector/history — scoring history
"""
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
from services.auth import require_auth

signals_bp = Blueprint("signals", __name__)


def _ts():
    return datetime.utcnow().isoformat()


def _ok(data, code=200):
    return jsonify({"success": True, "data": data, "error": None, "timestamp": _ts()}), code


def _err(msg, code=400):
    return jsonify({"success": False, "data": None, "error": msg, "timestamp": _ts()}), code


@signals_bp.route("/query", methods=["GET"])
def query_signals():
    """Query persisted signal events with optional filters."""
    from services import signal_service

    results = signal_service.query(
        category=request.args.get("category"),
        signal_type=request.args.get("signal_type"),
        source=request.args.get("source"),
        status=request.args.get("status"),
        state=request.args.get("state"),
        deal_id=request.args.get("deal_id"),
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
