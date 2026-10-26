"""AC-9, AC-10: API key authentication tests."""
import pytest


@pytest.mark.asyncio
async def test_ac9_no_api_key_returns_401(client):
    """AC-9: GET /incidents without X-API-Key returns 401."""
    resp = await client.get("/incidents")
    assert resp.status_code == 401
    assert "Missing or invalid API key" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_wrong_api_key_returns_401(client):
    resp = await client.get("/incidents", headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ac10_valid_key_returns_200(client, tenant):
    """AC-10: Valid X-API-Key returns 200 with tenant's data."""
    _, raw_key = tenant
    resp = await client.get("/incidents", headers={"X-API-Key": raw_key})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
