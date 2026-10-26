import pytest
from cryptography.fernet import Fernet
from unittest.mock import patch


@pytest.mark.asyncio
async def test_create_tenant_returns_201(client):
    resp = await client.post(
        "/tenants",
        json={"name": "Acme Corp", "slack_webhook_url": "https://hooks.slack.com/xxx"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "tenant_id" in data
    assert "api_key" in data
    assert len(data["api_key"]) == 64  # secrets.token_hex(32)
    assert "pagerduty" in data["webhook_urls"]
    assert data["tenant_id"] in data["webhook_urls"]["pagerduty"]


@pytest.mark.asyncio
async def test_create_tenant_missing_name_returns_422(client):
    resp = await client.post(
        "/tenants",
        json={"slack_webhook_url": "https://hooks.slack.com/xxx"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_tenant_missing_slack_url_returns_422(client):
    resp = await client.post("/tenants", json={"name": "Acme Corp"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_tenant_api_key_usable_for_auth(client):
    # Create tenant
    resp = await client.post(
        "/tenants",
        json={"name": "Auth Test", "slack_webhook_url": "https://hooks.slack.com/xxx"},
    )
    assert resp.status_code == 201
    api_key = resp.json()["api_key"]

    # Use returned key to hit authenticated endpoint
    resp2 = await client.get("/incidents", headers={"X-API-Key": api_key})
    assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_create_tenant_without_api_key_returns_401(client):
    resp = await client.get("/incidents")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_tenant_with_credentials_encrypts_them(client):
    """Credentials must not appear in plaintext in the response."""
    fernet_key = Fernet.generate_key().decode()

    with patch("src.routes.tenants.settings") as mock_settings:
        mock_settings.encryption_key = fernet_key
        mock_settings.base_url = "http://localhost:8000"

        resp = await client.post(
            "/tenants",
            json={
                "name": "Secure Corp",
                "slack_webhook_url": "https://hooks.slack.com/xxx",
                "github_pat": "ghp_supersecrettoken",
            },
        )

    assert resp.status_code == 201
    # Raw PAT must not appear anywhere in the response
    assert "ghp_supersecrettoken" not in resp.text
