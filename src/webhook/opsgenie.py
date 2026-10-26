import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.models.incidents import Incident, Tenant
from src.webhook._shared import run_analysis

router = APIRouter()

# Per spec FR-11: P1/P2 → high, P3/P4/P5 → low
_PRIORITY_MAP = {"P1": "high", "P2": "high", "P3": "low", "P4": "low", "P5": "low"}


@router.post("/opsgenie/{tenant_id}")
async def opsgenie_webhook(
    tenant_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    payload = json.loads(body)
    action = payload.get("action", "")
    if action not in ("Create", "Acknowledge"):
        return {"status": "ignored"}

    alert = payload.get("alert", {})
    alert_id = alert.get("alertId", "")
    if not alert_id:
        return {"status": "accepted"}

    existing = await db.execute(
        select(Incident).where(Incident.tenant_id == tenant_id, Incident.alert_id == alert_id)
    )
    if existing.scalar_one_or_none():
        return {"status": "accepted"}

    service_name = (alert.get("entity") or "unknown-service").lower().replace(" ", "-")
    severity = _PRIORITY_MAP.get(alert.get("priority", "P3"), "low")

    incident = Incident(
        tenant_id=tenant_id,
        alert_source="opsgenie",
        alert_id=alert_id,
        service_name=service_name,
        alert_title=alert.get("message", "OpsGenie alert"),
        severity=severity,
        status="active",
        started_at=datetime.now(timezone.utc),
        raw_alert=alert,
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)
    background_tasks.add_task(run_analysis, incident.id, tenant.id, service_name)

    return {"status": "accepted"}
