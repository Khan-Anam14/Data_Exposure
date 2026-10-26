import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, JSON, Integer, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from src.db.session import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    slack_webhook_url: Mapped[str] = mapped_column(Text)
    api_key_hash: Mapped[str] = mapped_column(String(64))
    github_org: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_repo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_pat_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    datadog_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    datadog_app_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    pagerduty_webhook_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    opsgenie_webhook_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (UniqueConstraint("tenant_id", "alert_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    alert_source: Mapped[str] = mapped_column(String(50))
    alert_id: Mapped[str] = mapped_column(String(255))
    service_name: Mapped[str] = mapped_column(String(255))
    alert_title: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_alert: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Phase 2: pgvector embedding stored as JSON array (avoid pgvector extension requirement at model level)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("incidents.id"))
    root_cause: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(String(10))
    confidence_reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    suggested_fix: Mapped[str] = mapped_column(Text)
    deploy_suspect: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    similar_past_incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ContextSnapshot(Base):
    __tablename__ = "context_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("incidents.id"))
    commits: Mapped[list | None] = mapped_column(JSON, nullable=True)
    metric_anomalies: Mapped[list | None] = mapped_column(JSON, nullable=True)
    similar_incidents: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class DeployEvent(Base):
    __tablename__ = "deploy_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    source: Mapped[str] = mapped_column(String(50))
    service_name: Mapped[str] = mapped_column(String(255))
    commits: Mapped[list] = mapped_column(JSON)
    pushed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Postmortem(Base):
    __tablename__ = "postmortems"
    __table_args__ = (UniqueConstraint("incident_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("incidents.id"))
    draft_markdown: Mapped[str] = mapped_column(Text)
    feedback: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
