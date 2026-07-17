"""
Search History Routes
Per-user persistence for the frontend search-history sidebar

The frontend keeps localStorage as the anonymous fallback; logged-in clients
swap to these endpoints inside frontend/lib/searchHistory.js (the single
client access point). Entry shape matches that module: {id, label, params, ts}.
"""

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.auth_routes import get_current_user
from backend.api.history_manager import SearchHistoryManager
from backend.api.models import SearchHistoryEntry, SearchHistoryEntryCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/history", tags=["Search History"])


@router.get("", response_model=List[SearchHistoryEntry])
async def list_history(current_user: dict = Depends(get_current_user)):
    """
    List the current user's search history, newest first.

    NEGATIVE SPACE CONTRACT:
    - Requires valid JWT token
    - Always returns an array (possibly empty), capped at 50 entries
    """
    entries = await SearchHistoryManager.list_entries(current_user["id"])
    return [SearchHistoryEntry(**entry) for entry in entries]


@router.post("", response_model=SearchHistoryEntry, status_code=status.HTTP_201_CREATED)
async def add_history_entry(
    request: SearchHistoryEntryCreate, current_user: dict = Depends(get_current_user)
):
    """
    Save a search to the current user's history.

    NEGATIVE SPACE CONTRACT:
    - Requires valid JWT token
    - Identical params (order-insensitive) bump the existing entry to the top
      (same id, refreshed ts) instead of duplicating
    - History is trimmed to the 50 most recent entries
    """
    entry = await SearchHistoryManager.add_entry(
        user_id=current_user["id"], label=request.label, params=request.params
    )

    return SearchHistoryEntry(**entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_history_entry(entry_id: UUID, current_user: dict = Depends(get_current_user)):
    """
    Delete one history entry.

    NEGATIVE SPACE CONTRACT:
    - Requires valid JWT token
    - Raises 404 if the entry doesn't exist or belongs to another user
    """
    removed = await SearchHistoryManager.remove_entry(current_user["id"], str(entry_id))

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="History entry not found or doesn't belong to you",
        )

    return None


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(current_user: dict = Depends(get_current_user)):
    """
    Delete the current user's entire search history.

    NEGATIVE SPACE CONTRACT:
    - Requires valid JWT token
    - Idempotent: clearing an empty history is a success
    """
    removed_count = await SearchHistoryManager.clear_entries(current_user["id"])
    logger.info(
        f"Search history cleared: {removed_count} entries for user {current_user['username']}"
    )
    return None
