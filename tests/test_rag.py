"""Tests for RAG embeddings and retrieval. AC-11."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_embed_text_returns_1024_floats():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"embedding": [0.1] * 1024}]}
    mock_resp.raise_for_status = MagicMock()

    with patch("src.rag.embeddings.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)
        from src.rag.embeddings import embed_text
        result = await embed_text("payment service latency spike")

    assert isinstance(result, list)
    assert len(result) == 1024
    assert all(isinstance(v, float) for v in result)


def test_incident_text_concatenates_fields():
    from src.rag.embeddings import incident_text
    text = incident_text("DB timeout", "payment-svc", "connection pool exhausted", ["CPU 90%", "errors spiked"])
    assert "DB timeout" in text
    assert "payment-svc" in text
    assert "connection pool exhausted" in text
    assert "CPU 90%" in text


@pytest.mark.asyncio
async def test_find_similar_incidents_empty_when_no_resolved(tmp_path):
    """When no resolved incidents exist, returns empty list."""
    import uuid
    mock_db = AsyncMock()
    mock_db.execute.return_value.fetchall.return_value = []

    from src.rag.retrieval import find_similar_incidents
    result = await find_similar_incidents(
        db=mock_db,
        tenant_id=uuid.uuid4(),
        embedding=[0.1] * 1024,
        exclude_incident_id=uuid.uuid4(),
    )
    assert result == []


@pytest.mark.asyncio
async def test_generate_postmortem_contains_required_sections():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="## Summary\n## Impact\n## Timeline\n## Root Cause\n## Contributing Factors\n## Action Items")]

    with patch("src.postmortem.generator._client") as mock_client:
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        from src.postmortem.generator import generate_postmortem

        incident = MagicMock()
        incident.service_name = "payment-svc"
        incident.alert_title = "High latency"
        incident.severity = "high"
        incident.started_at.strftime = MagicMock(return_value="2025-10-08 14:30:00")
        incident.resolved_at.strftime = MagicMock(return_value="2025-10-08 14:50:00")

        analysis = MagicMock()
        analysis.root_cause = "DB connection pool exhausted"
        analysis.confidence = "high"
        analysis.evidence = ["CPU 90%"]
        analysis.suggested_fix = "Increase pool size"
        analysis.deploy_suspect = None

        result = await generate_postmortem(incident, analysis, 20)

    for section in ["## Summary", "## Impact", "## Timeline", "## Root Cause", "## Contributing Factors", "## Action Items"]:
        assert section in result
