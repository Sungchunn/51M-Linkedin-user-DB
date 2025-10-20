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
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass
from typing import Optional, Set


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


def resolve_auth_context(header_key: Optional[str]) -> AuthContext:
    require = os.getenv("REQUIRE_API_KEY", "false").lower() == "true"
    keys = _load_keys()

    public_max = int(os.getenv("PUBLIC_MAX_LIMIT", "50"))
    auth_max = int(os.getenv("AUTH_MAX_LIMIT", "200"))
    trusted_max = int(os.getenv("TRUSTED_MAX_LIMIT", "1000"))
    max_offset = int(os.getenv("MAX_OFFSET", "100000"))

    if not header_key:
        if require:
            # No key but required: mark as public with zero scopes; caller should be rejected by endpoint guards
            return AuthContext(api_key=None, scopes=set(), tier="public", max_limit=public_max, max_offset=max_offset)
        return AuthContext(api_key=None, scopes=set(), tier="public", max_limit=public_max, max_offset=max_offset)

    meta = keys.get(header_key)
    if not meta:
        # Unknown key -> treat as public if not requiring, else still public; endpoint may reject
        return AuthContext(api_key=header_key, scopes=set(), tier="public", max_limit=public_max, max_offset=max_offset)

    scopes = set(meta.get("scopes", []))
    tier = str(meta.get("tier", "basic")).lower()
    if tier == "trusted":
        max_limit = trusted_max
    else:
        max_limit = auth_max

    return AuthContext(api_key=header_key, scopes=scopes, tier=tier, max_limit=max_limit, max_offset=max_offset)

