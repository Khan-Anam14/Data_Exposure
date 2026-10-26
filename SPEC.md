# RootSignal — AI-Powered Incident Root Cause Assistant
## Product Specification

| Field | Value |
|---|---|
| **Author** | Accord Base Engineering |
| **Date** | October 2025 |
| **Status** | Approved |
| **Stack** | Python 3.12, FastAPI, PostgreSQL + pgvector, Celery + Redis, Claude Sonnet |

---

## 1. Context

Engineering teams lose 60–80% of incident time diagnosing *what changed* rather than fixing it. Current tools (PagerDuty, Datadog, incident.io) alert on symptoms but provide no cross-signal root cause correlation. Teams earning $2M+/hour in downtime costs have no affordable AI-powered diagnosis tool.

RootSignal closes this gap: when an alert fires, it fetches recent deploys, metric anomalies, and past similar incidents in parallel, then posts a plain-English root cause + suggested fix to Slack in under 90 seconds.

**Evidence:** 80% of DevOps teams report MTTR exceeds multiple hours. Only 9% are satisfied with current tooling. TAM $3.8–8.5B, 9–12% CAGR.

**Goal:** Internal dogfood first → commercial SaaS at $199–499/month/team.

---

## 2. Functional Requirements

### Phase 1 — MVP Core

**FR-1** The system MUST receive PagerDuty webhook events at `POST /webhook/pagerduty/{tenant_id}`.

**FR-2** The system MUST validate PagerDuty HMAC-SHA256 webhook signatures before processing.

**FR-3** The system MUST deduplicate incidents by `(tenant_id, alert_id)` — re-delivery of the same alert MUST NOT create duplicate analyses.

**FR-4** The system MUST fetch the 10 most recent GitHub commits for the alerting service within a 2-hour window before the alert time.

**FR-5** The system MUST fetch Datadog metric anomalies (CPU, memory, error rate, request rate) for the alerting service over the 60 minutes preceding the alert.

**FR-6** Metric data MUST be pre-processed to anomaly summary strings (mean + stddev baseline vs. recent window) before being sent to the LLM — raw time series data MUST NOT be sent.

**FR-7** The system MUST call Claude Sonnet API with structured context and return a JSON root cause analysis with fields: `root_cause`, `confidence` (high/medium/low), `confidence_reason`, `evidence[]`, `suggested_fix`, `deploy_suspect`, `similar_past_incident_id`.

**FR-8** The system MUST post a formatted Slack message with the root cause analysis within 90 seconds of receiving the alert webhook.

**FR-9** If any single context fetch (GitHub, Datadog) fails or times out, the system MUST proceed with partial context and note the missing source.

**FR-10** If the LLM call fails, the system MUST post a fallback Slack message with raw signals and retry once with 5-second backoff.

**FR-11** The system MUST receive OpsGenie webhook events at `POST /webhook/opsgenie/{tenant_id}` and process them identically to PagerDuty alerts.

**FR-12** The system MUST receive Grafana alert webhook events at `POST /webhook/grafana/{tenant_id}`.

**FR-13** All tenant credentials (GitHub PAT, Datadog keys, webhook secrets) MUST be encrypted at rest using Fernet symmetric encryption.

**FR-14** The system MUST expose `GET /incidents/{incident_id}` returning incident metadata + latest analysis.

**FR-15** The system MUST expose `GET /incidents` returning paginated incident list for a tenant (authenticated by API key header).

**FR-16** API key authentication MUST be enforced on all non-webhook endpoints via `X-API-Key` header.

**FR-17** The system MUST store all incidents, analyses, and context snapshots in PostgreSQL.

### Phase 2 — Learning & Self-Serve

**FR-18** On incident resolution, the system MUST generate a semantic embedding of the incident (`alert_title + service_name + root_cause + evidence`) and store it in pgvector.

**FR-19** When a new incident arrives, the system MUST retrieve the top 2 past incidents with cosine similarity > 0.80 and inject them into the LLM prompt.

**FR-20** On incident resolution (PagerDuty `incident.resolve` event), the system MUST auto-draft a postmortem in Markdown and store it in the `postmortems` table.

**FR-21** The postmortem MUST include: Summary, Impact, Timeline, Root Cause, Contributing Factors, Action Items.

**FR-22** The system MUST offload analysis background tasks to Celery workers backed by Redis.

**FR-23** The system MUST expose a web dashboard at `GET /dashboard` showing: incident list, analysis detail, postmortem view (authenticated by session cookie or API key).

**FR-24** The system MUST support tenant self-serve onboarding via `POST /tenants` (creates tenant, returns API key + webhook URL).

**FR-25** The system MUST support GitLab webhook events at `POST /webhook/gitlab/{tenant_id}` as a deploy source.

### Phase 3 — Full Platform

**FR-26** Slack messages MUST include thumbs-up/thumbs-down interactive buttons for root cause feedback.

**FR-27** Confirmed-correct analyses (thumbs-up) MUST be weighted higher in future pgvector similarity retrieval.

**FR-28** The system MUST support AWS CloudWatch metric queries as an alternative to Datadog.

**FR-29** The system MUST apply a PII redaction pass before any data is sent to the LLM — targeting email addresses, IPv4, tokens matching `[A-Za-z0-9_-]{32,}`, and `sk-*` patterns.

**FR-30** The system MUST maintain an append-only audit log table recording all LLM calls, inputs (hashed), outputs, and tenant IDs for SOC2 compliance.

**FR-31** The system MUST integrate with Stripe metered billing, reporting one billing event per incident analyzed.

**FR-32** The system MUST support Prometheus remote_read or pushgateway as a metrics source.

---

## 3. Non-Functional Requirements

**NFR-1** End-to-end time from alert webhook receipt to Slack message MUST be under 90 seconds (P95).

**NFR-2** Individual context fetches (GitHub, Datadog) MUST time out after 15 seconds.

**NFR-3** The webhook endpoint MUST respond HTTP 200/accepted within 500ms — analysis runs asynchronously.

**NFR-4** LLM prompt MUST stay under 3,000 tokens total. Commits trimmed oldest-first if over budget.

**NFR-5** LLM cost per incident MUST stay under $0.02 (Claude Sonnet pricing).

**NFR-6** The system MUST support at least 100 concurrent tenants with no cross-tenant data leakage.

**NFR-7** All credentials MUST be encrypted at rest; database connections MUST use TLS.

**NFR-8** The system MUST handle PagerDuty at-least-once delivery without duplicate analyses (idempotency).

**NFR-9** The web dashboard MUST load the incident list in under 2 seconds for up to 1,000 incidents.

---

## 4. Acceptance Criteria

### Phase 1

**AC-1** (FR-1, FR-2) Given a valid PagerDuty webhook with correct HMAC signature, when the endpoint receives it, then it MUST return HTTP 200 within 500ms.

**AC-2** (FR-2) Given a PagerDuty webhook with an invalid signature, when the endpoint receives it, then it MUST return HTTP 403 and MUST NOT create an incident.

**AC-3** (FR-3) Given the same PagerDuty alert_id sent twice to the same tenant, when both webhooks are received, then only one incident and one analysis MUST be created.

**AC-4** (FR-7, FR-8) Given a valid PagerDuty alert with GitHub and Datadog configured, when the incident is processed, then a Slack message MUST be posted within 90 seconds containing root_cause, confidence, evidence, and suggested_fix.

**AC-5** (FR-9) Given Datadog API returns 500, when processing an incident, then the system MUST still post a Slack message noting "Datadog data unavailable" and MUST NOT block analysis.

**AC-6** (FR-10) Given Claude API returns an error on first call, when retry fires after 5 seconds, then if the retry succeeds the Slack message MUST be posted normally.

**AC-7** (FR-11) Given a valid OpsGenie webhook, when the endpoint receives it, then it MUST process identically to a PagerDuty alert and post to Slack.

**AC-8** (FR-13) Given a tenant is provisioned with a GitHub PAT, when the PAT is stored, then the raw PAT MUST NOT appear in any database column.

**AC-9** (FR-16) Given a request to `GET /incidents` without `X-API-Key` header, when the request is received, then it MUST return HTTP 401.

**AC-10** (FR-16) Given a request to `GET /incidents` with a valid `X-API-Key`, when the request is received, then it MUST return only incidents belonging to that tenant.

### Phase 2

**AC-11** (FR-18, FR-19) Given an incident is resolved with a stored embedding, when a similar alert fires, then the LLM prompt MUST contain the past incident's root_cause and suggested_fix.

**AC-12** (FR-20, FR-21) Given an incident resolves, when the postmortem is generated, then a Markdown document with Summary, Impact, Timeline, Root Cause, Contributing Factors, and Action Items MUST be stored in the postmortems table within 60 seconds.

**AC-13** (FR-22) Given a PagerDuty alert fires, when the Celery worker processes it, then the analysis MUST complete and Slack message MUST be posted within 90 seconds.

**AC-14** (FR-23) Given a user accesses `/dashboard` with a valid API key, when the page loads, then it MUST display a list of recent incidents with their confidence level and root cause summary.

### Phase 3

**AC-15** (FR-29) Given a commit message contains an email address or API token pattern, when context is assembled, then the LLM prompt MUST NOT contain the original value — only a redacted placeholder.

**AC-16** (FR-30) Given any LLM call is made, when it completes, then an audit log entry MUST be written with tenant_id, timestamp, model, prompt_hash, and output_hash.

---

## 5. Edge Cases

**EC-1** GitHub repo not found (404) — treat as "No commits available", proceed with partial context.

**EC-2** PagerDuty sends webhook during GitHub/Datadog outage — proceed with empty context, Slack message notes all sources unavailable.

**EC-3** Claude returns malformed JSON — retry once; if still malformed, post raw signals to Slack with "Analysis parsing failed" note.

**EC-4** Slack webhook URL deactivated (non-200 response) — log failure, store analysis in DB, do NOT retry Slack (avoid infinite loop).

**EC-5** Same tenant sends 100 alerts in 60 seconds (alert storm) — each creates a separate incident; Celery queue absorbs the burst; no rate limiting in MVP.

**EC-6** Commit message is empty or only whitespace — include commit SHA and author but note "No commit message".

**EC-7** Datadog returns metric series with fewer than 4 data points — insufficient for anomaly detection, skip that metric silently.

**EC-8** pgvector similarity search returns 0 results above threshold — proceed without past incidents, do not inject empty context.

**EC-9** Tenant PagerDuty webhook secret rotated — signature validation fails, return 403 with message directing to reconfigure; do NOT silently accept.

**EC-10** Incident resolve webhook arrives before trigger webhook — create incident with status=resolved, skip analysis (no active incident to analyze).

---

## 6. API Contracts

### Webhook endpoints

```
POST /webhook/pagerduty/{tenant_id}
Headers: X-PagerDuty-Signature: v1={hmac}
Body: PagerDuty V3 webhook payload
Response 200: {"status": "accepted"}
Response 403: {"detail": "Invalid signature"}
Response 404: {"detail": "Tenant not found"}

POST /webhook/opsgenie/{tenant_id}
Body: OpsGenie webhook payload
Response 200: {"status": "accepted"}

POST /webhook/grafana/{tenant_id}
Body: Grafana webhook payload (unified alerting format)
Response 200: {"status": "accepted"}
```

### Incident endpoints

```
GET /incidents
Headers: X-API-Key: {api_key}
Query: page=1&limit=20&status=active|resolved
Response 200: {
  "items": [IncidentSummary],
  "total": number,
  "page": number,
  "limit": number
}
Response 401: {"detail": "Missing or invalid API key"}

GET /incidents/{incident_id}
Headers: X-API-Key: {api_key}
Response 200: {
  "incident": Incident,
  "analysis": Analysis | null,
  "postmortem": Postmortem | null
}
Response 404: {"detail": "Incident not found"}
```

### Tenant provisioning (Phase 2)

```
POST /tenants
Body: {
  name: string,
  slack_webhook_url: string,
  github_org?: string,
  github_repo?: string,
  github_pat?: string,
  datadog_api_key?: string,
  datadog_app_key?: string,
  pagerduty_webhook_secret?: string
}
Response 201: {
  "tenant_id": uuid,
  "api_key": string,       // returned once, never again
  "webhook_urls": {
    "pagerduty": string,
    "opsgenie": string,
    "grafana": string
  }
}
```

### Types

```typescript
interface Incident {
  id: string;           // uuid
  service_name: string;
  alert_title: string;
  severity: "high" | "low";
  status: "active" | "resolved";
  started_at: string;   // ISO 8601
  resolved_at: string | null;
}

interface Analysis {
  id: string;
  root_cause: string;
  confidence: "high" | "medium" | "low";
  confidence_reason: string;
  evidence: string[];
  suggested_fix: string;
  deploy_suspect: { commit_sha: string; author: string; message: string } | null;
  llm_model: string;
  prompt_tokens: number;
  completion_tokens: number;
  created_at: string;
}

interface Postmortem {
  id: string;
  incident_id: string;
  draft_markdown: string;
  created_at: string;
}
```

---

## 7. Data Models

### tenants

| Field | Type | Constraints |
|---|---|---|
| id | UUID | PK, default uuid4 |
| name | VARCHAR(255) | NOT NULL |
| slack_webhook_url | TEXT | NOT NULL |
| api_key_hash | CHAR(64) | NOT NULL, SHA-256 of API key |
| github_org | VARCHAR(255) | NULLABLE |
| github_repo | VARCHAR(255) | NULLABLE |
| github_pat_encrypted | TEXT | NULLABLE, Fernet encrypted |
| datadog_api_key_encrypted | TEXT | NULLABLE |
| datadog_app_key_encrypted | TEXT | NULLABLE |
| pagerduty_webhook_secret_encrypted | TEXT | NULLABLE |
| opsgenie_webhook_secret_encrypted | TEXT | NULLABLE |
| service_metrics | JSONB | NULLABLE |
| created_at | TIMESTAMPTZ | NOT NULL |

### incidents

| Field | Type | Constraints |
|---|---|---|
| id | UUID | PK, default uuid4 |
| tenant_id | UUID | FK tenants.id, NOT NULL |
| alert_source | VARCHAR(50) | NOT NULL (pagerduty/opsgenie/grafana) |
| alert_id | VARCHAR(255) | NOT NULL |
| service_name | VARCHAR(255) | NOT NULL |
| alert_title | TEXT | NOT NULL |
| severity | VARCHAR(50) | NOT NULL |
| status | VARCHAR(50) | NOT NULL, default 'active' |
| started_at | TIMESTAMPTZ | NOT NULL |
| resolved_at | TIMESTAMPTZ | NULLABLE |
| raw_alert | JSONB | NULLABLE |
| embedding | vector(1024) | NULLABLE (Phase 2) |
| — | UNIQUE(tenant_id, alert_id) | — |

### analyses

| Field | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| incident_id | UUID | FK incidents.id |
| root_cause | TEXT | NOT NULL |
| confidence | VARCHAR(10) | NOT NULL (high/medium/low) |
| confidence_reason | TEXT | NOT NULL |
| evidence | JSONB | NULLABLE |
| suggested_fix | TEXT | NOT NULL |
| deploy_suspect | JSONB | NULLABLE |
| similar_past_incident_id | UUID | NULLABLE |
| llm_model | VARCHAR(100) | NULLABLE |
| prompt_tokens | INTEGER | NULLABLE |
| completion_tokens | INTEGER | NULLABLE |
| created_at | TIMESTAMPTZ | NOT NULL |

### context_snapshots

| Field | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| incident_id | UUID | FK incidents.id |
| commits | JSONB | NULLABLE |
| metric_anomalies | JSONB | NULLABLE |
| similar_incidents | JSONB | NULLABLE |
| created_at | TIMESTAMPTZ | NOT NULL |

### postmortems (Phase 2)

| Field | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| incident_id | UUID | FK incidents.id, UNIQUE |
| draft_markdown | TEXT | NOT NULL |
| feedback | VARCHAR(10) | NULLABLE (thumbs_up/thumbs_down) |
| created_at | TIMESTAMPTZ | NOT NULL |

### audit_log (Phase 3)

| Field | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| tenant_id | UUID | NOT NULL |
| event_type | VARCHAR(50) | NOT NULL (llm_call/webhook_received/etc) |
| prompt_hash | CHAR(64) | NULLABLE (SHA-256) |
| output_hash | CHAR(64) | NULLABLE |
| llm_model | VARCHAR(100) | NULLABLE |
| metadata | JSONB | NULLABLE |
| created_at | TIMESTAMPTZ | NOT NULL |

---

## 8. Out of Scope

**OS-1** Fine-tuning or training custom LLM models — RAG retrieval covers this use case without MLOps overhead.

**OS-2** Real-time streaming of log lines to the LLM — pre-processed anomaly summaries are sufficient and cheaper.

**OS-3** Mobile app — web dashboard + Slack covers all notification needs.

**OS-4** Multi-language support (i18n) — English only for MVP.

**OS-5** Self-hosted on-premise option — Phase 3+ only, excluded from current scope.

**OS-6** Alertmanager (Prometheus) direct integration — users can use Grafana as the alerting layer instead.

**OS-7** GitHub Actions specific workflow correlation — commit-level correlation is sufficient for Phase 1-2.

---

## 9. Phase Implementation Plan

### Phase 1 — Complete MVP (Week 1–4)
Files to build:
- `src/middleware/auth.py` — API key auth dependency
- `src/webhook/opsgenie.py` — OpsGenie webhook handler
- `src/webhook/grafana.py` — Grafana webhook handler
- `src/routes/incidents.py` — paginated incidents list endpoint
- `tests/test_webhook_pagerduty.py` — AC-1 through AC-6
- `tests/test_webhook_opsgenie.py` — AC-7
- `tests/test_auth.py` — AC-9, AC-10
- `tests/conftest.py` — fixtures

### Phase 2 — Learning & Self-Serve (Week 5–12)
Files to build:
- `src/rag/embeddings.py` — voyage/openai embedding client
- `src/rag/retrieval.py` — pgvector similarity search
- `src/postmortem/generator.py` — LLM postmortem draft
- `src/tasks/analysis.py` — Celery task (replaces BackgroundTasks)
- `celery_app.py` — Celery + Redis config
- `src/dashboard/routes.py` — Jinja2 web dashboard
- `src/dashboard/templates/` — HTML templates
- `src/routes/tenants.py` — self-serve onboarding endpoint
- `src/webhook/gitlab.py` — GitLab deploy source
- `tests/test_rag.py` — AC-11
- `tests/test_postmortem.py` — AC-12

### Phase 3 — Full Platform (Month 4–6)
Files to build:
- `src/pii/redactor.py` — regex + pattern PII redaction
- `src/audit/log.py` — append-only audit log writer
- `src/billing/stripe_client.py` — Stripe metered billing
- `src/metrics/cloudwatch.py` — CloudWatch metrics fetcher
- `src/metrics/prometheus.py` — Prometheus remote_read client
- `tests/test_pii_redactor.py` — AC-15
- `tests/test_audit.py` — AC-16
