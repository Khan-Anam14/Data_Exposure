import json
from datetime import datetime

import anthropic
from src.config import settings

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

_SYSTEM = (
    "You are a senior SRE writing a blameless postmortem. "
    "Output only the Markdown document — no preamble, no fences."
)


async def generate_postmortem(
    service_name: str,
    alert_title: str,
    root_cause: str,
    evidence: list[str],
    suggested_fix: str,
    started_at: datetime,
    resolved_at: datetime | None,
) -> str:
    duration = (
        f"{int((resolved_at - started_at).total_seconds() / 60)} minutes"
        if resolved_at else "ongoing"
    )

    prompt = f"""Generate a blameless postmortem for this incident:

Service: {service_name}
Title: {alert_title}
Duration: {duration}
Started: {started_at.strftime('%Y-%m-%d %H:%M UTC')}
Root Cause: {root_cause}
Evidence: {chr(10).join(f'- {e}' for e in evidence)}
Suggested Fix Applied: {suggested_fix}

Write a postmortem with these sections:
# Postmortem: {alert_title}
## Summary
## Impact
## Timeline
## Root Cause
## Contributing Factors
## Action Items
"""

    response = await _client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1200,
        temperature=0,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
