"""
Natural-Language Query Parser
Extracts structured search filters + a semantic query from freeform text.

An OpenAI model (NL_PARSE_MODEL, default gpt-4o-mini) receives the user's text
plus the ACTUAL region/industry vocabulary from the database and returns a
strict-JSON structure. The residual intent (role, seniority, domain, skills)
stays in semantic_query for the existing hybrid vector+lexical search;
only hard constraints become filters.

NEGATIVE SPACE CONTRACT:
- parse_natural_query never raises: any failure returns a fallback where the
  entire text is the semantic query and parse_failed=True — search still works
- regions/industries are kept ONLY if they exactly match the database
  vocabulary (case-insensitive compare, DB casing returned) — a hallucinated
  filter value would silently return zero results
- Skills/technologies are deliberately NOT hard filters (skills @> is exact
  AND-containment — one wrong string zeroes the results); they stay in the
  semantic query where embeddings handle them
- Years are clamped to [0, 80]; a min > max pair is swapped
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, cast

from openai import AsyncOpenAI

from backend.api import database

logger = logging.getLogger(__name__)

_client: Optional[AsyncOpenAI] = None
_vocab: Optional[Dict[str, List[str]]] = None

# Successful parses cached by normalized text so pagination and repeat
# searches don't re-pay the LLM call. FIFO-evicted at the cap.
_parse_cache: Dict[str, Dict[str, Any]] = {}
_PARSE_CACHE_MAX = 256

PARSE_SCHEMA = {
    "name": "search_filters",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "semantic_query": {
                "type": "string",
                "description": "The search intent minus extracted hard filters: role, seniority, domain, skills, technologies. Empty string when the request contains only filters and filler words.",
            },
            "regions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "US states from the allowed list only. Map cities/metros to their state.",
            },
            "industries": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Industries from the allowed list only.",
            },
            "min_years_experience": {"type": ["integer", "null"]},
            "max_years_experience": {"type": ["integer", "null"]},
            "job_title": {
                "type": ["string", "null"],
                "description": "Only when the text demands an exact title match; otherwise leave null and keep it in semantic_query.",
            },
            "company": {
                "type": ["string", "null"],
                "description": "Only when a specific employer is named.",
            },
            "has_linkedin": {"type": "boolean"},
            "has_email": {"type": "boolean"},
            "has_phone": {"type": "boolean"},
            "has_website": {"type": "boolean"},
            "has_twitter": {"type": "boolean"},
            "has_github": {"type": "boolean"},
        },
        "required": [
            "semantic_query",
            "regions",
            "industries",
            "min_years_experience",
            "max_years_experience",
            "job_title",
            "company",
            "has_linkedin",
            "has_email",
            "has_phone",
            "has_website",
            "has_twitter",
            "has_github",
        ],
    },
}

SYSTEM_PROMPT = """You convert a recruiter's freeform talent-search request into structured filters for a profile database.

Rules:
- semantic_query carries everything that describes the KIND of person (role, seniority, domain, skills, technologies). When in doubt, keep words there.
- Generic person nouns ("candidate", "people", "someone", "profiles", "talent") and search verbs ("find", "search for", "looking for", "show me") are filler, NOT intent — never put them in semantic_query. "find candidates in NYC" is only a location filter: semantic_query is "". Role phrases keep their words though: "people operations manager" and "talent acquisition lead" stay intact.
- semantic_query must NOT repeat anything you extracted into filters: once a location, industry, experience amount, company, or contact requirement becomes a filter, its words leave semantic_query ("sales directors in the banking industry" -> industries=[banking], semantic_query="sales directors").
- regions: only values from ALLOWED_REGIONS. Map cities/metros to their state ("NYC" -> "new york", "Bay Area" -> "california", "Austin" -> "texas"). If no location is mentioned, return [].
- industries: only values from ALLOWED_INDUSTRIES, and only when the text clearly names a sector. Do not guess an industry from a job role.
- min/max_years_experience: only when the text states an experience amount ("8+ years" -> min 8; "junior" alone is NOT a number).
- company: only when a specific employer is named ("at Google", "works for Stripe").
- job_title: null unless the user explicitly pins the exact title ("title is VP of Sales", a quoted title). Casually described roles ("ML researchers", "sales leaders") belong ONLY in semantic_query — a title filter is a hard substring match and easily returns zero results.
- has_*: true only when the text asks for that contact info ("with emails", "must have GitHub").
- Extract nothing that is not in the text."""


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("NEGATIVE SPACE: OPENAI_API_KEY not set — cannot parse queries")
        _client = AsyncOpenAI(api_key=api_key)
    return _client


async def get_filter_vocabulary() -> Dict[str, List[str]]:
    """Distinct region/industry values from the DB. Cached for process lifetime
    (the dataset is static); ~52 regions + ~147 industries."""
    global _vocab
    if _vocab is None:
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            regions = await conn.fetch(
                "SELECT DISTINCT region FROM profiles "
                "WHERE region IS NOT NULL AND is_deleted = FALSE ORDER BY region"
            )
            industries = await conn.fetch(
                "SELECT DISTINCT industry FROM profiles "
                "WHERE industry IS NOT NULL AND is_deleted = FALSE ORDER BY industry"
            )
        _vocab = {
            "regions": [r["region"] for r in regions],
            "industries": [r["industry"] for r in industries],
        }
        logger.info(
            f"NL parser vocabulary loaded: {len(_vocab['regions'])} regions, "
            f"{len(_vocab['industries'])} industries"
        )
    return _vocab


def _validate_against_vocab(values: List[str], vocab: List[str]) -> List[str]:
    """Keep only values present in the vocabulary (case-insensitive), in DB casing."""
    lookup = {v.lower(): v for v in vocab}
    matched = [lookup[v.lower()] for v in values if v.lower() in lookup]
    dropped = [v for v in values if v.lower() not in lookup]
    if dropped:
        logger.warning(f"NL parser: dropped non-vocabulary values {dropped}")
    return matched


def _fallback(text: str) -> Dict[str, Any]:
    return {"semantic_query": text, "filters": {}, "parse_failed": True}


# Deterministic backstop to the prompt rule above: single tokens that describe
# every profile and none. Lexically they'd match profiles merely CONTAINING the
# word ("JD candidate"). Role words like "people"/"talent" are deliberately
# absent — they carry meaning in phrases ("people operations", "talent
# acquisition"), which the LLM keeps intact.
_FILLER_TOKENS = {
    "anyone",
    "candidate",
    "candidates",
    "find",
    "give",
    "i",
    "list",
    "looking",
    "me",
    "need",
    "person",
    "please",
    "profile",
    "profiles",
    "search",
    "seeking",
    "show",
    "someone",
    "want",
}


def _strip_filler(text: str) -> str:
    """Drop filler tokens from a residual query; may return an empty string."""
    kept = [t for t in text.split() if t.lower().strip(",.") not in _FILLER_TOKENS]
    return " ".join(kept)


_HAS_FLAG_TOKENS = {
    "has_email": {"email", "emails"},
    "has_phone": {"phone", "phones"},
    "has_github": {"github"},
    "has_linkedin": {"linkedin"},
    "has_twitter": {"twitter"},
    "has_website": {"website"},
}


def _subtract_filter_tokens(semantic_query: str, filters: Dict[str, Any]) -> str:
    """
    The model is instructed to subtract extracted-filter phrases from
    semantic_query but does not always comply ("sales directors in the banking
    industry" kept "banking industry" while industries=[banking]). Enforce it
    deterministically: tokens belonging to extracted filter VALUES and their
    marker words must not survive into the lexical gate, where they would
    demand the literal word in the profile text.
    """
    drop: set[str] = set()
    for value in (filters.get("regions") or []) + (filters.get("industries") or []):
        drop.update(value.lower().split())
    if filters.get("industries"):
        drop.update({"industry", "industries", "sector"})
    if filters.get("company"):
        drop.update(str(filters["company"]).lower().split())
        drop.add("at")
    if (
        filters.get("min_years_experience") is not None
        or filters.get("max_years_experience") is not None
    ):
        drop.update({"year", "years", "experience"})
    for flag, words in _HAS_FLAG_TOKENS.items():
        if filters.get(flag):
            drop.update(words)
    kept = [t for t in semantic_query.split() if t.lower().strip(",.") not in drop]
    return " ".join(kept)


async def parse_natural_query(text: str) -> Dict[str, Any]:
    """
    Parse freeform text into {semantic_query, filters, parse_failed}.

    filters contains only SearchRequest-shaped fields that were actually
    extracted (regions, industries, min/max_years_experience, job_title,
    company, has_*). Never raises.
    """
    cache_key = text.strip().lower()
    cached = _parse_cache.get(cache_key)
    if cached is not None:
        return {**cached, "filters": dict(cached["filters"])}

    started = time.time()
    try:
        vocab = await get_filter_vocabulary()
        client = _get_client()

        response = await client.chat.completions.create(
            model=os.getenv("NL_PARSE_MODEL", "gpt-4o-mini"),
            temperature=0,
            max_tokens=400,
            response_format=cast(Any, {"type": "json_schema", "json_schema": PARSE_SCHEMA}),
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"ALLOWED_REGIONS: {', '.join(vocab['regions'])}\n\n"
                        f"ALLOWED_INDUSTRIES: {', '.join(vocab['industries'])}\n\n"
                        f"Request: {text}"
                    ),
                },
            ],
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("NEGATIVE SPACE: model returned no content for parse request")
        raw = json.loads(content)

        filters: Dict[str, Any] = {}

        regions = _validate_against_vocab(raw.get("regions") or [], vocab["regions"])
        if regions:
            filters["regions"] = regions

        industries = _validate_against_vocab(raw.get("industries") or [], vocab["industries"])
        if industries:
            filters["industries"] = industries

        min_years = raw.get("min_years_experience")
        max_years = raw.get("max_years_experience")
        min_years = max(0, min(80, min_years)) if min_years is not None else None
        max_years = max(0, min(80, max_years)) if max_years is not None else None
        if min_years is not None and max_years is not None and min_years > max_years:
            min_years, max_years = max_years, min_years
        if min_years is not None:
            filters["min_years_experience"] = min_years
        if max_years is not None:
            filters["max_years_experience"] = max_years

        if raw.get("job_title"):
            filters["job_title"] = raw["job_title"]
        if raw.get("company"):
            filters["company"] = raw["company"]

        for flag in (
            "has_linkedin",
            "has_email",
            "has_phone",
            "has_website",
            "has_twitter",
            "has_github",
        ):
            if raw.get(flag) is True:
                filters[flag] = True

        # May legitimately end up empty ("find candidates in NYC" is only a
        # filter) — an empty query downstream means filtered browse mode.
        semantic_query = _subtract_filter_tokens(
            _strip_filler((raw.get("semantic_query") or "").strip()), filters
        )

        logger.info(
            f"NL parse ok in {(time.time() - started) * 1000:.0f}ms: "
            f"{len(filters)} filters from {text!r}"
        )
        result = {"semantic_query": semantic_query, "filters": filters, "parse_failed": False}
        if len(_parse_cache) >= _PARSE_CACHE_MAX:
            _parse_cache.pop(next(iter(_parse_cache)))
        _parse_cache[cache_key] = {**result, "filters": dict(filters)}
        return result

    except Exception as e:
        logger.warning(f"NL parse failed for {text!r} — falling back to pure semantic: {e}")
        return _fallback(text)
