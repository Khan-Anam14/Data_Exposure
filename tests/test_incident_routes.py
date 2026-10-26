"""Incident routes: pagination, tenant isolation, postmortem field."""
import uuid
from datetime import datetime, timezone

import pytest

from src.models.incidents import Analysis, Incident


async def _make_incident(db_session, tenant_id, alert_id: str = "X-1") -> Incident:
    i = Incident(
        tenant_id=tenant_id,
        alert_source="pagerduty",
        alert_id=alert_id,
        service_name="checkout",
        alert_title="Test alert",
        severity="high",
        status="active",
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(i)
    await db_session.commit()
    await db_session.refresh(i)
    return i


@pytest.mark.asyncio
async def test_list_incidents_paginated(client, tenant, db_session):
    """GET /incidents returns paginated list for the tenant."""
    t, raw_key = tenant
    for i in range(3):
        await _make_incident(db_session, t.id, f"INC-{i}")

    resp = await client.get("/incidents?page=1&limit=2", headers={"X-API-Key": raw_key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["limit"] == 2


@pytest.mark.asyncio
async def test_get_incident_with_analysis(client, tenant, db_session):
    """GET /incidents/{id} returns incident + analysis."""
    t, raw_key = tenant
    inc = await _make_incident(db_session, t.id, "INC-ANA")

    analysis = Analysis(
        incident_id=inc.id,
        root_cause="DB connection pool exhausted",
        confidence="high",
        confidence_reason="Clear metric spike correlates with deploy",
        evidence=["CPU spike 22% → 87%"],
        suggested_fix="Increase pool size to 50",
    )
    db_session.add(analysis)
    await db_session.commit()

    resp = await client.get(f"/incidents/{inc.id}", headers={"X-API-Key": raw_key})
    assert resp.status_code == 200
    data = resp.json()
    assert data["incident"]["id"] == str(inc.id)
    assert data["analysis"]["root_cause"] == "DB connection pool exhausted"
    assert data["analysis"]["confidence"] == "high"


@pytest.mark.asyncio
async def test_get_incident_cross_tenant_returns_404(client, tenant, db_session):
    """Getting another tenant's incident returns 404."""
    import hashlib, secrets
    from src.models.incidents import Tenant

    # Create second tenant
    raw2 = secrets.token_hex(32)
    t2 = Tenant(
        name="Other",
        slack_webhook_url="https://x.com",
        api_key_hash=hashlib.sha256(raw2.encode()).hexdigest(),
    )
    db_session.add(t2)
    await db_session.commit()
    await db_session.refresh(t2)

    # Incident belongs to t2
    inc = await _make_incident(db_session, t2.id, "INC-OTHER")

    _, raw_key = tenant  # t1's key
    resp = await client.get(f"/incidents/{inc.id}", headers={"X-API-Key": raw_key})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_incident_404(client, tenant):
    _, raw_key = tenant
    resp = await client.get(f"/incidents/{uuid.uuid4()}", headers={"X-API-Key": raw_key})
    assert resp.status_code == 404
