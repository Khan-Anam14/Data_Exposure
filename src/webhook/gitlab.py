import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.models.incidents import DeployEvent, Tenant

router = APIRouter()


@router.post("/gitlab/{tenant_id}")
async def gitlab_webhook(
    tenant_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_gitlab_token: str = Header(default=""),
):
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if tenant.opsgenie_webhook_secret_encrypted:
        from cryptography.fernet import Fernet
        from src.config import settings
        expected = Fernet(settings.encryption_key.encode()).decrypt(
            tenant.opsgenie_webhook_secret_encrypted.encode()
        ).decode()
        if not x_gitlab_token == expected:
            raise HTTPException(status_code=403, detail="Invalid token")

    body = await request.body()
    payload = json.loads(body)

    if payload.get("event_name") != "push":
        return {"status": "ignored"}

    commits = [
        {
            "sha": c.get("id", "")[:8],
            "message": c.get("message", "").split("\n")[0][:120],
            "author": c.get("author", {}).get("name", "unknown"),
            "timestamp": c.get("timestamp", ""),
        }
        for c in payload.get("commits", [])
    ]

    service_name = payload.get("project", {}).get("name", "unknown").lower().replace(" ", "-")

    event = DeployEvent(
        tenant_id=tenant_id,
        source="gitlab",
        service_name=service_name,
        commits=commits,
        pushed_at=datetime.now(timezone.utc),
    )
    db.add(event)
    await db.commit()

    return {"status": "accepted", "commits_stored": len(commits)}
