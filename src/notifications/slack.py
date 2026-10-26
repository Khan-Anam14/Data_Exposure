import httpx

_CONFIDENCE_EMOJI = {"high": "🟢", "medium": "🟡", "low": "🔴"}


async def post_to_slack(
    webhook_url: str,
    alert_title: str,
    severity: str,
    analysis: dict,
    elapsed_seconds: float,
) -> bool:
    confidence = analysis.get("confidence", "low")
    evidence = "\n".join(f"• {e}" for e in (analysis.get("evidence") or []))
    deploy = analysis.get("deploy_suspect")
    deploy_line = (
        f"🐙 Suspect: `{deploy['commit_sha']}` by {deploy['author']} — \"{deploy['message']}\""
        if deploy else "🐙 No suspect deploy identified"
    )

    payload = {
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"🚨 Incident: {alert_title}"}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Severity:* {severity.upper()}\n"
                        f"*Root Cause* {_CONFIDENCE_EMOJI.get(confidence, '⚪')} `{confidence} confidence`:\n"
                        f"{analysis.get('root_cause', 'Analysis unavailable')}"
                    ),
                },
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Evidence:*\n{evidence or 'No signals captured'}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Suggested Fix:*\n{analysis.get('suggested_fix', 'N/A')}"}},
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": deploy_line},
                    {"type": "mrkdwn", "text": f"_Analysis in {elapsed_seconds:.1f}s_"},
                ],
            },
        ]
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(webhook_url, json=payload)
        return resp.status_code == 200
