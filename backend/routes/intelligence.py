"""NEST Intelligence Routes — Bond Intel + Monitor + AI Router"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

intelligence_bp = Blueprint("intelligence", __name__)

try:
    from services.core import ok, err
except ImportError:
    def ok(d, c=200):
        return jsonify({"success": True, "data": d, "timestamp": datetime.utcnow().isoformat()}), c

    def err(m, c=400):
        return jsonify({"success": False, "error": m, "timestamp": datetime.utcnow().isoformat()}), c

from services.bond_intelligence import (bond_intel, BOND_TYPES, GRADING_CRITERIA,
                                        MILESTONE_GATES, PROFESSIONAL_TEAM,
                                        HUNDRED_PCT_FINANCING, REQUIRED_DOCUMENTS)
from services.project_monitor import project_monitor
from services.ai_router import ai_router
from services.phase_bond_engine import phase_bond_engine
from services.ma_bond_engine import ma_bond_engine, MA_BOND_RULES
from services.forensic_audit import forensic_audit, AUDIT_STANDARDS
from services.bridge_fund import bridge_fund
from services.licensing import licensing_service


# ── BOND INTELLIGENCE ─────────────────────────────────────────

@intelligence_bp.route("/api/bond-intel/types", methods=["GET"])
def bond_types():
    return ok(BOND_TYPES)


@intelligence_bp.route("/api/bond-intel/grading", methods=["GET"])
def grading():
    return ok(GRADING_CRITERIA)


@intelligence_bp.route("/api/bond-intel/milestones", methods=["GET"])
def milestones():
    return ok(MILESTONE_GATES)


@intelligence_bp.route("/api/bond-intel/team", methods=["GET"])
def team():
    return ok(PROFESSIONAL_TEAM)


@intelligence_bp.route("/api/bond-intel/documents", methods=["GET"])
def documents():
    bond_type = request.args.get("bond_type", "REVENUE_BOND")
    return ok(REQUIRED_DOCUMENTS.get(bond_type, REQUIRED_DOCUMENTS["REVENUE_BOND"]))


@intelligence_bp.route("/api/bond-intel/100pct-path", methods=["GET"])
def hundred_pct():
    return ok(HUNDRED_PCT_FINANCING)


@intelligence_bp.route("/api/bond-intel/rating-readiness", methods=["POST"])
@jwt_required()
def rating_readiness():
    body = request.get_json() or {}
    return ok(bond_intel.assess_rating_readiness(body))


@intelligence_bp.route("/api/bond-intel/financing-path", methods=["POST"])
@jwt_required()
def financing_path():
    body = request.get_json() or {}
    return ok(bond_intel.get_financing_path(
        body.get("stage", "pre_development"),
        body.get("loan_amount_usd", 0),
        body.get("presales_pct", 0)
    ))


@intelligence_bp.route("/api/bond-intel/milestone-status", methods=["POST"])
@jwt_required()
def milestone_status():
    body = request.get_json() or {}
    return ok(bond_intel.get_milestone_status(
        body.get("current_gate", 1),
        body.get("presales_pct", 0),
        body.get("has_feasibility", False),
        body.get("has_GMP", False)
    ))


# ── PROJECT MONITOR ───────────────────────────────────────────

@intelligence_bp.route("/api/monitor/projects", methods=["POST"])
@jwt_required()
def create_project():
    body = request.get_json() or {}
    if not body.get("deal_id"):
        return err("deal_id required")
    return ok(project_monitor.create_project(body["deal_id"], body)), 201


@intelligence_bp.route("/api/monitor/projects/<deal_id>", methods=["GET"])
@jwt_required()
def get_dashboard(deal_id):
    return ok(project_monitor.get_dashboard(deal_id))


@intelligence_bp.route("/api/monitor/projects/<deal_id>/draw", methods=["POST"])
@jwt_required()
def record_draw(deal_id):
    body = request.get_json() or {}
    return ok(project_monitor.record_draw(deal_id, body))


@intelligence_bp.route("/api/monitor/projects/<deal_id>/presale", methods=["POST"])
@jwt_required()
def record_presale(deal_id):
    body = request.get_json() or {}
    return ok(project_monitor.record_presale(
        deal_id, body.get("unit_type", "ILU"),
        body.get("unit_number", ""), body.get("deposit_usd", 0),
        body.get("binding", False)
    ))


@intelligence_bp.route("/api/monitor/projects/<deal_id>/alert/<alert_id>/ack", methods=["PATCH"])
@jwt_required()
def ack_alert(deal_id, alert_id):
    p = project_monitor.projects.get(deal_id)
    if not p:
        return err("Not found", 404)
    for a in p.get("alerts", []):
        if a["id"] == alert_id:
            a["acknowledged"] = True
            return ok({"acknowledged": True, "alert_id": alert_id})
    return err("Alert not found", 404)


# ── AI ROUTER ─────────────────────────────────────────────────

@intelligence_bp.route("/api/ai/status", methods=["GET"])
@jwt_required()
def ai_status():
    return ok(ai_router.get_tool_status())


@intelligence_bp.route("/api/ai/market-rates", methods=["GET"])
def market_rates():
    return ok(ai_router.get_market_rates())


@intelligence_bp.route("/api/ai/route", methods=["POST"])
@jwt_required()
def route_task():
    body = request.get_json() or {}
    if not body.get("prompt"):
        return err("prompt required")
    return ok(ai_router.route(
        task_type=body.get("task_type", "credit_memo"),
        prompt=body["prompt"],
        system=body.get("system"),
        force_tool=body.get("force_tool"),
    ))


# ── PHASE BOND ENGINE ─────────────────────────────────────────

@intelligence_bp.route("/api/phase-bonds/structure", methods=["POST"])
@jwt_required()
def phase_bond_structure():
    body = request.get_json() or {}
    if not body.get("total_project_cost_usd"):
        return err("total_project_cost_usd required")
    return ok(phase_bond_engine.structure_phase_bonds(
        body["total_project_cost_usd"],
        body.get("base_rate_bps", 650),
        body.get("project_type", "senior_living")
    ))


@intelligence_bp.route("/api/phase-bonds/phases", methods=["GET"])
def phase_bond_phases():
    return ok(phase_bond_engine.PHASES)


@intelligence_bp.route("/api/phase-bonds/economics", methods=["POST"])
@jwt_required()
def phase_bond_economics():
    body = request.get_json() or {}
    structure = phase_bond_engine.structure_phase_bonds(
        body.get("total_project_cost_usd", 200_000_000),
        body.get("base_rate_bps", 650),
        body.get("project_type", "senior_living")
    )
    return ok(phase_bond_engine.compute_nest_economics(structure["phases"]))


@intelligence_bp.route("/api/phase-bonds/calls-puts", methods=["POST"])
@jwt_required()
def phase_bond_calls_puts():
    body = request.get_json() or {}
    structure = phase_bond_engine.structure_phase_bonds(
        body.get("total_project_cost_usd", 200_000_000),
        body.get("base_rate_bps", 650)
    )
    scenarios = body.get("rate_scenarios", [
        {"name": "rates_down_100", "rate_bps": 550},
        {"name": "rates_up_100", "rate_bps": 750},
        {"name": "rates_up_200", "rate_bps": 850},
    ])
    return ok(phase_bond_engine.optimize_calls_puts(structure["phases"], scenarios))


# ── M&A BOND ENGINE ───────────────────────────────────────────

@intelligence_bp.route("/api/ma-bonds/rules", methods=["GET"])
def ma_bond_rules():
    return ok(MA_BOND_RULES)


@intelligence_bp.route("/api/ma-bonds/structure", methods=["POST"])
@jwt_required()
def ma_bond_structure():
    body = request.get_json() or {}
    company = body.get("company", {})
    terms = body.get("acquisition_terms", {})
    if not company.get("ebitda_usd"):
        return err("company.ebitda_usd required")
    return ok(ma_bond_engine.structure_acquisition_bond(company, terms))


@intelligence_bp.route("/api/ma-bonds/pik-analysis", methods=["POST"])
@jwt_required()
def ma_pik_analysis():
    body = request.get_json() or {}
    return ok(ma_bond_engine.model_pik_vs_cash_pay(
        body.get("bond_amount_usd", 100_000_000),
        body.get("coupon_pct", 12),
        body.get("hold_years", 5),
        body.get("ebitda_growth_pct", 10)
    ))


@intelligence_bp.route("/api/ma-bonds/balance-sheet", methods=["POST"])
@jwt_required()
def ma_balance_sheet():
    body = request.get_json() or {}
    return ok(ma_bond_engine.balance_sheet_analysis(
        body.get("company", {}),
        body.get("bond_structure", {})
    ))


# ── FORENSIC AUDIT ────────────────────────────────────────────

@intelligence_bp.route("/api/audit/standards", methods=["GET"])
def audit_standards():
    return ok(AUDIT_STANDARDS)


@intelligence_bp.route("/api/audit/run", methods=["POST"])
@jwt_required()
def run_audit():
    body = request.get_json() or {}
    return ok(forensic_audit.run_full_audit(
        body.get("deal", {}),
        body.get("documents", {}),
        body.get("financials", {})
    ))


@intelligence_bp.route("/api/audit/sources-uses", methods=["POST"])
@jwt_required()
def audit_sources_uses():
    body = request.get_json() or {}
    return ok(forensic_audit.validate_sources_uses(
        body.get("sources_uses", {}),
        body.get("bank_records", [])
    ))


@intelligence_bp.route("/api/audit/assumptions", methods=["POST"])
@jwt_required()
def audit_assumptions():
    body = request.get_json() or {}
    return ok(forensic_audit.validate_assumptions(
        body.get("projections", {}),
        body.get("market_comps", [])
    ))


@intelligence_bp.route("/api/audit/rating-presentation", methods=["POST"])
@jwt_required()
def audit_rating_presentation():
    body = request.get_json() or {}
    return ok(forensic_audit.rating_agency_presentation(
        body.get("deal", {}),
        body.get("audit", {}),
        body.get("target_agency", "SP")
    ))


@intelligence_bp.route("/api/audit/bank-presentation", methods=["POST"])
@jwt_required()
def audit_bank_presentation():
    body = request.get_json() or {}
    return ok(forensic_audit.bank_presentation(
        body.get("deal", {}),
        body.get("audit", {}),
        body.get("bank", "JPMorgan")
    ))


# ── BRIDGE FUND ───────────────────────────────────────────────

@intelligence_bp.route("/api/bridge/underwrite", methods=["POST"])
@jwt_required()
def bridge_underwrite():
    body = request.get_json() or {}
    if not body.get("amount_usd"):
        return err("amount_usd required")
    return ok(bridge_fund.underwrite_bridge(
        body.get("deal", {}),
        body["amount_usd"],
        body.get("use_of_proceeds", "soft_costs")
    ))


@intelligence_bp.route("/api/bridge/equity-value", methods=["POST"])
@jwt_required()
def bridge_equity_value():
    body = request.get_json() or {}
    return ok(bridge_fund.calculate_equity_value(
        body.get("deal", {}),
        body.get("equity_pct", 12.5),
        body.get("exit_ev_usd", 0)
    ))


@intelligence_bp.route("/api/bridge/portfolio", methods=["GET"])
@jwt_required()
def bridge_portfolio():
    return ok(bridge_fund.portfolio_dashboard())


@intelligence_bp.route("/api/bridge/<loan_id>/repay", methods=["POST"])
@jwt_required()
def bridge_repay(loan_id):
    body = request.get_json() or {}
    return ok(bridge_fund.repay_loan(loan_id, body.get("repayment_source", "bond_proceeds")))


# ── LICENSING & COMPLIANCE ────────────────────────────────────

@intelligence_bp.route("/api/licensing/roadmap", methods=["GET"])
def licensing_roadmap():
    return ok(licensing_service.get_roadmap())


@intelligence_bp.route("/api/licensing/status", methods=["GET"])
@jwt_required()
def licensing_status():
    return ok(licensing_service.get_current_status())


@intelligence_bp.route("/api/licensing/fees", methods=["GET"])
@jwt_required()
def licensing_fees():
    return ok(licensing_service.get_fee_structure())


@intelligence_bp.route("/api/licensing/compliance-calendar", methods=["GET"])
@jwt_required()
def compliance_calendar():
    return ok(licensing_service.get_compliance_calendar())


@intelligence_bp.route("/api/licensing/rent-vs-own", methods=["POST"])
@jwt_required()
def rent_vs_own():
    body = request.get_json() or {}
    return ok(licensing_service.calculate_rent_vs_own(
        body.get("annual_fees_usd", 0)
    ))


@intelligence_bp.route("/api/licensing/finra-letter", methods=["POST"])
@jwt_required()
def finra_letter():
    letter = licensing_service.generate_finra_sponsorship_request()
    return ok({"letter": letter})


@intelligence_bp.route("/api/licensing/exam/<exam_name>", methods=["GET"])
def exam_detail(exam_name):
    return ok(licensing_service.get_exam_study_plan(exam_name))
