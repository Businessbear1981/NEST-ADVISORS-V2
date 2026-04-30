"""
NEST AI Router — The Power Strip
NEST is the power strip. Every AI tool plugs in via universal API.
Primary: Claude (analysis, writing, modeling)
Real-time data: Grok
Fallback: ChatGPT
Quality: Grammarly (when configured)
All agents route through here. One interface. Multiple models.
"""
import os, httpx
from datetime import datetime

OR_KEY = os.getenv("OPENROUTER_API_KEY", "")
MODEL_CLAUDE = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
GROK_KEY = os.getenv("GROK_API_KEY", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")

# Task → tool mapping
ROUTING = {
    "credit_memo": "claude", "business_plan": "claude",
    "risk_assessment": "claude", "feasibility_narrative": "claude",
    "bd_outreach": "claude", "investor_teaser": "claude",
    "bond_structuring": "claude", "executive_summary": "claude",
    "ma_analysis": "claude", "legal_summary": "claude",
    "market_rates": "grok", "treasury_rates": "grok",
    "market_news": "grok", "competitor_intel": "grok",
    "fallback": "claude",
}


class AIRouter:

    def route(self, task_type: str, prompt: str,
              system: str = None, force_tool: str = None) -> dict:
        tool = force_tool or ROUTING.get(task_type, "claude")
        if tool == "grok" and GROK_KEY:
            r = self._grok(prompt)
            if r["success"]:
                return r
        if tool == "openai" and OPENAI_KEY:
            return self._openai(prompt, system)
        return self._claude(prompt, system)

    def _claude(self, prompt: str, system: str = None) -> dict:
        try:
            from services.core import call_claude, JIMMY_LEE
            text = call_claude(prompt, system or JIMMY_LEE)
            return {"tool": "claude", "model": MODEL_CLAUDE,
                    "content": text, "success": True,
                    "timestamp": datetime.utcnow().isoformat()}
        except Exception as e:
            return {"tool": "claude", "content": "", "success": False, "error": str(e)}

    def _grok(self, prompt: str) -> dict:
        try:
            with httpx.Client(timeout=20) as c:
                r = c.post("https://api.x.ai/v1/chat/completions",
                           headers={"Authorization": f"Bearer {GROK_KEY}",
                                    "Content-Type": "application/json"},
                           json={"model": "grok-beta", "max_tokens": 1000,
                                 "messages": [{"role": "user", "content": prompt}]})
                r.raise_for_status()
                return {"tool": "grok", "content": r.json()["choices"][0]["message"]["content"],
                        "success": True, "timestamp": datetime.utcnow().isoformat()}
        except Exception as e:
            return {"tool": "grok", "content": "", "success": False, "error": str(e)}

    def _openai(self, prompt: str, system: str = None) -> dict:
        try:
            msgs = []
            if system:
                msgs.append({"role": "system", "content": system})
            msgs.append({"role": "user", "content": prompt})
            with httpx.Client(timeout=30) as c:
                r = c.post("https://api.openai.com/v1/chat/completions",
                           headers={"Authorization": f"Bearer {OPENAI_KEY}",
                                    "Content-Type": "application/json"},
                           json={"model": "gpt-4o", "max_tokens": 2000, "messages": msgs})
                r.raise_for_status()
                return {"tool": "openai", "content": r.json()["choices"][0]["message"]["content"],
                        "success": True, "timestamp": datetime.utcnow().isoformat()}
        except Exception as e:
            return {"tool": "openai", "content": "", "success": False, "error": str(e)}

    def get_market_rates(self) -> dict:
        """Live rates — Grok first, FRED fallback."""
        if GROK_KEY:
            r = self._grok("Current US market data: 10yr Treasury rate, SOFR, IG credit spread bps, senior living cap rate range. Be specific with today's numbers.")
            if r["success"]:
                return {"source": "grok", "data": r["content"], "timestamp": r["timestamp"]}
        try:
            with httpx.Client(timeout=8) as c:
                r = c.get("https://api.stlouisfed.org/fred/series/observations",
                          params={"series_id": "DGS10", "api_key": os.getenv("FRED_API_KEY", ""),
                                  "sort_order": "desc", "limit": 1, "file_type": "json"})
                if r.status_code == 200:
                    obs = r.json().get("observations", [])
                    rate = float(obs[0]["value"]) if obs else 4.28
                    return {"source": "FRED", "treasury_10yr_pct": rate,
                            "sofr_pct": 5.33, "ig_spread_bps": 112,
                            "timestamp": datetime.utcnow().isoformat()}
        except Exception:
            pass
        return {"source": "static_fallback", "treasury_10yr_pct": 4.28,
                "sofr_pct": 5.33, "ig_spread_bps": 112}

    def get_tool_status(self) -> dict:
        status = {
            "claude": {"configured": bool(OR_KEY), "model": MODEL_CLAUDE, "primary": True},
            "grok": {"configured": bool(GROK_KEY), "model": "grok-beta",
                     "use": "real-time market data", "key_env": "GROK_API_KEY"},
            "openai": {"configured": bool(OPENAI_KEY), "model": "gpt-4o",
                       "use": "fallback content", "key_env": "OPENAI_API_KEY"},
            "grammarly": {"configured": False, "use": "document quality",
                          "note": "Enterprise API required"},
            "cowork": {"configured": False, "use": "team collaboration",
                       "note": "Connect via Claude.ai settings"},
        }
        return {"tools": status, "primary": "claude",
                "nest_is_power_strip": True,
                "philosophy": "NEST routes every task to the best available tool. Claude is primary. Grok adds real-time data. ChatGPT is fallback. System works even with only Claude configured."}


ai_router = AIRouter()
