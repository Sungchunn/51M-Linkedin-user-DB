"""
Simple API key + scopes auth.

Environment configuration:
- REQUIRE_API_KEY: "true"/"false" (default: false)
- API_KEYS: JSON mapping of api key -> {"scopes": [...], "tier": "public|basic|trusted"}
  Example: {"demo-key": {"scopes": ["search:read"], "tier": "basic"}}
- PUBLIC_MAX_LIMIT (default: 50)
- AUTH_MAX_LIMIT (default: 200)
- TRUSTED_MAX_LIMIT (default: 1000)
- MAX_OFFSET (default: 100000)

PRIORITY: Database API keys checked FIRST, then falls back to env var API keys
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass
from typing import Optional, Set
import logging

logger = logging.getLogger(__name__)


@dataclass
class AuthContext:
    api_key: Optional[str]
    scopes: Set[str]
    tier: str  # public|basic|trusted
    max_limit: int
    max_offset: int

    @property
    def allow_export(self) -> bool:
        return "export:read" in self.scopes and self.tier in {"basic", "trusted"}

    @property
    def allow_pii(self) -> bool:
        return "pii:read" in self.scopes


def _load_keys() -> dict:
    raw = os.getenv("API_KEYS", "{}")
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_tier_max_limit(tier: str) -> int:
    """Get max result limit for a given tier"""
    public_max = int(os.getenv("PUBLIC_MAX_LIMIT", "50"))
    auth_max = int(os.getenv("AUTH_MAX_LIMIT", "200"))
    trusted_max = int(os.getenv("TRUSTED_MAX_LIMIT", "1000"))

    tier_limits = {
        "public": public_max,
        "basic": auth_max,
        "trusted": trusted_max
    }
    return tier_limits.get(tier, public_max)


async def resolve_auth_context(header_key: Optional[str]) -> AuthContext:
    """
    Resolve authentication context from API key.

    PRIORITY:
    1. Check database for user-generated API keys (via APIKeyManager)
    2. Fall back to environment variable API keys (admin/demo keys)
    3. If no key provided, return public tier context

    Returns AuthContext with tier, scopes, and limits.
    """
    require = os.getenv("REQUIRE_API_KEY", "false").lower() == "true"
    public_max = int(os.getenv("PUBLIC_MAX_LIMIT", "50"))
    max_offset = int(os.getenv("MAX_OFFSET", "100000"))

    # No API key provided
    if not header_key:
        if require:
            # No key but required: mark as public with zero scopes; endpoint guards will reject
            return AuthContext(api_key=None, scopes=set(), tier="public", max_limit=public_max, max_offset=max_offset)
        return AuthContext(api_key=None, scopes=set(), tier="public", max_limit=public_max, max_offset=max_offset)

    # PRIORITY 1: Check database for user-generated API keys
    try:
        from backend.api.user_manager import APIKeyManager
        db_key_data = await APIKeyManager.verify_api_key(header_key)

        if db_key_data:
            tier = db_key_data.get('tier', 'public')
            scopes = set(db_key_data.get('scopes', []))
            max_limit = _get_tier_max_limit(tier)

            logger.info(f"Database API key validated: tier={tier}, scopes={scopes}")

            return AuthContext(
                api_key=header_key,
                scopes=scopes,
                tier=tier,
                max_limit=max_limit,
                max_offset=max_offset
            )
    except Exception as e:
        logger.error(f"Error checking database API key: {e}")

    # PRIORITY 2: Fall back to environment variable API keys (for admin/demo keys)
    keys = _load_keys()
    meta = keys.get(header_key)

    if not meta:
        # Unknown key -> treat as public (no scopes)
        logger.warning(f"Unknown API key provided (not in DB or env): {header_key[:8]}...")
        return AuthContext(api_key=header_key, scopes=set(), tier="public", max_limit=public_max, max_offset=max_offset)

    # Environment variable key found
    scopes = set(meta.get("scopes", []))
    tier = str(meta.get("tier", "basic")).lower()
    max_limit = _get_tier_max_limit(tier)

    logger.info(f"Environment API key validated: tier={tier}, scopes={scopes}")

    return AuthContext(api_key=header_key, scopes=scopes, tier=tier, max_limit=max_limit, max_offset=max_offset)
