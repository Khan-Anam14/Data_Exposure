import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def find_similar(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    exclude_incident_id: uuid.UUID,
    embedding: list[float],
    threshold: float = 0.20,  # cosine distance (lower = more similar)
    limit: int = 2,
) -> list[dict]:
    """pgvector ivfflat cosine similarity search for past resolved incidents."""
    vector_str = "[" + ",".join(str(v) for v in embedding) + "]"
    result = await db.execute(
        text("""
            SELECT i.id, a.root_cause, a.suggested_fix, i.started_at,
                   (i.embedding <=> :embedding::vector) AS distance
            FROM incidents i
            JOIN analyses a ON a.incident_id = i.id
            WHERE i.tenant_id = :tenant_id
              AND i.status = 'resolved'
              AND i.id != :exclude_id
              AND i.embedding IS NOT NULL
              AND (i.embedding <=> :embedding::vector) < :threshold
            ORDER BY distance ASC
            LIMIT :limit
        """),
        {
            "embedding": vector_str,
            "tenant_id": str(tenant_id),
            "exclude_id": str(exclude_incident_id),
            "threshold": threshold,
            "limit": limit,
        },
    )
    rows = result.fetchall()
    return [
        {"id": str(r.id), "root_cause": r.root_cause, "suggested_fix": r.suggested_fix}
        for r in rows
    ]
