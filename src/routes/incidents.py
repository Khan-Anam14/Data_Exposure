import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.middleware.auth import require_api_key
from src.models.incidents import Analysis, Incident, Postmortem, Tenant

router = APIRouter(prefix="/incidents")


def _incident_dict(i: Incident) -> dict:
    return {
        "id": str(i.id),
        "service_name": i.service_name,
        "alert_title": i.alert_title,
        "severity": i.severity,
        "status": i.status,
        "alert_source": i.alert_source,
        "started_at": i.started_at.isoformat(),
        "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None,
    }


@router.get("")
async def list_incidents(
    page: int = 1,
    limit: int = 20,
    status: str | None = None,
    tenant: Tenant = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    limit = min(limit, 100)
    q = select(Incident).where(Incident.tenant_id == tenant.id)
    if status:
        q = q.where(Incident.status == status)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(q.order_by(Incident.started_at.desc()).offset((page - 1) * limit).limit(limit))
    items = [_incident_dict(i) for i in rows.scalars()]

    return {"items": items, "total": total, "page": page, "limit": limit}


@router.get("/{incident_id}")
async def get_incident(
    incident_id: uuid.UUID,
    tenant: Tenant = Depends(require_api_key),
    db: AsyncSession = Depends(get_db),
):
    incident = await db.get(Incident, incident_id)
    if not incident or incident.tenant_id != tenant.id:
        raise HTTPException(status_code=404, detail="Incident not found")

    analysis = (await db.execute(select(Analysis).where(Analysis.incident_id == incident_id))).scalar_one_or_none()
    postmortem = (await db.execute(select(Postmortem).where(Postmortem.incident_id == incident_id))).scalar_one_or_none()

    return {
        "incident": _incident_dict(incident),
        "analysis": {
            "root_cause": analysis.root_cause,
            "confidence": analysis.confidence,
            "confidence_reason": analysis.confidence_reason,
            "evidence": analysis.evidence or [],
            "suggested_fix": analysis.suggested_fix,
            "deploy_suspect": analysis.deploy_suspect,
            "llm_model": analysis.llm_model,
            "created_at": analysis.created_at.isoformat(),
        } if analysis else None,
        "postmortem": {
            "draft_markdown": postmortem.draft_markdown,
            "created_at": postmortem.created_at.isoformat(),
        } if postmortem else None,
    }
