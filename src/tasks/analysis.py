import asyncio
import time
import uuid

from celery_app import celery


@celery.task(name="src.tasks.analysis.run_analysis_task", bind=True, max_retries=2, default_retry_delay=5)
def run_analysis_task(self, incident_id_str: str, tenant_id_str: str, service_name: str):
    """Celery task wrapping the async analysis pipeline."""
    asyncio.run(_async_analysis(uuid.UUID(incident_id_str), uuid.UUID(tenant_id_str), service_name))


async def _async_analysis(incident_id: uuid.UUID, tenant_id: uuid.UUID, service_name: str):
    import time
    from src.db.session import AsyncSessionLocal
    from src.models.incidents import Analysis, ContextSnapshot, Incident, Tenant
    from src.context.fetchers import gather_context
    from src.llm.analyzer import analyze_incident
    from src.notifications.slack import post_to_slack

    async with AsyncSessionLocal() as db:
        incident = await db.get(Incident, incident_id)
        tenant = await db.get(Tenant, tenant_id)
        if not incident or not tenant:
            return

        started = time.monotonic()
        commits, anomalies = await gather_context(service_name, incident.started_at, tenant)

        db.add(ContextSnapshot(
            incident_id=incident_id, commits=commits,
            metric_anomalies=anomalies, similar_incidents=[],
        ))

        try:
            result = await analyze_incident(
                service_name=service_name, alert_title=incident.alert_title,
                severity=incident.severity, alert_time=incident.started_at,
                commits=commits, anomalies=anomalies,
            )
        except Exception as exc:
            result = {
                "root_cause": "AI analysis failed — review context snapshot.",
                "confidence": "low", "confidence_reason": str(exc),
                "evidence": [f"Commits: {len(commits)}", f"Anomalies: {len(anomalies)}"],
                "suggested_fix": "Check context snapshot for raw signals.",
                "deploy_suspect": None, "similar_past_incident_id": None, "_usage": {},
            }

        usage = result.pop("_usage", {})
        db.add(Analysis(
            incident_id=incident_id, root_cause=result.get("root_cause", ""),
            confidence=result.get("confidence", "low"),
            confidence_reason=result.get("confidence_reason", ""),
            evidence=result.get("evidence", []), suggested_fix=result.get("suggested_fix", ""),
            deploy_suspect=result.get("deploy_suspect"),
            similar_past_incident_id=result.get("similar_past_incident_id"),
            llm_model=usage.get("model"), prompt_tokens=usage.get("input_tokens"),
            completion_tokens=usage.get("output_tokens"),
        ))
        await db.commit()

        await post_to_slack(
            webhook_url=tenant.slack_webhook_url, alert_title=incident.alert_title,
            severity=incident.severity, analysis=result,
            elapsed_seconds=time.monotonic() - started,
        )
