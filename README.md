# RootSignal — AI Incident Root Cause Assistant

When production breaks, RootSignal tells your team **what changed, why, and what to do** — in plain English, in under 90 seconds.

---

## Quick Start

```bash
# 1. Start Postgres + Redis
docker compose up -d

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Fill in: ANTHROPIC_API_KEY, ENCRYPTION_KEY, VOYAGE_API_KEY (Phase 2)
# Generate encryption key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 4. Run the API server
cd data_exposure
uvicorn src.main:app --reload

# 5. (Phase 2) Run Celery worker
celery -A celery_app worker --loglevel=info

# 6. Provision a tenant
python scripts/provision_tenant.py \
  --name "My Company" \
  --slack-webhook "https://hooks.slack.com/services/..." \
  --github-org myorg \
  --github-repo myrepo \
  --github-pat ghp_... \
  --datadog-api-key xxx \
  --datadog-app-key yyy \
  --pagerduty-secret zzz
```

Provisioning prints your **Tenant ID** and all **webhook URLs** to configure.

---

## Architecture

```
Alert fires (PagerDuty / OpsGenie / Grafana)
         ↓
POST /webhook/{source}/{tenant_id}
         ↓
  Parallel fetch (15s timeout each):
  • GitHub commits (last 2 hours)
  • Datadog metric anomalies (last 60 min)
  • Past similar incidents [Phase 2 — pgvector RAG]
         ↓
  Claude Sonnet → structured JSON root cause
         ↓
  Slack message posted < 90 seconds
         ↓
  Incident resolve → postmortem auto-drafted [Phase 2]
```

---

## Project Structure

```
data_exposure/
├── src/
│   ├── main.py                    FastAPI app
│   ├── config.py                  Settings (env vars)
│   ├── db/session.py              Async Postgres engine
│   ├── models/incidents.py        All SQLAlchemy models
│   ├── webhook/
│   │   ├── pagerduty.py           PagerDuty webhook + analysis
│   │   ├── opsgenie.py            OpsGenie webhook
│   │   └── grafana.py             Grafana webhook
│   ├── context/fetchers.py        GitHub + Datadog data fetchers
│   ├── llm/analyzer.py            Claude prompt + JSON output
│   ├── notifications/slack.py     Slack block message poster
│   ├── middleware/auth.py         API key authentication
│   ├── routes/incidents.py        REST API: list + get incidents
│   ├── dashboard/                 Web dashboard (Jinja2)
│   │   ├── routes.py
│   │   └── templates/
│   ├── rag/                       Phase 2: pgvector similarity
│   │   ├── embeddings.py          Voyage AI embeddings
│   │   └── retrieval.py           Past incident retrieval
│   ├── postmortem/generator.py    Phase 2: auto-draft postmortems
│   ├── tasks/analysis.py          Celery task (Phase 2)
│   ├── pii/redactor.py            Phase 3: PII redaction
│   └── audit/log.py               Phase 3: SOC2 audit log
├── celery_app.py                  Celery + Redis config
├── scripts/provision_tenant.py    Tenant onboarding CLI
├── tests/
│   ├── test_pii_redactor.py
│   └── test_audit.py
├── docker-compose.yml             Postgres + Redis
├── requirements.txt
└── .env.example
```

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Health check |
| `POST` | `/webhook/pagerduty/{tenant_id}` | HMAC sig | PagerDuty alerts |
| `POST` | `/webhook/opsgenie/{tenant_id}` | None | OpsGenie alerts |
| `POST` | `/webhook/grafana/{tenant_id}` | None | Grafana alerts |
| `GET` | `/incidents` | X-API-Key | List incidents |
| `GET` | `/incidents/{id}` | X-API-Key | Incident + analysis + postmortem |
| `GET` | `/dashboard` | Cookie/Query | Web dashboard |

---

## Phases

| Phase | Status | Scope |
|-------|--------|-------|
| **1 — MVP** | ✅ Built | PagerDuty + OpsGenie + Grafana, GitHub + Datadog, Claude analysis, Slack, REST API |
| **2 — Learning** | 🔧 Scaffold | pgvector RAG, postmortem drafts, Celery queue, web dashboard |
| **3 — Platform** | 📋 Planned | PII redaction, SOC2 audit log, Stripe billing, CloudWatch, Prometheus |

---

## Tests

```bash
cd data_exposure
pytest tests/ -v
```

Tests are pure-unit (no DB/network required for test_pii_redactor.py and test_audit.py).
