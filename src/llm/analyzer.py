import json
from datetime import datetime

import anthropic
from tenacity import retry, stop_after_attempt, wait_fixed

from src.config import settings

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

_SYSTEM = (
    "You are an SRE incident analyst. You receive structured context about a production alert "
    "and output a root cause analysis. Be specific, not generic. If evidence is weak, say so. "
    "Output valid JSON only — no markdown fences, no extra text."
)

_OUTPUT_SCHEMA = """{
  "root_cause": "<1-2 sentence plain-English cause>",
  "confidence": "high|medium|low",
  "confidence_reason": "<why this confidence level>",
  "evidence": ["<signal 1>", "<signal 2>"],
  "suggested_fix": "<one actionable step>",
  "deploy_suspect": {"commit_sha": "", "author": "", "message": ""} or null,
  "similar_past_incident_id": "<uuid>" or null
}"""


def _fmt_commits(commits: list[dict]) -> str:
    if not commits:
        return "No deployments in the last 2 hours."
    return "\n".join(
        f"- [{c['sha']}] {c['minutes_before_alert']}min before alert | {c['author']}: {c['message']}"
        for c in commits
    )


def _fmt_anomalies(anomalies: list[str]) -> str:
    return "\n".join(f"- {a}" for a in anomalies) if anomalies else "No significant metric anomalies detected."


def _fmt_past(past: list | None) -> str:
    if not past:
        return "No similar incidents on record."
    return "\n".join(
        f"- [{p['id']}] {p['root_cause']} | Fix: {p['suggested_fix']}" for p in past
    )


@retry(stop=stop_after_attempt(2), wait=wait_fixed(5))
async def analyze_incident(
    service_name: str,
    alert_title: str,
    severity: str,
    alert_time: datetime,
    commits: list[dict],
    anomalies: list[str],
    past_incidents: list | None = None,
) -> dict:
    prompt = f"""INCIDENT
Service: {service_name}
Alert: {alert_title}
Severity: {severity}
Time: {alert_time.strftime('%Y-%m-%d %H:%M:%S')} UTC

RECENT DEPLOYMENTS (last 2 hours, newest first)
{_fmt_commits(commits)}

METRIC ANOMALIES (last 60 minutes)
{_fmt_anomalies(anomalies)}

PAST SIMILAR INCIDENTS
{_fmt_past(past_incidents)}

Respond with JSON matching this schema exactly:
{_OUTPUT_SCHEMA}"""

    response = await _client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=600,
        temperature=0,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    result = json.loads(text)
    result["_usage"] = {
        "model": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return result
