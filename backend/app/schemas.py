from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2)
    description: Optional[str] = None


class Project(ProjectCreate):
    id: int
    status: str = "active"
    created_at: datetime


class BrandConfigCreate(BaseModel):
    tone: str
    audience: str
    offers: List[str] = []
    rubrics: List[str] = []
    forbidden: List[str] = []
    cta_policy: str


class BrandConfig(BrandConfigCreate):
    id: int
    project_id: int
    version: int
    created_at: datetime


class BudgetCreate(BaseModel):
    daily: float
    weekly: float
    monthly: float
    token_limit: int
    video_seconds_limit: int
    publication_limit: int


class Budget(BudgetCreate):
    id: int
    project_id: int
    created_at: datetime


class SourceCreate(BaseModel):
    title: str
    source_type: str
    uri: Optional[str] = None
    content: Optional[str] = None


class Source(SourceCreate):
    id: int
    project_id: int
    created_at: datetime


class AtomCreate(BaseModel):
    source_id: int
    kind: str
    text: str
    source_backed: bool
    embedding: Optional[List[float]] = None


class Atom(BaseModel):
    id: int
    project_id: int
    source_id: int
    kind: str
    text: str
    source_backed: bool
    embedding: Optional[List[float]] = None
    created_at: datetime


class TopicCreate(BaseModel):
    title: str
    angle: str
    rubric: Optional[str] = None
    planned_for: Optional[datetime] = None


class Topic(TopicCreate):
    id: int
    project_id: int
    status: str = "planned"
    created_at: datetime


class ContentPackCreate(BaseModel):
    topic_id: int
    description: Optional[str] = None


class ContentPack(ContentPackCreate):
    id: int
    project_id: int
    status: str = "queued"
    created_at: datetime


class ContentItemCreate(BaseModel):
    pack_id: int
    channel: str
    format: str
    body: str
    metadata: dict = Field(default_factory=dict)


class ContentItem(ContentItemCreate):
    id: int
    project_id: int
    status: str = "draft"
    created_at: datetime


class QcReportCreate(BaseModel):
    content_item_id: int
    score: float
    passed: bool
    reasons: List[str] = []


class QcReport(QcReportCreate):
    id: int
    project_id: int
    created_at: datetime


class PublicationCreate(BaseModel):
    content_item_id: int
    platform: str
    scheduled_at: datetime
    status: str = "scheduled"
    idempotency_key: Optional[str] = None


class Publication(PublicationCreate):
    id: int
    project_id: int
    platform_post_id: Optional[str] = None
    platform_post_url: Optional[str] = None
    published_at: Optional[datetime] = None
    attempt_count: int = 0
    last_error: Optional[str] = None


class MetricSnapshotCreate(BaseModel):
    content_item_id: int
    impressions: int = 0
    clicks: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0


class MetricSnapshot(MetricSnapshotCreate):
    id: int
    project_id: int
    collected_at: datetime


class RedirectLinkCreate(BaseModel):
    content_item_id: Optional[int] = None
    target_url: str
    slug: Optional[str] = None
    utm_params: dict = Field(default_factory=dict)
    is_active: bool = True


class RedirectLink(RedirectLinkCreate):
    id: int
    project_id: int
    created_at: datetime


class ClickEvent(BaseModel):
    id: int
    project_id: int
    redirect_link_id: int
    content_item_id: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    referrer: Optional[str] = None
    utm_params: dict = Field(default_factory=dict)
    query_params: dict = Field(default_factory=dict)
    clicked_at: datetime


class LearningEventCreate(BaseModel):
    parameter: str
    previous_value: str
    new_value: str
    reason: str


class LearningEvent(LearningEventCreate):
    id: int
    project_id: int
    created_at: datetime


class AutoLearningConfigCreate(BaseModel):
    max_changes_per_week: int = 2
    rollback_threshold: float = 0.02
    rollback_window: int = 20
    protected_parameters: List[str] = Field(default_factory=list)


class AutoLearningConfig(AutoLearningConfigCreate):
    id: int
    project_id: int
    created_at: datetime


class AutoLearningState(BaseModel):
    id: int
    project_id: int
    parameters: dict = Field(default_factory=dict)
    stable_parameters: dict = Field(default_factory=dict)
    window_started_at: Optional[datetime] = None
    changes_in_window: int = 0
    last_change_at: Optional[datetime] = None
    last_rollback_at: Optional[datetime] = None
    created_at: datetime


class PromptVersionCreate(BaseModel):
    prompt_key: str
    content: str
    is_active: bool = True


class PromptVersion(PromptVersionCreate):
    id: int
    project_id: int
    version: int
    created_at: datetime


class BudgetUsageCreate(BaseModel):
    budget_id: int
    usage_date: datetime
    token_used: int = 0
    video_seconds_used: int = 0
    publications_used: int = 0


class BudgetUsage(BudgetUsageCreate):
    id: int
    project_id: int
    created_at: datetime


class BudgetWindowUsage(BaseModel):
    window: str
    token_used: int
    video_seconds_used: int
    publications_used: int


class BudgetReport(BaseModel):
    project_id: int
    budget: Budget
    windows: List[BudgetWindowUsage]
    is_blocked: bool
    generated_at: datetime


class Role(BaseModel):
    id: int
    name: str
    created_at: datetime


class RoleCreate(BaseModel):
    name: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    roles: List[str] = Field(default_factory=lambda: ["Viewer"])
    is_active: bool = True


class User(BaseModel):
    id: int
    email: EmailStr
    roles: List[str]
    is_active: bool
    created_at: datetime


class BootstrapUserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class IntegrationTokenCreate(BaseModel):
    provider: str
    token: str


class IntegrationTokenUpdate(BaseModel):
    token: str


class IntegrationToken(BaseModel):
    id: int
    project_id: int
    provider: str
    token: str
    created_at: datetime
    updated_at: datetime


class AlertCreate(BaseModel):
    alert_type: str
    severity: str
    message: str
    metadata: dict = Field(default_factory=dict)


class Alert(AlertCreate):
    id: int
    project_id: int
    created_at: datetime
