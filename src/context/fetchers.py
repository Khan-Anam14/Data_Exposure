import asyncio
import statistics
from datetime import datetime, timedelta

import httpx
from cryptography.fernet import Fernet

from src.config import settings


def _decrypt(value: str) -> str:
    return Fernet(settings.encryption_key.encode()).decrypt(value.encode()).decode()


async def _empty() -> list:
    return []


async def fetch_github_commits(
    github_org: str,
    github_repo: str,
    github_pat_encrypted: str,
    service_path: str | None,
    alert_time: datetime,
) -> list[dict]:
    token = _decrypt(github_pat_encrypted)
    since = (alert_time - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")

    params: dict = {"since": since, "per_page": 10}
    if service_path:
        params["path"] = service_path

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"https://api.github.com/repos/{github_org}/{github_repo}/commits",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"},
            params=params,
        )
        resp.raise_for_status()
        raw = resp.json()

    result = []
    for c in raw:
        committed_at = datetime.fromisoformat(c["commit"]["author"]["date"].replace("Z", "+00:00"))
        minutes_before = int((alert_time - committed_at).total_seconds() / 60)
        result.append({
            "sha": c["sha"][:8],
            "author": c["commit"]["author"]["name"],
            "message": c["commit"]["message"].split("\n")[0][:120],
            "timestamp": c["commit"]["author"]["date"],
            "minutes_before_alert": minutes_before,
        })
    return result


async def fetch_datadog_anomalies(
    service_name: str,
    datadog_api_key_encrypted: str,
    datadog_app_key_encrypted: str,
    alert_time: datetime,
    service_metrics: dict | None = None,
) -> list[str]:
    api_key = _decrypt(datadog_api_key_encrypted)
    app_key = _decrypt(datadog_app_key_encrypted)

    queries = (
        service_metrics.get(service_name)
        if service_metrics and service_name in service_metrics
        else [
            f"avg:system.cpu.user{{service:{service_name}}}",
            f"avg:system.mem.used{{service:{service_name}}}",
            f"avg:trace.{service_name}.hits{{*}}",
            f"avg:trace.{service_name}.errors{{*}}",
        ]
    )

    t_end = int(alert_time.timestamp())
    t_start = t_end - 3600
    t_baseline_end = t_end - 900

    anomalies: list[str] = []
    headers = {"DD-API-KEY": api_key, "DD-APPLICATION-KEY": app_key}

    async with httpx.AsyncClient(timeout=15.0) as client:
        for query in queries:
            try:
                resp = await client.get(
                    "https://api.datadoghq.com/api/v1/query",
                    headers=headers,
                    params={"from": t_start, "to": t_end, "query": query},
                )
                if resp.status_code != 200:
                    continue
                series = resp.json().get("series", [])
                if not series:
                    continue

                points = series[0].get("pointlist", [])
                if len(points) < 4:
                    continue

                baseline = [p[1] for p in points if p[0] / 1000 <= t_baseline_end and p[1] is not None]
                recent = [p[1] for p in points if p[0] / 1000 > t_baseline_end and p[1] is not None]
                if not baseline or not recent:
                    continue

                mean = statistics.mean(baseline)
                std = statistics.stdev(baseline) if len(baseline) > 1 else 0
                peak = max(recent)

                if std > 0 and abs(peak - mean) > 2 * std:
                    metric_name = series[0].get("metric", query)
                    pct = (peak - mean) / mean * 100
                    anomalies.append(
                        f"{metric_name} spiked from {mean:.1f} to {peak:.1f} (+{pct:.0f}%) in the last 15 minutes"
                    )
            except Exception:
                continue

    return anomalies


async def gather_context(service_name: str, alert_time: datetime, tenant) -> tuple[list, list]:
    github_coro = (
        fetch_github_commits(
            tenant.github_org, tenant.github_repo, tenant.github_pat_encrypted, None, alert_time
        )
        if tenant.github_org and tenant.github_pat_encrypted
        else _empty()
    )

    dd_coro = (
        fetch_datadog_anomalies(
            service_name,
            tenant.datadog_api_key_encrypted,
            tenant.datadog_app_key_encrypted,
            alert_time,
            tenant.service_metrics,
        )
        if tenant.datadog_api_key_encrypted and tenant.datadog_app_key_encrypted
        else _empty()
    )

    results = await asyncio.gather(github_coro, dd_coro, return_exceptions=True)
    commits = results[0] if not isinstance(results[0], Exception) else []
    anomalies = results[1] if not isinstance(results[1], Exception) else []
    return commits, anomalies
