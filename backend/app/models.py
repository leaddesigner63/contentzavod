from __future__ import annotations

from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active")

    brand_configs: Mapped[list[BrandConfig]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    brand_config_history: Mapped[list[BrandConfigHistory]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    datasets: Mapped[list[ProjectDataset]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    vector_indexes: Mapped[list[ProjectVectorIndex]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    budgets: Mapped[list[Budget]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    sources: Mapped[list[Source]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    atoms: Mapped[list[Atom]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    topics: Mapped[list[Topic]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    content_packs: Mapped[list[ContentPack]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    content_items: Mapped[list[ContentItem]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    qc_reports: Mapped[list[QcReport]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    publications: Mapped[list[Publication]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    metric_snapshots: Mapped[list[MetricSnapshot]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    redirect_links: Mapped[list[RedirectLink]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    click_events: Mapped[list[ClickEvent]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    learning_events: Mapped[list[LearningEvent]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    auto_learning_config: Mapped[Optional[AutoLearningConfig]] = relationship(
        back_populates="project", cascade="all, delete-orphan", uselist=False
    )
    auto_learning_state: Mapped[Optional[AutoLearningState]] = relationship(
        back_populates="project", cascade="all, delete-orphan", uselist=False
    )
    prompt_versions: Mapped[list[PromptVersion]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    prompt_version_history: Mapped[list[PromptVersionHistory]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    budget_usages: Mapped[list[BudgetUsage]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    integration_tokens: Mapped[list[IntegrationToken]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    alerts: Mapped[list[Alert]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    user_roles: Mapped[list[UserRole]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user_roles: Mapped[list[UserRole]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uniq_user_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))

    user: Mapped[User] = relationship(back_populates="user_roles")
    role: Mapped[Role] = relationship(back_populates="user_roles")


class BrandConfig(Base, TimestampMixin):
    __tablename__ = "brand_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    version: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_stable: Mapped[bool] = mapped_column(Boolean, default=False)
    tone: Mapped[str] = mapped_column(String(255))
    audience: Mapped[str] = mapped_column(String(255))
    offers: Mapped[list] = mapped_column(JSON, default=list)
    rubrics: Mapped[list] = mapped_column(JSON, default=list)
    forbidden: Mapped[list] = mapped_column(JSON, default=list)
    cta_policy: Mapped[str] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="brand_configs")


class BrandConfigHistory(Base, TimestampMixin):
    __tablename__ = "brand_config_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    brand_config_id: Mapped[int] = mapped_column(ForeignKey("brand_configs.id"))
    version: Mapped[int] = mapped_column(Integer)
    change_summary: Mapped[Optional[str]] = mapped_column(Text)
    change_payload: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped[Project] = relationship(back_populates="brand_config_history")
    brand_config: Mapped[BrandConfig] = relationship()


class ProjectDataset(Base, TimestampMixin):
    __tablename__ = "project_datasets"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uniq_project_dataset"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(64), default="atoms")
    storage_uri: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    project: Mapped[Project] = relationship(back_populates="datasets")


class ProjectVectorIndex(Base, TimestampMixin):
    __tablename__ = "project_vector_indexes"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uniq_project_vector_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(128))
    provider: Mapped[str] = mapped_column(String(64), default="pgvector")
    embedding_dimension: Mapped[int] = mapped_column(Integer, default=1536)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped[Project] = relationship(back_populates="vector_indexes")


class Budget(Base, TimestampMixin):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    daily: Mapped[float] = mapped_column(Float)
    weekly: Mapped[float] = mapped_column(Float)
    monthly: Mapped[float] = mapped_column(Float)
    token_limit: Mapped[int] = mapped_column(Integer)
    video_seconds_limit: Mapped[int] = mapped_column(Integer)
    publication_limit: Mapped[int] = mapped_column(Integer)

    project: Mapped[Project] = relationship(back_populates="budgets")
    usages: Mapped[list[BudgetUsage]] = relationship(
        back_populates="budget", cascade="all, delete-orphan"
    )


class BudgetUsage(Base, TimestampMixin):
    __tablename__ = "budget_usages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.id"))
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    usage_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    token_used: Mapped[int] = mapped_column(Integer, default=0)
    video_seconds_used: Mapped[int] = mapped_column(Integer, default=0)
    publications_used: Mapped[int] = mapped_column(Integer, default=0)

    budget: Mapped[Budget] = relationship(back_populates="usages")
    project: Mapped[Project] = relationship(back_populates="budget_usages")


class Source(Base, TimestampMixin):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(64))
    uri: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[Optional[str]] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="sources")
    atoms: Mapped[list[Atom]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class Atom(Base, TimestampMixin):
    __tablename__ = "atoms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    kind: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    source_backed: Mapped[bool] = mapped_column(Boolean)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1536))

    project: Mapped[Project] = relationship(back_populates="atoms")
    source: Mapped[Source] = relationship(back_populates="atoms")


class Topic(Base, TimestampMixin):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(String(255))
    angle: Mapped[str] = mapped_column(String(255))
    rubric: Mapped[Optional[str]] = mapped_column(String(255))
    planned_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="planned")

    project: Mapped[Project] = relationship(back_populates="topics")
    content_packs: Mapped[list[ContentPack]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )


class ContentPack(Base, TimestampMixin):
    __tablename__ = "content_packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="queued")

    project: Mapped[Project] = relationship(back_populates="content_packs")
    topic: Mapped[Topic] = relationship(back_populates="content_packs")
    content_items: Mapped[list[ContentItem]] = relationship(
        back_populates="content_pack", cascade="all, delete-orphan"
    )


class ContentItem(Base, TimestampMixin):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    pack_id: Mapped[int] = mapped_column(ForeignKey("content_packs.id"))
    channel: Mapped[str] = mapped_column(String(64))
    format: Mapped[str] = mapped_column(String(64))
    body: Mapped[str] = mapped_column(Text)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="draft")

    project: Mapped[Project] = relationship(back_populates="content_items")
    content_pack: Mapped[ContentPack] = relationship(back_populates="content_items")
    qc_reports: Mapped[list[QcReport]] = relationship(
        back_populates="content_item", cascade="all, delete-orphan"
    )
    publications: Mapped[list[Publication]] = relationship(
        back_populates="content_item", cascade="all, delete-orphan"
    )
    metric_snapshots: Mapped[list[MetricSnapshot]] = relationship(
        back_populates="content_item", cascade="all, delete-orphan"
    )
    redirect_links: Mapped[list[RedirectLink]] = relationship(
        back_populates="content_item", cascade="all, delete-orphan"
    )
    click_events: Mapped[list[ClickEvent]] = relationship(
        back_populates="content_item", cascade="all, delete-orphan"
    )


class QcReport(Base, TimestampMixin):
    __tablename__ = "qc_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    content_item_id: Mapped[int] = mapped_column(ForeignKey("content_items.id"))
    score: Mapped[float] = mapped_column(Float)
    passed: Mapped[bool] = mapped_column(Boolean)
    reasons: Mapped[list] = mapped_column(JSON, default=list)

    project: Mapped[Project] = relationship(back_populates="qc_reports")
    content_item: Mapped[ContentItem] = relationship(back_populates="qc_reports")


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    content_item_id: Mapped[int] = mapped_column(ForeignKey("content_items.id"))
    platform: Mapped[str] = mapped_column(String(64))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="scheduled")
    platform_post_id: Mapped[Optional[str]] = mapped_column(String(255))
    platform_post_url: Mapped[Optional[str]] = mapped_column(String(512))
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="publications")
    content_item: Mapped[ContentItem] = relationship(back_populates="publications")


class MetricSnapshot(Base):
    __tablename__ = "metrics_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    content_item_id: Mapped[int] = mapped_column(ForeignKey("content_items.id"))
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    project: Mapped[Project] = relationship(back_populates="metric_snapshots")
    content_item: Mapped[ContentItem] = relationship(back_populates="metric_snapshots")


class RedirectLink(Base, TimestampMixin):
    __tablename__ = "redirect_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    content_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("content_items.id")
    )
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    target_url: Mapped[str] = mapped_column(Text)
    utm_params: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    project: Mapped[Project] = relationship(back_populates="redirect_links")
    content_item: Mapped[Optional[ContentItem]] = relationship(
        back_populates="redirect_links"
    )
    click_events: Mapped[list[ClickEvent]] = relationship(
        back_populates="redirect_link", cascade="all, delete-orphan"
    )


class ClickEvent(Base):
    __tablename__ = "click_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    redirect_link_id: Mapped[int] = mapped_column(ForeignKey("redirect_links.id"))
    content_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("content_items.id")
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(64))
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    referrer: Mapped[Optional[str]] = mapped_column(Text)
    utm_params: Mapped[dict] = mapped_column(JSON, default=dict)
    query_params: Mapped[dict] = mapped_column(JSON, default=dict)
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    project: Mapped[Project] = relationship(back_populates="click_events")
    redirect_link: Mapped[RedirectLink] = relationship(back_populates="click_events")
    content_item: Mapped[Optional[ContentItem]] = relationship(
        back_populates="click_events"
    )


class LearningEvent(Base, TimestampMixin):
    __tablename__ = "learning_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    parameter: Mapped[str] = mapped_column(String(255))
    previous_value: Mapped[str] = mapped_column(Text)
    new_value: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="learning_events")


class AutoLearningConfig(Base, TimestampMixin):
    __tablename__ = "auto_learning_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), unique=True)
    max_changes_per_week: Mapped[int] = mapped_column(Integer, default=2)
    rollback_threshold: Mapped[float] = mapped_column(Float, default=0.02)
    rollback_window: Mapped[int] = mapped_column(Integer, default=20)
    protected_parameters: Mapped[list] = mapped_column(JSON, default=list)

    project: Mapped[Project] = relationship(back_populates="auto_learning_config")


class AutoLearningState(Base, TimestampMixin):
    __tablename__ = "auto_learning_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), unique=True)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    stable_parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    window_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    changes_in_window: Mapped[int] = mapped_column(Integer, default=0)
    last_change_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_rollback_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    project: Mapped[Project] = relationship(back_populates="auto_learning_state")


class PromptVersion(Base, TimestampMixin):
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    prompt_key: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_stable: Mapped[bool] = mapped_column(Boolean, default=False)

    project: Mapped[Project] = relationship(back_populates="prompt_versions")


class PromptVersionHistory(Base, TimestampMixin):
    __tablename__ = "prompt_version_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    prompt_version_id: Mapped[int] = mapped_column(ForeignKey("prompt_versions.id"))
    prompt_key: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer)
    change_summary: Mapped[Optional[str]] = mapped_column(Text)
    change_payload: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped[Project] = relationship(back_populates="prompt_version_history")
    prompt_version: Mapped[PromptVersion] = relationship()


class IntegrationToken(Base):
    __tablename__ = "integration_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    provider: Mapped[str] = mapped_column(String(32))
    token_encrypted: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    project: Mapped[Project] = relationship(back_populates="integration_tokens")


class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    alert_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text)
    metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped[Project] = relationship(back_populates="alerts")
