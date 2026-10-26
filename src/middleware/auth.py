import hashlib

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.models.incidents import Tenant


async def require_api_key(
    x_api_key: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    result = await db.execute(select(Tenant).where(Tenant.api_key_hash == key_hash))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    return tenant
