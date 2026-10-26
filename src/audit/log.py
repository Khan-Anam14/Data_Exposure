import hashlib
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.incidents import AuditLog


async def write_audit_log(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    event_type: str,
    llm_model: str | None = None,
    prompt: str | None = None,
    output: str | None = None,
    metadata: dict | None = None,
) -> None:
    entry = AuditLog(
        tenant_id=tenant_id,
        event_type=event_type,
        llm_model=llm_model,
        prompt_hash=hashlib.sha256(prompt.encode()).hexdigest() if prompt else None,
        output_hash=hashlib.sha256(output.encode()).hexdigest() if output else None,
        metadata_=metadata,
    )
    db.add(entry)
    # Caller is responsible for commit
