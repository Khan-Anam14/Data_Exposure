import hashlib
import secrets
import uuid

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.session import get_db
from src.models.incidents import Tenant

router = APIRouter(prefix="/tenants", tags=["tenants"])


def _encrypt(value: str) -> str:
    return Fernet(settings.encryption_key.encode()).encrypt(value.encode()).decode()


class TenantCreate(BaseModel):
    name: str
    slack_webhook_url: str
    github_org: str | None = None
    github_repo: str | None = None
    github_pat: str | None = None
    datadog_api_key: str | None = None
    datadog_app_key: str | None = None
    pagerduty_webhook_secret: str | None = None
    opsgenie_webhook_secret: str | None = None


@router.post("", status_code=201)
async def create_tenant(body: TenantCreate, db: AsyncSession = Depends(get_db)):
    api_key = secrets.token_hex(32)
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    tenant = Tenant(
        name=body.name,
        slack_webhook_url=body.slack_webhook_url,
        api_key_hash=api_key_hash,
        github_org=body.github_org,
        github_repo=body.github_repo,
        github_pat_encrypted=_encrypt(body.github_pat) if body.github_pat else None,
        datadog_api_key_encrypted=_encrypt(body.datadog_api_key) if body.datadog_api_key else None,
        datadog_app_key_encrypted=_encrypt(body.datadog_app_key) if body.datadog_app_key else None,
        pagerduty_webhook_secret_encrypted=_encrypt(body.pagerduty_webhook_secret) if body.pagerduty_webhook_secret else None,
        opsgenie_webhook_secret_encrypted=_encrypt(body.opsgenie_webhook_secret) if body.opsgenie_webhook_secret else None,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    tid = str(tenant.id)
    base = settings.base_url.rstrip("/")
    return {
        "tenant_id": tid,
        "api_key": api_key,
        "webhook_urls": {
            "pagerduty": f"{base}/webhook/pagerduty/{tid}",
            "opsgenie": f"{base}/webhook/opsgenie/{tid}",
            "grafana": f"{base}/webhook/grafana/{tid}",
            "gitlab": f"{base}/webhook/gitlab/{tid}",
        },
    }
