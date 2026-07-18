"""
INSIGHT - Search History Test Suite
Tests the per-user /history endpoints (migration 010)

Requires PG_DSN and migration 010_search_history.sql applied.
Creates throwaway users (histtest_*) and removes them in the final cleanup test.
"""

import os
import uuid

import pytest
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient

from backend.api import database
from backend.api.app import app


def _make_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _register_and_login(client: AsyncClient) -> str:
    """Create a unique throwaway user and return a Bearer token."""
    suffix = uuid.uuid4().hex[:10]
    username = f"histtest_{suffix}"
    password = "test-password-123"

    register = await client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@prospectiq.local",
            "password": password,
            "full_name": "History Test User",
        },
    )
    assert register.status_code == 201, f"registration failed: {register.text}"

    login = await client.post(
        "/auth/login",
        json={
            "username": username,
            "password": password,
        },
    )
    assert login.status_code == 200, f"login failed: {login.text}"

    return login.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestSearchHistoryAPI:
    """Search history endpoint tests"""

    @pytest.fixture(scope="class", autouse=True)
    def setup(self):
        """Setup: Load environment variables"""
        load_dotenv()

        if not os.getenv("PG_DSN"):
            pytest.skip("PG_DSN not configured")

        yield

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """
        pytest-asyncio gives each test its own event loop, but the global asyncpg
        pool stays bound to the loop it was created on. Close it after every test
        so the next test rebuilds it on its own loop.
        """
        yield
        await database.close_pool()

    @pytest.mark.asyncio
    async def test_tc_h_0_table_exists(self):
        """TC-H.0: search_history table exists (migration 010 applied)"""
        pool = await database.get_pool()
        exists = await pool.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'search_history')"
        )
        assert exists, (
            "search_history table missing — apply migrations/010_search_history.sql "
            "before running these tests"
        )

    @pytest.mark.asyncio
    async def test_tc_h_1_requires_auth(self):
        """TC-H.1: All history endpoints reject unauthenticated requests"""
        async with _make_client() as client:
            assert (await client.get("/history")).status_code == 403
            assert (
                await client.post("/history", json={"label": "x", "params": {}})
            ).status_code == 403
            assert (await client.delete(f"/history/{uuid.uuid4()}")).status_code == 403
            assert (await client.delete("/history")).status_code == 403

    @pytest.mark.asyncio
    async def test_tc_h_2_add_and_list(self):
        """TC-H.2: POST persists an entry; GET returns it newest-first"""
        async with _make_client() as client:
            token = await _register_and_login(client)

            params = {"keyword": "python engineer", "states": ["California"], "has_email": True}
            created = await client.post(
                "/history",
                json={"label": "python engineer", "params": params},
                headers=_auth(token),
            )
            assert created.status_code == 201
            entry = created.json()
            assert set(entry.keys()) == {"id", "label", "params", "ts"}
            assert entry["label"] == "python engineer"
            assert entry["params"] == params
            assert isinstance(entry["ts"], int)

            listed = await client.get("/history", headers=_auth(token))
            assert listed.status_code == 200
            entries = listed.json()
            assert len(entries) == 1
            assert entries[0]["id"] == entry["id"]
            assert entries[0]["params"] == params

    @pytest.mark.asyncio
    async def test_tc_h_3_identical_params_bump_not_duplicate(self):
        """TC-H.3: Re-running identical params (any key order) bumps the entry"""
        async with _make_client() as client:
            token = await _register_and_login(client)

            first = await client.post(
                "/history",
                json={"label": "designer", "params": {"keyword": "designer", "has_linkedin": True}},
                headers=_auth(token),
            )
            assert first.status_code == 201

            # Same params, different key order and updated label
            second = await client.post(
                "/history",
                json={
                    "label": "designer (rerun)",
                    "params": {"has_linkedin": True, "keyword": "designer"},
                },
                headers=_auth(token),
            )
            assert second.status_code == 201

            assert second.json()["id"] == first.json()["id"]
            assert second.json()["ts"] >= first.json()["ts"]

            listed = await client.get("/history", headers=_auth(token))
            entries = listed.json()
            assert len(entries) == 1
            assert entries[0]["label"] == "designer (rerun)"

    @pytest.mark.asyncio
    async def test_tc_h_4_newest_first_ordering(self):
        """TC-H.4: Listing is newest-first; re-running moves an entry to the top"""
        async with _make_client() as client:
            token = await _register_and_login(client)

            for label in ["first", "second", "third"]:
                resp = await client.post(
                    "/history",
                    json={"label": label, "params": {"keyword": label}},
                    headers=_auth(token),
                )
                assert resp.status_code == 201

            # Re-run "first" — it should move to the top
            resp = await client.post(
                "/history",
                json={"label": "first", "params": {"keyword": "first"}},
                headers=_auth(token),
            )
            assert resp.status_code == 201

            listed = await client.get("/history", headers=_auth(token))
            labels = [e["label"] for e in listed.json()]
            assert labels == ["first", "third", "second"]

    @pytest.mark.asyncio
    async def test_tc_h_5_remove_entry(self):
        """TC-H.5: DELETE /history/{id} removes only that entry; 404 on repeat"""
        async with _make_client() as client:
            token = await _register_and_login(client)

            keep = await client.post(
                "/history",
                json={"label": "keep", "params": {"keyword": "keep"}},
                headers=_auth(token),
            )
            remove = await client.post(
                "/history",
                json={"label": "remove", "params": {"keyword": "remove"}},
                headers=_auth(token),
            )

            deleted = await client.delete(f"/history/{remove.json()['id']}", headers=_auth(token))
            assert deleted.status_code == 204

            listed = await client.get("/history", headers=_auth(token))
            assert [e["id"] for e in listed.json()] == [keep.json()["id"]]

            repeat = await client.delete(f"/history/{remove.json()['id']}", headers=_auth(token))
            assert repeat.status_code == 404

    @pytest.mark.asyncio
    async def test_tc_h_6_clear_history(self):
        """TC-H.6: DELETE /history empties the list and is idempotent"""
        async with _make_client() as client:
            token = await _register_and_login(client)

            for label in ["a", "b"]:
                await client.post(
                    "/history",
                    json={"label": label, "params": {"keyword": label}},
                    headers=_auth(token),
                )

            cleared = await client.delete("/history", headers=_auth(token))
            assert cleared.status_code == 204

            listed = await client.get("/history", headers=_auth(token))
            assert listed.json() == []

            # Clearing an empty history is still a success
            again = await client.delete("/history", headers=_auth(token))
            assert again.status_code == 204

    @pytest.mark.asyncio
    async def test_tc_h_7_user_isolation(self):
        """TC-H.7: Users can't see or delete each other's entries"""
        async with _make_client() as client:
            token_a = await _register_and_login(client)
            token_b = await _register_and_login(client)

            created = await client.post(
                "/history",
                json={"label": "private", "params": {"keyword": "private"}},
                headers=_auth(token_a),
            )
            entry_id = created.json()["id"]

            listed_b = await client.get("/history", headers=_auth(token_b))
            assert listed_b.json() == []

            stolen = await client.delete(f"/history/{entry_id}", headers=_auth(token_b))
            assert stolen.status_code == 404

            listed_a = await client.get("/history", headers=_auth(token_a))
            assert [e["id"] for e in listed_a.json()] == [entry_id]

    @pytest.mark.asyncio
    async def test_tc_h_8_validation(self):
        """TC-H.8: Blank labels and malformed entry ids are rejected"""
        async with _make_client() as client:
            token = await _register_and_login(client)

            blank = await client.post(
                "/history", json={"label": "   ", "params": {"keyword": "x"}}, headers=_auth(token)
            )
            assert blank.status_code == 422

            missing_params = await client.post(
                "/history", json={"label": "no params"}, headers=_auth(token)
            )
            assert missing_params.status_code == 422

            bad_id = await client.delete("/history/not-a-uuid", headers=_auth(token))
            assert bad_id.status_code == 422

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_tc_h_9_capped_at_50(self):
        """TC-H.9: History is trimmed to the 50 most recent entries"""
        async with _make_client() as client:
            token = await _register_and_login(client)

            for i in range(55):
                resp = await client.post(
                    "/history",
                    json={"label": f"search {i}", "params": {"keyword": f"search {i}"}},
                    headers=_auth(token),
                )
                assert resp.status_code == 201

            listed = await client.get("/history", headers=_auth(token))
            entries = listed.json()
            assert len(entries) == 50
            # Oldest five were trimmed; newest survives at the top
            assert entries[0]["label"] == "search 54"
            assert all(e["label"] not in {f"search {i}" for i in range(5)} for e in entries)

    @pytest.mark.asyncio
    async def test_tc_h_10_cleanup(self):
        """TC-H.10: Remove throwaway users (cascade deletes their history)"""
        pool = await database.get_pool()
        deleted = await pool.execute("DELETE FROM users WHERE username LIKE 'histtest_%'")
        print(f"✅ Cleanup: {deleted}")

        remaining = await pool.fetchval(
            "SELECT COUNT(*) FROM search_history sh JOIN users u ON u.id = sh.user_id "
            "WHERE u.username LIKE 'histtest_%'"
        )
        assert remaining == 0
