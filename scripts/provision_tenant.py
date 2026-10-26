"""
Provision a new tenant and print the webhook URL + API key.

Usage:
  python scripts/provision_tenant.py \
    --name "Acme Corp" \
    --slack-webhook "https://hooks.slack.com/services/..." \
    --github-org myorg \
    --github-repo myrepo \
    --github-pat ghp_... \
    --datadog-api-key xxx \
    --datadog-app-key yyy \
    --pagerduty-secret zzz
"""
import argparse
import asyncio
import hashlib
import os
import secrets
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.config import settings
from src.models.incidents import Tenant


def _enc(value: str | None) -> str | None:
    if not value:
        return None
    return Fernet(settings.encryption_key.encode()).encrypt(value.encode()).decode()


async def provision(args: argparse.Namespace) -> None:
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    raw_key = secrets.token_hex(32)
    api_key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    async with Session() as db:
        tenant = Tenant(
            name=args.name,
            slack_webhook_url=args.slack_webhook,
            api_key_hash=api_key_hash,
            github_org=args.github_org,
            github_repo=args.github_repo,
            github_pat_encrypted=_enc(args.github_pat),
            datadog_api_key_encrypted=_enc(args.datadog_api_key),
            datadog_app_key_encrypted=_enc(args.datadog_app_key),
            pagerduty_webhook_secret_encrypted=_enc(args.pagerduty_secret),
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)

    print(f"\n✅ Tenant provisioned: {tenant.name}")
    print(f"   Tenant ID  : {tenant.id}")
    print(f"   API Key    : {raw_key}  ← store this, it's shown only once")
    print(f"\n   Webhook URLs (configure in your alert provider):")
    print(f"   PagerDuty  : POST https://your-domain/webhook/pagerduty/{tenant.id}")
    print(f"   OpsGenie   : POST https://your-domain/webhook/opsgenie/{tenant.id}")
    print(f"   Grafana    : POST https://your-domain/webhook/grafana/{tenant.id}")
    print()
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Provision a RootSignal tenant")
    parser.add_argument("--name", required=True)
    parser.add_argument("--slack-webhook", required=True)
    parser.add_argument("--github-org")
    parser.add_argument("--github-repo")
    parser.add_argument("--github-pat")
    parser.add_argument("--datadog-api-key")
    parser.add_argument("--datadog-app-key")
    parser.add_argument("--pagerduty-secret")
    asyncio.run(provision(parser.parse_args()))
