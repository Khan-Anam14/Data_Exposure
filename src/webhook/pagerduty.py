import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.session import get_db
from src.models.incidents import Incident, Tenant

router = APIRouter()


def _decrypt(value: str) -> str:
    from cryptography.fernet import Fernet
    return Fernet(settings.encryption_key.encode()).decrypt(value.encode()).decode()


def _verify_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = "v1=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _service_name(incident_data: dict) -> str:
    return (
        incident_data.get("service", {})
        .get("summary", "unknown-service")
        .lower()
        .replace(" ", "-")
    )


@router.post("/pagerduty/{tenant_id}")
async def pagerduty_webhook(
    tenant_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_pagerduty_signature: str = Header(default=""),
):
    body = await request.body()

    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if tenant.pagerduty_webhook_secret_encrypted:
        secret = _decrypt(tenant.pagerduty_webhook_secret_encrypted)
        if not _verify_signature(body, x_pagerduty_signature, secret):
            raise HTTPException(status_code=403, detail="Invalid signature")

    payload = json.loads(body)

    for message in payload.get("messages", []):
        event_type = message.get("event", "")
        incident_data = message.get("incident", {})
        alert_id = incident_data.get("id", "")

        if not alert_id:
            continue

        if event_type == "incident.resolve":
            await _mark_resolved(db, tenant_id, alert_id)
            continue

        existing = await db.execute(
            select(Incident).where(
                Incident.tenant_id == tenant_id,
                Incident.alert_id == alert_id,
            )
        )
        if existing.scalar_one_or_none():
            continue

        service = _service_name(incident_data)
        incident = Incident(
            tenant_id=tenant_id,
            alert_source="pagerduty",
            alert_id=alert_id,
            service_name=service,
            alert_title=incident_data.get("title", "Unknown incident"),
            severity=incident_data.get("urgency", "high"),
            status="active",
            started_at=datetime.now(timezone.utc),
            raw_alert=incident_data,
        )
        db.add(incident)
        await db.commit()
        await db.refresh(incident)

        from src.tasks.analysis import run_analysis_task
        run_analysis_task.delay(str(incident.id), str(tenant_id), service)

    return {"status": "accepted"}


async def _mark_resolved(db: AsyncSession, tenant_id: uuid.UUID, alert_id: str):
    result = await db.execute(
        select(Incident).where(
            Incident.tenant_id == tenant_id,
            Incident.alert_id == alert_id,
        )
    )
    incident = result.scalar_one_or_none()
    if incident and incident.status == "active":
        incident.status = "resolved"
        incident.resolved_at = datetime.now(timezone.utc)
        await db.commit()
