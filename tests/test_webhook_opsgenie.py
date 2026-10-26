"""OpsGenie webhook tests."""
import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from src.models.incidents import Incident


def _og_payload(alert_id: str, priority: str = "P1", entity: str = "checkout") -> dict:
    return {
        "action": "Create",
        "alert": {
            "alertId": alert_id,
            "message": f"Alert on {entity}",
            "priority": priority,
            "entity": entity,
        },
    }


@pytest.mark.asyncio
async def test_p1_creates_high_severity(client, tenant, db_session):
    """P1 alert creates incident with severity=high."""
    t, _ = tenant
    body = json.dumps(_og_payload("OG-001", "P1")).encode()

    with patch("src.webhook.opsgenie.run_analysis", new=AsyncMock()):
        resp = await client.post(f"/webhook/opsgenie/{t.id}", content=body)
    assert resp.status_code == 200

    row = await db_session.execute(
        select(Incident).where(Incident.tenant_id == t.id, Incident.alert_id == "OG-001")
    )
    incident = row.scalar_one_or_none()
    assert incident is not None
    assert incident.severity == "high"
    assert incident.alert_source == "opsgenie"


@pytest.mark.asyncio
async def test_p4_creates_low_severity(client, tenant, db_session):
    """P4 alert creates incident with severity=low."""
    t, _ = tenant
    body = json.dumps(_og_payload("OG-002", "P4")).encode()

    with patch("src.webhook.opsgenie.run_analysis", new=AsyncMock()):
        resp = await client.post(f"/webhook/opsgenie/{t.id}", content=body)
    assert resp.status_code == 200

    row = await db_session.execute(
        select(Incident).where(Incident.tenant_id == t.id, Incident.alert_id == "OG-002")
    )
    incident = row.scalar_one_or_none()
    assert incident.severity == "low"


@pytest.mark.asyncio
async def test_duplicate_deduplication(client, tenant, db_session):
    """Same alert_id sent twice creates only one incident."""
    t, _ = tenant
    body = json.dumps(_og_payload("OG-DUP")).encode()

    with patch("src.webhook.opsgenie.run_analysis", new=AsyncMock()):
        await client.post(f"/webhook/opsgenie/{t.id}", content=body)
        await client.post(f"/webhook/opsgenie/{t.id}", content=body)

    rows = await db_session.execute(
        select(Incident).where(Incident.tenant_id == t.id, Incident.alert_id == "OG-DUP")
    )
    assert len(rows.scalars().all()) == 1


@pytest.mark.asyncio
async def test_unknown_tenant_404(client):
    body = json.dumps(_og_payload("OG-X")).encode()
    resp = await client.post(f"/webhook/opsgenie/{uuid.uuid4()}", content=body)
    assert resp.status_code == 404
