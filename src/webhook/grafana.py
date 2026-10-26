import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.models.incidents import Incident, Tenant

router = APIRouter()


@router.post("/grafana/{tenant_id}")
async def grafana_webhook(
    tenant_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()

    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    payload = json.loads(body)

    # Grafana unified alerting format
    for alert in payload.get("alerts", []):
        if alert.get("status") != "firing":
            continue

        labels = alert.get("labels", {})
        alert_id = alert.get("fingerprint", "")
        if not alert_id:
            continue

        existing = await db.execute(
            select(Incident).where(
                Incident.tenant_id == tenant_id,
                Incident.alert_id == alert_id,
            )
        )
        if existing.scalar_one_or_none():
            continue

        service = labels.get("service", labels.get("job", "unknown-service")).lower()
        title = alert.get("annotations", {}).get("summary", labels.get("alertname", "Grafana alert"))
        severity = labels.get("severity", "high").lower()

        incident = Incident(
            tenant_id=tenant_id,
            alert_source="grafana",
            alert_id=alert_id,
            service_name=service,
            alert_title=title,
            severity=severity,
            status="active",
            started_at=datetime.now(timezone.utc),
            raw_alert=alert,
        )
        db.add(incident)
        await db.commit()
        await db.refresh(incident)

        from src.tasks.analysis import run_analysis_task
        run_analysis_task.delay(str(incident.id), str(tenant_id), service)

    return {"status": "accepted"}
