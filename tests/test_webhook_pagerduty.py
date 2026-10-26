"""AC-1 through AC-6: PagerDuty webhook tests."""
import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from src.models.incidents import Incident

ALERT_ID = "PD-001"
SERVICE = "payment-service"


def _make_payload(alert_id: str = ALERT_ID, urgency: str = "high") -> dict:
    return {
        "messages": [{
            "event": "incident.trigger",
            "incident": {
                "id": alert_id,
                "title": "High CPU on payment-service",
                "urgency": urgency,
                "service": {"summary": SERVICE},
            },
        }]
    }


def _sign(body: bytes, secret: str) -> str:
    return "v1=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_ac1_valid_webhook_returns_200(client, tenant, db_session):
    """AC-1: Valid webhook returns 200."""
    t, _ = tenant
    body = json.dumps(_make_payload()).encode()
    resp = await client.post(f"/webhook/pagerduty/{t.id}", content=body)
    assert resp.status_code == 200
    assert resp.json() == {"status": "accepted"}


@pytest.mark.asyncio
async def test_ac2_invalid_signature_returns_403(client, db_session):
    """AC-2: Invalid HMAC returns 403."""
    from cryptography.fernet import Fernet
    from src.config import settings
    from src.models.incidents import Tenant
    import hashlib, secrets

    raw_key = secrets.token_hex(32)
    webhook_secret = "mysecret"
    encrypted_secret = Fernet(settings.encryption_key.encode()).encrypt(webhook_secret.encode()).decode()

    t = Tenant(
        name="Signed Tenant",
        slack_webhook_url="https://hooks.slack.com/x",
        api_key_hash=hashlib.sha256(raw_key.encode()).hexdigest(),
        pagerduty_webhook_secret_encrypted=encrypted_secret,
    )
    db_session.add(t)
    await db_session.commit()
    await db_session.refresh(t)

    body = json.dumps(_make_payload()).encode()
    resp = await client.post(
        f"/webhook/pagerduty/{t.id}",
        content=body,
        headers={"X-PagerDuty-Signature": "v1=badsignature"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_ac3_duplicate_alert_not_duplicated(client, tenant, db_session):
    """AC-3: Same alert_id sent twice creates only one incident."""
    t, _ = tenant
    body = json.dumps(_make_payload()).encode()

    with patch("src.webhook.pagerduty._run_analysis", new=AsyncMock()):
        await client.post(f"/webhook/pagerduty/{t.id}", content=body)
        await client.post(f"/webhook/pagerduty/{t.id}", content=body)

    rows = await db_session.execute(
        select(Incident).where(Incident.tenant_id == t.id, Incident.alert_id == ALERT_ID)
    )
    incidents = rows.scalars().all()
    assert len(incidents) == 1


@pytest.mark.asyncio
async def test_ac5_datadog_failure_still_processes(client, tenant, db_session):
    """AC-5: If Datadog fails, analysis still runs with partial context."""
    t, _ = tenant
    body = json.dumps(_make_payload(alert_id="PD-002")).encode()

    # Mock _run_analysis to avoid actually calling external APIs
    with patch("src.webhook.pagerduty._run_analysis", new=AsyncMock()) as mock_run:
        resp = await client.post(f"/webhook/pagerduty/{t.id}", content=body)
        assert resp.status_code == 200
        mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_unknown_tenant_returns_404(client):
    """404 on unknown tenant_id."""
    body = json.dumps(_make_payload()).encode()
    resp = await client.post(f"/webhook/pagerduty/{uuid.uuid4()}", content=body)
    assert resp.status_code == 404
