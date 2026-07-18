"""
Search History Management
Database operations for per-user search history (backs the sidebar in the frontend)

NEGATIVE SPACE CONTRACT (mirrors frontend/lib/searchHistory.js):
- Every entry is { id: str, label: str, params: dict, ts: int(epoch ms) }
- Listing is always newest-first and never exceeds MAX_ENTRIES_PER_USER
- Adding an entry with identical params bumps the existing row to the top
  (same id, updated ts) instead of duplicating
- params are opaque to the API: stored verbatim, replayed by the client
"""

import hashlib
import json
from typing import Any, Dict, List

from backend.api import database

MAX_ENTRIES_PER_USER = 50


def params_signature(params: Dict[str, Any]) -> str:
    """SHA-256 hex of the canonical (sorted-keys, compact) params JSON."""
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class SearchHistoryManager:
    """Manages per-user search history entries"""

    @staticmethod
    def _row_to_entry(row) -> Dict[str, Any]:
        return {
            "id": str(row["id"]),
            "label": row["label"],
            "params": json.loads(row["params"]),
            "ts": int(row["updated_at"].timestamp() * 1000),
        }

    @staticmethod
    async def list_entries(user_id: str) -> List[Dict[str, Any]]:
        """Newest-first history for a user, capped at MAX_ENTRIES_PER_USER."""
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, label, params, updated_at
                FROM search_history
                WHERE user_id = $1
                ORDER BY updated_at DESC, id
                LIMIT $2
            """,
                user_id,
                MAX_ENTRIES_PER_USER,
            )

        return [SearchHistoryManager._row_to_entry(row) for row in rows]

    @staticmethod
    async def add_entry(user_id: str, label: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upsert an entry: identical params (by signature) bump the existing row,
        then trim the user's history to MAX_ENTRIES_PER_USER.
        """
        signature = params_signature(params)

        pool = await database.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO search_history (user_id, label, params, params_signature)
                    VALUES ($1, $2, $3::jsonb, $4)
                    ON CONFLICT ON CONSTRAINT search_history_unique_per_user
                    DO UPDATE SET
                        label = EXCLUDED.label,
                        params = EXCLUDED.params,
                        updated_at = NOW()
                    RETURNING id, label, params, updated_at
                """,
                    user_id,
                    label,
                    json.dumps(params),
                    signature,
                )

                await conn.execute(
                    """
                    DELETE FROM search_history
                    WHERE user_id = $1
                      AND id NOT IN (
                          SELECT id
                          FROM search_history
                          WHERE user_id = $1
                          ORDER BY updated_at DESC, id
                          LIMIT $2
                      )
                """,
                    user_id,
                    MAX_ENTRIES_PER_USER,
                )

        return SearchHistoryManager._row_to_entry(row)

    @staticmethod
    async def remove_entry(user_id: str, entry_id: str) -> bool:
        """Delete one entry. Returns False if it doesn't exist or belongs to another user."""
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM search_history WHERE id = $1 AND user_id = $2", entry_id, user_id
            )

        return str(result) == "DELETE 1"

    @staticmethod
    async def clear_entries(user_id: str) -> int:
        """Delete all of a user's history. Returns the number of rows removed."""
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM search_history WHERE user_id = $1", user_id)

        return int(result.split()[-1])
