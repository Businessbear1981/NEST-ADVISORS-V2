"""Market signals routes — ingest data, Vector scoring, FRED rates.

Persists all ingested signals to Supabase via signal_service.
Uses real VectorAgent for composite scoring (replaces placeholder).
Falls back to in-memory when Supabase is unavailable.
"""
import threading
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
from services.auth import require_auth

market_bp = Blueprint("market", __name__)

_lock = threading.RLock()
_signals = []  # in-memory fallback


def _ts():
    return datetime.utcnow().isoformat()


def _ok(data, code=200):
    return jsonify({"success": True, "data": data, "error": None, "timestamp": _ts()}), code


def _err(msg, code=400):
    return jsonify({"success": False, "data": None, "error": msg, "timestamp": _ts()}), code


def _get_vector_agent():
    try:
        return current_app.config.get("VECTOR")
    except RuntimeError:
        from agents.vector_agent import vector
        return vector


def _get_fred_plugin():
    try:
        from services.data_connectors import FREDPlugin
        return FREDPlugin()
    except Exception:
        return None


DEFAULT_SIGNALS = {
    "treasury_10yr_pct": 4.25,
    "treasury_10yr_change_bps": -5,
    "sofr_pct": 4.30,
    "credit_spread_ig_bps": 125,
    "credit_spread_hy_bps": 375,
    "tlt_price": 92.50,
    "vix": 18.5,
    "refi_market_access": "open_favorable",
}


@market_bp.route("/signals", methods=["POST"])
def ingest_signals():
    body = request.get_json() or {}
    signals = body.get("signals", DEFAULT_SIGNALS)

    vector_agent = _get_vector_agent()
    vector_signals = _translate_to_vector_format(signals)
    score = vector_agent.score_signals(vector_signals) if vector_agent else 50
    recommendation = vector_agent.recommend(vector_signals, {}) if vector_agent else {}
    rec_label = recommendation.get("recommendation", "monitor").lower() if isinstance(recommendation, dict) else "monitor"

    entry = {
        "captured_at": _ts(),
        "signals": signals,
        "vector_score": score,
        "vector_recommendation": rec_label,
        "apex_short_active": False,
        "apex_position": None,
    }

    # Persist to Supabase via signal_service
    try:
        from services import signal_service
        from services.database import db

        market_event = signal_service.SignalEvent(
            signal_type="market_snapshot",
            category="macro_market",
            source="api_ingest",
            value=score,
            direction="bullish" if score >= 65 else "bearish" if score < 30 else "neutral",
            confidence=0.8,
            severity="info",
            source_ref=f"market_snapshot_{datetime.utcnow().strftime('%Y-%m-%dT%H')}",
            payload=signals,
        )
        persisted = signal_service.ingest(market_event)
        if persisted:
            entry["id"] = persisted.get("id")
            entry["persisted"] = True

        signal_service.save_vector_snapshot(
            composite_score=score,
            recommendation=rec_label,
            signals_used=vector_signals,
            put_risk_level=recommendation.get("put_risk", {}).get("put_risk_level") if isinstance(recommendation, dict) else None,
            reasoning=recommendation.get("reasoning") if isinstance(recommendation, dict) else None,
            estimated_savings=recommendation.get("estimated_savings_usd") if isinstance(recommendation, dict) else None,
        )
    except Exception:
        entry["persisted"] = False

    with _lock:
        _signals.append(entry)
        if len(_signals) > 1000:
            _signals.pop(0)

    return _ok(entry, 201)


@market_bp.route("/signals/latest", methods=["GET"])
def latest_signals():
    # Try Supabase first
    try:
        from services.database import db
        snapshot = db.get_latest_vector_snapshot()
        if snapshot:
            return _ok({
                "source": "supabase",
                "vector_snapshot": snapshot,
                "captured_at": snapshot.get("created_at"),
                "vector_score": snapshot.get("composite_score"),
                "vector_recommendation": snapshot.get("recommendation"),
            })
    except Exception:
        pass

    with _lock:
        if _signals:
            return _ok(_signals[-1])

    # Compute on-the-fly from FRED + defaults
    signals_to_use = dict(DEFAULT_SIGNALS)
    fred = _get_fred_plugin()
    if fred:
        try:
            snap = fred.get_bond_desk_snapshot()
            if snap.get("success"):
                r = snap["rates"]
                signals_to_use["treasury_10yr_pct"] = r.get("treasury_10yr", 4.25)
                signals_to_use["sofr_pct"] = r.get("sofr", 4.30)
                signals_to_use["credit_spread_ig_bps"] = round(r.get("ig_spread", 1.25) * 100)
                signals_to_use["credit_spread_hy_bps"] = round(r.get("hy_spread", 3.75) * 100)
        except Exception:
            pass

    vector_agent = _get_vector_agent()
    vector_signals = _translate_to_vector_format(signals_to_use)
    score = vector_agent.score_signals(vector_signals) if vector_agent else 50
    rec = vector_agent.recommend(vector_signals, {}) if vector_agent else {}
    rec_label = rec.get("recommendation", "monitor").lower() if isinstance(rec, dict) else "monitor"

    return _ok({
        "source": "computed",
        "captured_at": _ts(),
        "signals": signals_to_use,
        "vector_score": score,
        "vector_recommendation": rec_label,
        "apex_short_active": False,
        "apex_position": None,
    })


def _translate_to_vector_format(signals: dict) -> dict:
    """Translate market route signal keys to VectorAgent signal keys."""
    return {
        "treasury_10yr": signals.get("treasury_10yr_pct", signals.get("treasury_10yr", 4.25)),
        "treasury_change_bps": signals.get("treasury_10yr_change_bps", signals.get("treasury_change_bps", 0)),
        "sofr": signals.get("sofr_pct", signals.get("sofr", 4.30)),
        "credit_spread_ig": signals.get("credit_spread_ig_bps", signals.get("credit_spread_ig", 125)),
        "credit_spread_hy": signals.get("credit_spread_hy_bps", signals.get("credit_spread_hy", 375)),
        "vix": signals.get("vix", 18.5),
        "refi_market_access": _parse_refi_access(signals.get("refi_market_access", 50)),
        "deal_dscr": signals.get("deal_dscr", 1.5),
        "deal_occupancy": signals.get("deal_occupancy", 90),
        "covenant_status": signals.get("covenant_status", "compliant"),
        "months_since_origination": signals.get("months_since_origination", 12),
        "hft_return_ytd": signals.get("hft_return_ytd", 10),
        "b_tranche_coverage": signals.get("b_tranche_coverage", 1.0),
        "lc_capacity_ratio": signals.get("lc_capacity_ratio", 1.0),
    }


def _parse_refi_access(val) -> float:
    """Convert string or numeric refi access to 0-100 scale."""
    if isinstance(val, (int, float)):
        return float(val)
    mapping = {"open_favorable": 85, "open_neutral": 60, "restricted": 30, "closed": 5}
    return mapping.get(str(val), 50)


# ── Live FRED Rates (unchanged) ──────────────────────────────

@market_bp.route("/rates/live", methods=["GET"])
def live_rates():
    """Bond Desk live rate snapshot from FRED."""
    fred = _get_fred_plugin()
    if not fred:
        return _err("FRED plugin unavailable", 503)
    snapshot = fred.get_bond_desk_snapshot()
    return _ok(snapshot)


@market_bp.route("/rates/yield-curve", methods=["GET"])
def yield_curve():
    """Full Treasury yield curve."""
    fred = _get_fred_plugin()
    if not fred:
        return _err("FRED plugin unavailable", 503)
    curve = fred.get_yield_curve()
    return _ok(curve)


@market_bp.route("/rates/snapshot", methods=["GET"])
def market_snapshot():
    """Quick market snapshot — key rates for dashboards."""
    fred = _get_fred_plugin()
    if not fred:
        return _err("FRED plugin unavailable", 503)
    snap = fred.get_market_snapshot()
    return _ok(snap)
