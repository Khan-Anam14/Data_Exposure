"""Tests for postmortem generation. AC-12."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_incident(status="resolved"):
    i = MagicMock()
    i.id = "test-incident-id"
    i.service_name = "checkout-svc"
    i.alert_title = "Payment timeout P1"
    i.severity = "high"
    i.status = status
    i.started_at.strftime = MagicMock(return_value="2025-10-08 14:30:00")
    i.resolved_at.strftime = MagicMock(return_value="2025-10-08 14:55:00")
    return i


def _make_analysis():
    a = MagicMock()
    a.root_cause = "DB connection pool exhausted after deploy abc123"
    a.confidence = "high"
    a.evidence = ["CPU spiked to 92%", "error rate +400%"]
    a.suggested_fix = "Increase pool size from 10 to 25 in checkout-svc config"
    a.deploy_suspect = {"commit_sha": "abc123", "author": "dev", "message": "increase pool"}
    return a


@pytest.mark.asyncio
async def test_postmortem_contains_all_sections():
    sections = ["## Summary", "## Impact", "## Timeline", "## Root Cause", "## Contributing Factors", "## Action Items"]
    mock_markdown = "\n".join(sections) + "\n- [ ] Fix pool [Team TBD]"

    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text=mock_markdown)]

    with patch("src.postmortem.generator._client") as mc:
        mc.messages.create = AsyncMock(return_value=mock_resp)
        from src.postmortem.generator import generate_postmortem
        result = await generate_postmortem(_make_incident(), _make_analysis(), 25)

    for s in sections:
        assert s in result, f"Missing section: {s}"


@pytest.mark.asyncio
async def test_postmortem_includes_action_items():
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text="## Action Items\n- [ ] Increase pool size [Team TBD]\n- [ ] Add alerting [Team TBD]")]

    with patch("src.postmortem.generator._client") as mc:
        mc.messages.create = AsyncMock(return_value=mock_resp)
        from src.postmortem.generator import generate_postmortem
        result = await generate_postmortem(_make_incident(), _make_analysis(), 25)

    assert "[Team TBD]" in result
    assert "## Action Items" in result
