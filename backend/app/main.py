from contextlib import contextmanager
from datetime import timedelta
import os
import csv
import io
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse

from . import auth, schemas
from .db import get_session
from .dependencies import get_store
from .observability import configure_logging, configure_tracing, get_logger
from .services.alerts import AlertService, IntegrationMonitor
from .services.budgets import BudgetLimitExceeded, BudgetService
from .services.ingest import IngestService
from .services.learning import AutoLearningService
from .services.metrics import MetricsCollector
from .services.object_storage import LocalObjectStorage
from .services.pipeline import PipelineService
from .services.planner import PlannerService
from .services.redirects import RedirectService
from .services.video_workshop import (
    PostProcessOptions,
    Sora2Client,
    StyleAnchors,
    VideoWorkshopService,
)
from .storage_db import DatabaseStore
from .vector_store import VectorStore

app = FastAPI(title="ContentZavod MVP")


@contextmanager
def store_context() -> DatabaseStore:
    with get_session() as session:
        yield DatabaseStore(session)


def get_video_workshop_service(store: DatabaseStore) -> VideoWorkshopService:
    sora_base_url = os.getenv("SORA_BASE_URL", "http://localhost:9001")
    sora_api_key = os.getenv("SORA_API_KEY", "demo-key")
    workdir = Path(os.getenv("VIDEO_WORKSHOP_WORKDIR", "storage/video_workshop"))
    storage_root = Path(os.getenv("OBJECT_STORAGE_ROOT", "storage/object_storage"))
    public_base_url = os.getenv(
        "OBJECT_STORAGE_PUBLIC_URL", "http://localhost:8000/storage"
    )
    storage = LocalObjectStorage(storage_root, public_base_url)
    ffmpeg_path = os.getenv("FFMPEG_PATH", "ffmpeg")
    return VideoWorkshopService(
        store,
        Sora2Client(sora_base_url, sora_api_key),
        storage,
        workdir,
        ffmpeg_path=ffmpeg_path,
    )


@app.on_event("startup")
def startup() -> None:
    configure_logging()
    configure_tracing(app)
    if os.getenv("INTEGRATION_CHECKS_ENABLED", "true").lower() in {"true", "1", "yes"}:
        interval_seconds = int(os.getenv("INTEGRATION_CHECK_INTERVAL", "300"))
        timeout_seconds = int(os.getenv("INTEGRATION_CHECK_TIMEOUT", "5"))
        monitor = IntegrationMonitor(
            store_context,
            interval_seconds=interval_seconds,
            timeout=timeout_seconds,
        )
        monitor.start()
        app.state.integration_monitor = monitor


@app.on_event("shutdown")
def shutdown() -> None:
    monitor = getattr(app.state, "integration_monitor", None)
    if monitor:
        monitor.stop()


@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    logger = get_logger()
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        "request_completed",
        extra={
            "event": "request_completed",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/auth/token", response_model=schemas.TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    store: DatabaseStore = Depends(get_store),
) -> schemas.TokenResponse:
    user = auth.authenticate_user(store, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    access_token = auth.create_access_token(
        data={"sub": user.email, "roles": user.roles},
        secret_key=store.jwt_secret_key,
        algorithm=store.jwt_algorithm,
        expires_delta=timedelta(minutes=store.jwt_expire_minutes),
    )
    return schemas.TokenResponse(access_token=access_token)


@app.post("/auth/bootstrap", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(
    payload: schemas.BootstrapUserCreate,
    store: DatabaseStore = Depends(get_store),
) -> schemas.User:
    if store.has_users():
        raise HTTPException(status_code=403, detail="bootstrap_forbidden")
    user_payload = schemas.UserCreate(
        email=payload.email,
        password=payload.password,
        roles=["Admin"],
        is_active=True,
    )
    password_hash = auth.get_password_hash(payload.password)
    return store.create_user(user_payload, password_hash)


@app.get("/users", response_model=list[schemas.User])
def list_users(
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin")),
) -> list[schemas.User]:
    return store.list_users()


@app.post("/users", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: schemas.UserCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin")),
) -> schemas.User:
    password_hash = auth.get_password_hash(payload.password)
    return store.create_user(payload, password_hash)


@app.get("/roles", response_model=list[schemas.Role])
def list_roles(
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin")),
) -> list[schemas.Role]:
    return store.list_roles()


@app.post("/projects", response_model=schemas.Project)
def create_project(
    payload: schemas.ProjectCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin")),
) -> schemas.Project:
    return store.create_project(payload)


@app.get("/projects", response_model=list[schemas.Project])
def list_projects(
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.Project]:
    return store.list_projects()


@app.get("/projects/{project_id}", response_model=schemas.Project)
def get_project(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> schemas.Project:
    try:
        return store.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/redirect-links", response_model=schemas.RedirectLink
)
def create_redirect_link(
    project_id: int,
    payload: schemas.RedirectLinkCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.RedirectLink:
    try:
        service = RedirectService(store)
        return service.create_link(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/redirect-links", response_model=list[schemas.RedirectLink]
)
def list_redirect_links(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.RedirectLink]:
    try:
        return store.list_redirect_links(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/redirect-links/{link_id}/clicks",
    response_model=list[schemas.ClickEvent],
)
def list_click_events(
    project_id: int,
    link_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.ClickEvent]:
    try:
        return store.list_click_events(project_id, redirect_link_id=link_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/r/{slug}")
def resolve_redirect(
    slug: str,
    request: Request,
    store: DatabaseStore = Depends(get_store),
) -> RedirectResponse:
    service = RedirectService(store)
    try:
        result = service.resolve(slug, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RedirectResponse(result.redirect_url)


@app.post(
    "/projects/{project_id}/planning/period",
    response_model=schemas.PlanPeriodResponse,
)
def plan_period(
    project_id: int,
    payload: schemas.PlanPeriodRequest,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.PlanPeriodResponse:
    service = PlannerService(store)
    try:
        result = service.plan_period(
            project_id,
            start_date=payload.start_date,
            days=payload.days,
            rubrics=payload.rubrics,
            rubric_weights=payload.rubric_weights,
            channels=payload.channels,
            channel_slots=payload.channel_slots,
            channel_frequency=payload.channel_frequency,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return schemas.PlanPeriodResponse(
        topics=result.topics,
        content_packs=result.content_packs,
        content_items=result.content_items,
        publications=result.publications,
    )

@app.post("/projects/{project_id}/brand-configs", response_model=schemas.BrandConfig)
def create_brand_config(
    project_id: int,
    payload: schemas.BrandConfigCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.BrandConfig:
    try:
        return store.create_brand_config(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/brand-configs/history",
    response_model=list[schemas.BrandConfigHistory],
)
def list_brand_config_history(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.BrandConfigHistory]:
    try:
        return store.list_brand_config_history(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put(
    "/projects/{project_id}/brand-configs/{config_id}/stable",
    response_model=schemas.BrandConfig,
)
def set_brand_config_stable(
    project_id: int,
    config_id: int,
    payload: schemas.StableVersionUpdate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.BrandConfig:
    try:
        return store.set_brand_config_stable(project_id, config_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/brand-configs/rollback",
    response_model=schemas.BrandConfig,
)
def rollback_brand_config(
    project_id: int,
    payload: schemas.BrandConfigRollback,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.BrandConfig:
    try:
        return store.rollback_brand_config(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/brand-configs", response_model=list[schemas.BrandConfig]
)
def list_brand_configs(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.BrandConfig]:
    try:
        return store.list_brand_configs(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/datasets", response_model=list[schemas.ProjectDataset]
)
def list_project_datasets(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.ProjectDataset]:
    try:
        return store.list_project_datasets(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/vector-indexes",
    response_model=list[schemas.ProjectVectorIndex],
)
def list_project_vector_indexes(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.ProjectVectorIndex]:
    try:
        return store.list_project_vector_indexes(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/budgets", response_model=schemas.Budget)
def create_budget(
    project_id: int,
    payload: schemas.BudgetCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin")),
) -> schemas.Budget:
    try:
        return store.create_budget(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/budgets", response_model=list[schemas.Budget])
def list_budgets(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin")),
) -> list[schemas.Budget]:
    try:
        return store.list_budgets(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/sources", response_model=schemas.Source)
def create_source(
    project_id: int,
    payload: schemas.SourceCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.Source:
    try:
        return store.create_source(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/sources", response_model=list[schemas.Source])
def list_sources(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.Source]:
    try:
        return store.list_sources(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/ingest/files", response_model=schemas.IngestResponse)
async def ingest_file(
    project_id: int,
    file: UploadFile = File(...),
    title: str | None = Form(None),
    source_type: str | None = Form(None),
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.IngestResponse:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty_file")
    service = IngestService(store, vector_store=VectorStore(store.session))
    try:
        result = service.ingest_file(
            project_id,
            filename=file.filename or "upload.bin",
            content=content,
            content_type=file.content_type or "application/octet-stream",
            title=title,
            source_type=source_type,
        )
        return schemas.IngestResponse(source=result.source, atoms=result.atoms)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/projects/{project_id}/ingest/links", response_model=schemas.IngestResponse)
def ingest_link(
    project_id: int,
    payload: schemas.IngestLinkRequest,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.IngestResponse:
    service = IngestService(store, vector_store=VectorStore(store.session))
    try:
        result = service.ingest_link(
            project_id,
            url=payload.url,
            title=payload.title,
            source_type=payload.source_type,
        )
        return schemas.IngestResponse(source=result.source, atoms=result.atoms)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/projects/{project_id}/atoms", response_model=schemas.Atom)
def create_atom(
    project_id: int,
    payload: schemas.AtomCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.Atom:
    try:
        return store.create_atom(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/atoms", response_model=list[schemas.Atom])
def list_atoms(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.Atom]:
    try:
        return store.list_atoms(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/topics", response_model=schemas.Topic)
def create_topic(
    project_id: int,
    payload: schemas.TopicCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.Topic:
    try:
        return store.create_topic(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/topics", response_model=list[schemas.Topic])
def list_topics(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.Topic]:
    try:
        return store.list_topics(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/content-packs", response_model=schemas.ContentPack)
def create_content_pack(
    project_id: int,
    payload: schemas.ContentPackCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.ContentPack:
    try:
        return store.create_content_pack(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/content-packs", response_model=list[schemas.ContentPack]
)
def list_content_packs(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.ContentPack]:
    try:
        return store.list_content_packs(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/content-items", response_model=schemas.ContentItem
)
def create_content_item(
    project_id: int,
    payload: schemas.ContentItemCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.ContentItem:
    try:
        return store.create_content_item(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/content-items", response_model=list[schemas.ContentItem]
)
def list_content_items(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.ContentItem]:
    try:
        return store.list_content_items(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/video-workshop/run",
    response_model=schemas.ContentItem,
)
def run_video_workshop(
    project_id: int,
    payload: schemas.VideoWorkshopRunRequest,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.ContentItem:
    try:
        _, topic = store.get_content_item_with_topic(
            project_id, payload.content_item_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    service = get_video_workshop_service(store)
    anchors = payload.style_anchors
    style_anchors = StyleAnchors(
        camera=anchors.camera,
        movement=anchors.movement,
        angle=anchors.angle,
        lighting=anchors.lighting,
        palette=anchors.palette,
        location=anchors.location,
        characters=anchors.characters,
    )
    postprocess = None
    if payload.postprocess:
        postprocess = PostProcessOptions(
            resolution=payload.postprocess.resolution,
            video_codec=payload.postprocess.video_codec,
            remove_audio=payload.postprocess.remove_audio,
            audio_path=Path(payload.postprocess.audio_path)
            if payload.postprocess.audio_path
            else None,
            cover_enabled=payload.postprocess.cover_enabled,
        )
    try:
        service.run_workshop(
            project_id,
            payload.content_item_id,
            topic.title,
            topic.angle,
            style_anchors,
            postprocess,
            payload.clip_durations,
        )
    except BudgetLimitExceeded as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return store.get_content_item(project_id, payload.content_item_id)


@app.post("/projects/{project_id}/qc-reports", response_model=schemas.QcReport)
def create_qc_report(
    project_id: int,
    payload: schemas.QcReportCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.QcReport:
    try:
        return store.create_qc_report(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/qc-reports", response_model=list[schemas.QcReport])
def list_qc_reports(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.QcReport]:
    try:
        return store.list_qc_reports(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/publications", response_model=schemas.Publication
)
def create_publication(
    project_id: int,
    payload: schemas.PublicationCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.Publication:
    try:
        return store.create_publication(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/publications", response_model=list[schemas.Publication]
)
def list_publications(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.Publication]:
    try:
        return store.list_publications(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/metrics", response_model=schemas.MetricSnapshot
)
def create_metric_snapshot(
    project_id: int,
    payload: schemas.MetricSnapshotCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.MetricSnapshot:
    try:
        return store.create_metric_snapshot(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/metrics/collect",
    response_model=list[schemas.MetricSnapshot],
)
def collect_metrics(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> list[schemas.MetricSnapshot]:
    collector = MetricsCollector(store)
    result = collector.collect(project_id)
    return result.snapshots


@app.get(
    "/projects/{project_id}/metrics", response_model=list[schemas.MetricSnapshot]
)
def list_metric_snapshots(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.MetricSnapshot]:
    try:
        return store.list_metric_snapshots(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/learning-events", response_model=schemas.LearningEvent
)
def create_learning_event(
    project_id: int,
    payload: schemas.LearningEventCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.LearningEvent:
    try:
        return store.create_learning_event(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/learning-events",
    response_model=list[schemas.LearningEvent],
)
def list_learning_events(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.LearningEvent]:
    try:
        return store.list_learning_events(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/auto-learning/config",
    response_model=schemas.AutoLearningConfig,
)
def get_auto_learning_config(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> schemas.AutoLearningConfig:
    try:
        return store.get_or_create_auto_learning_config(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put(
    "/projects/{project_id}/auto-learning/config",
    response_model=schemas.AutoLearningConfig,
)
def update_auto_learning_config(
    project_id: int,
    payload: schemas.AutoLearningConfigCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.AutoLearningConfig:
    try:
        return store.upsert_auto_learning_config(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/auto-learning/state",
    response_model=schemas.AutoLearningState,
)
def get_auto_learning_state(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> schemas.AutoLearningState:
    try:
        return store.get_or_create_auto_learning_state(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/auto-learning/run",
    response_model=dict,
)
def run_auto_learning(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> dict:
    service = AutoLearningService(store)
    result = service.run(project_id)
    return {
        "state": result.state,
        "applied_changes": result.applied_changes,
        "rollback_applied": result.rollback_applied,
    }


@app.post("/projects/{project_id}/pipelines/run")
def run_pipeline(
    project_id: int,
    topic_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> dict:
    pipeline = PipelineService(store, video_workshop=get_video_workshop_service(store))
    try:
        return pipeline.run(project_id, topic_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except BudgetLimitExceeded as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/projects/{project_id}/budget-usages", response_model=schemas.BudgetUsage)
def create_budget_usage(
    project_id: int,
    payload: schemas.BudgetUsageCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin")),
) -> schemas.BudgetUsage:
    try:
        return store.create_budget_usage(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/budget-usages", response_model=list[schemas.BudgetUsage]
)
def list_budget_usages(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin")),
) -> list[schemas.BudgetUsage]:
    try:
        return store.list_budget_usages(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/budget-report", response_model=schemas.BudgetReport
)
def get_budget_report(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> schemas.BudgetReport:
    service = BudgetService(store)
    try:
        return service.build_report(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/budget-report/export")
def export_budget_report(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> Response:
    service = BudgetService(store)
    try:
        report = service.build_report(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "window",
            "budget_limit",
            "token_used",
            "token_limit",
            "token_used_pct",
            "video_seconds_used",
            "video_seconds_limit",
            "video_seconds_used_pct",
            "publications_used",
            "publications_limit",
            "publications_used_pct",
        ]
    )
    for window in report.windows:
        writer.writerow(
            [
                window.window,
                window.budget_limit,
                window.token_used,
                window.token_limit,
                window.token_used_pct,
                window.video_seconds_used,
                window.video_seconds_limit,
                window.video_seconds_used_pct,
                window.publications_used,
                window.publications_limit,
                window.publications_used_pct,
            ]
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=budget_report.csv"},
    )


@app.post(
    "/projects/{project_id}/prompt-versions", response_model=schemas.PromptVersion
)
def create_prompt_version(
    project_id: int,
    payload: schemas.PromptVersionCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.PromptVersion:
    try:
        return store.create_prompt_version(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/prompt-versions/history",
    response_model=list[schemas.PromptVersionHistory],
)
def list_prompt_version_history(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.PromptVersionHistory]:
    try:
        return store.list_prompt_version_history(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put(
    "/projects/{project_id}/prompt-versions/{prompt_id}/stable",
    response_model=schemas.PromptVersion,
)
def set_prompt_version_stable(
    project_id: int,
    prompt_id: int,
    payload: schemas.StableVersionUpdate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.PromptVersion:
    try:
        return store.set_prompt_version_stable(project_id, prompt_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/prompt-versions/rollback",
    response_model=schemas.PromptVersion,
)
def rollback_prompt_version(
    project_id: int,
    payload: schemas.PromptVersionRollback,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor")),
) -> schemas.PromptVersion:
    try:
        return store.rollback_prompt_version(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/prompt-versions",
    response_model=list[schemas.PromptVersion],
)
def list_prompt_versions(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.PromptVersion]:
    try:
        return store.list_prompt_versions(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/integration-tokens",
    response_model=schemas.IntegrationToken,
    status_code=status.HTTP_201_CREATED,
)
def create_integration_token(
    project_id: int,
    payload: schemas.IntegrationTokenCreate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin")),
) -> schemas.IntegrationToken:
    try:
        return store.create_integration_token(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/integration-tokens",
    response_model=list[schemas.IntegrationToken],
)
def list_integration_tokens(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin")),
) -> list[schemas.IntegrationToken]:
    try:
        return store.list_integration_tokens(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/integration-tokens/{token_id}",
    response_model=schemas.IntegrationToken,
)
def get_integration_token(
    project_id: int,
    token_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin")),
) -> schemas.IntegrationToken:
    try:
        return store.get_integration_token(project_id, token_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put(
    "/projects/{project_id}/integration-tokens/{token_id}",
    response_model=schemas.IntegrationToken,
)
def update_integration_token(
    project_id: int,
    token_id: int,
    payload: schemas.IntegrationTokenUpdate,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin")),
) -> schemas.IntegrationToken:
    try:
        return store.update_integration_token(project_id, token_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/projects/{project_id}/integration-tokens/{token_id}", status_code=204)
def delete_integration_token(
    project_id: int,
    token_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin")),
) -> None:
    try:
        store.delete_integration_token(project_id, token_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return None


@app.get("/projects/{project_id}/alerts", response_model=list[schemas.Alert])
def list_alerts(
    project_id: int,
    store: DatabaseStore = Depends(get_store),
    _: schemas.User = Depends(auth.require_roles("Admin", "Editor", "Viewer")),
) -> list[schemas.Alert]:
    service = AlertService(store)
    try:
        return service.store.list_alerts(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
