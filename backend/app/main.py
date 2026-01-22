from datetime import timedelta

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse

from . import auth, schemas
from .dependencies import get_store
from .services.learning import AutoLearningService
from .services.metrics import MetricsCollector
from .services.pipeline import PipelineService
from .services.redirects import RedirectService
from .storage_db import DatabaseStore

app = FastAPI(title="ContentZavod MVP")


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
    pipeline = PipelineService(store)
    try:
        return pipeline.run(project_id, topic_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
