"""
NEST EDGAR Connector — SEC EFTS full-text search + company filings.

Targets Form D (private placements), 8-K (material events), S-1 (IPOs)
in SIC codes relevant to senior living, healthcare, and real estate.
SEC requires a descriptive User-Agent header; rate limit is 10 req/sec.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

log = logging.getLogger(__name__)

EFTS_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

USER_AGENT = "NEST Advisors kevin@nestadvisors.ai"

TARGET_SIC_CODES = [
    "6022",  # State commercial banks — Federal Reserve members
    "6035",  # Savings institutions — federally chartered
    "6159",  # Federal-sponsored credit agencies
    "6199",  # Finance services
    "6512",  # Operators of real property
    "8051",  # Skilled nursing care facilities
    "8059",  # Nursing and personal care facilities NEC
    "8062",  # General medical and surgical hospitals
]

TARGET_FORMS = ["D", "D/A", "8-K", "S-1", "S-1/A"]

FORM_CATEGORY_MAP = {
    "D": "deal_sourcing",
    "D/A": "deal_sourcing",
    "8-K": "regulatory",
    "S-1": "deal_sourcing",
    "S-1/A": "deal_sourcing",
}


def _headers() -> dict:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }


def search_filings(
    form_types: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 40,
) -> list[dict]:
    """Search EDGAR EFTS for recent filings matching our target forms.

    Uses the full-text search endpoint which supports dateRange and forms filters.
    Returns list of raw filing hit dicts.
    """
    if form_types is None:
        form_types = TARGET_FORMS

    if date_from is None:
        date_from = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    if date_to is None:
        date_to = datetime.utcnow().strftime("%Y-%m-%d")

    all_hits: list[dict] = []

    for form_type in form_types:
        try:
            params = {
                "q": f'formType:"{form_type}"',
                "dateRange": "custom",
                "startdt": date_from,
                "enddt": date_to,
                "forms": form_type,
            }
            resp = httpx.get(
                "https://efts.sec.gov/LATEST/search-index",
                params=params,
                headers=_headers(),
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            all_hits.extend(hits[:limit])
        except httpx.HTTPStatusError as e:
            log.warning("EDGAR EFTS search failed for %s: %s", form_type, e)
        except Exception as e:
            log.error("EDGAR EFTS search error for %s: %s", form_type, e)

    return all_hits[:limit]


def search_full_text(
    query: str = "senior living OR nursing facility OR healthcare real estate",
    form_types: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 40,
) -> list[dict]:
    """Full-text search across EDGAR filings via the EFTS search API.

    This is the primary search method — it uses SEC's full-text search
    to find filings mentioning keywords relevant to NEST's deal pipeline.
    """
    if date_from is None:
        date_from = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    if date_to is None:
        date_to = datetime.utcnow().strftime("%Y-%m-%d")

    forms_param = ",".join(form_types) if form_types else ",".join(TARGET_FORMS)

    try:
        params = {
            "q": query,
            "dateRange": "custom",
            "startdt": date_from,
            "enddt": date_to,
            "forms": forms_param,
        }
        resp = httpx.get(
            "https://efts.sec.gov/LATEST/search-index",
            params=params,
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])
        return hits[:limit]
    except Exception as e:
        log.error("EDGAR full-text search error: %s", e)
        return []


def poll_recent_filings(
    days_back: int = 7,
    limit: int = 40,
) -> list[dict]:
    """Poll for recent filings using both form-type search and full-text search.

    Combines two strategies:
    1. Form-type search for D, 8-K, S-1 filings
    2. Full-text search for senior living / healthcare / real estate keywords

    Returns deduplicated list of filing dicts normalized for downstream processing.
    """
    date_from = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    date_to = datetime.utcnow().strftime("%Y-%m-%d")

    raw_hits = search_full_text(
        query="senior living OR nursing facility OR healthcare real estate OR assisted living OR CCRC",
        form_types=TARGET_FORMS,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )

    seen_accessions: set[str] = set()
    normalized: list[dict] = []

    for hit in raw_hits:
        source = hit.get("_source", hit)
        accession = (
            source.get("file_num", "")
            or source.get("accession_no", "")
            or source.get("adsh", "")
            or ""
        )
        if accession in seen_accessions and accession:
            continue
        if accession:
            seen_accessions.add(accession)

        filing = {
            "accession_number": accession,
            "form_type": source.get("form_type", source.get("file_type", "")),
            "entity_name": source.get("entity_name", source.get("display_names", [""])[0] if isinstance(source.get("display_names"), list) else ""),
            "date_filed": source.get("file_date", source.get("period_of_report", "")),
            "cik": source.get("entity_id", source.get("ciks", [""])[0] if isinstance(source.get("ciks"), list) else ""),
            "sic_code": source.get("sic", ""),
            "state": _extract_state(source),
            "description": source.get("file_description", ""),
            "offering_amount": _extract_offering_amount(source),
            "url": _build_filing_url(source),
            "raw": source,
        }
        normalized.append(filing)

    log.info("EDGAR poll: %d filings found (%d unique)", len(raw_hits), len(normalized))
    return normalized[:limit]


def _extract_state(source: dict) -> Optional[str]:
    """Extract state abbreviation from filing data."""
    for key in ("state", "inc_state", "ba_state", "state_of_inc"):
        val = source.get(key)
        if val and isinstance(val, str) and len(val) == 2:
            return val.upper()
    addresses = source.get("addresses", {})
    if isinstance(addresses, dict):
        for addr_type in ("business", "mailing"):
            addr = addresses.get(addr_type, {})
            state = addr.get("stateOrCountry", "")
            if state and len(state) == 2:
                return state.upper()
    return None


def _extract_offering_amount(source: dict) -> Optional[float]:
    """Extract offering amount from Form D data if available."""
    for key in ("offering_amount", "total_offering_amount", "total_amount_sold"):
        val = source.get(key)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass
    return None


def _build_filing_url(source: dict) -> str:
    """Build SEC EDGAR filing URL."""
    accession = source.get("accession_no", source.get("adsh", ""))
    if accession:
        clean = accession.replace("-", "")
        return f"https://www.sec.gov/Archives/edgar/data/{source.get('entity_id', source.get('ciks', [''])[0] if isinstance(source.get('ciks'), list) else '')}/{clean}/{accession}-index.htm"
    return ""
