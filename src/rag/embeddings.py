import httpx
from src.config import settings


async def embed(text: str) -> list[float]:
    """Voyage AI voyage-3-lite — 1024 dims, cheapest option."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.voyageai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {settings.voyage_api_key}"},
            json={"model": "voyage-3-lite", "input": [text]},
        )
        resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


def incident_text(alert_title: str, service_name: str, root_cause: str, evidence: list) -> str:
    evidence_str = " ".join(evidence or [])
    return f"{alert_title} {service_name} {root_cause} {evidence_str}"
