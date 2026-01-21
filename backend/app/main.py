from fastapi import Depends, FastAPI, HTTPException

from . import schemas
from .db import get_session
from .services.pipeline import PipelineService
from .storage_db import DatabaseStore

app = FastAPI(title="ContentZavod MVP")


def get_store():
    with get_session() as session:
        yield DatabaseStore(session)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/projects", response_model=schemas.Project)
def create_project(
    payload: schemas.ProjectCreate, store: DatabaseStore = Depends(get_store)
) -> schemas.Project:
    return store.create_project(payload)


@app.get("/projects", response_model=list[schemas.Project])
def list_projects(store: DatabaseStore = Depends(get_store)) -> list[schemas.Project]:
    return store.list_projects()


@app.get("/projects/{project_id}", response_model=schemas.Project)
def get_project(
    project_id: int, store: DatabaseStore = Depends(get_store)
) -> schemas.Project:
    try:
        return store.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.post("/projects/{project_id}/brand-configs", response_model=schemas.BrandConfig)
def create_brand_config(
    project_id: int,
    payload: schemas.BrandConfigCreate,
    store: DatabaseStore = Depends(get_store),
) -> schemas.BrandConfig:
    try:
        return store.create_brand_config(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/brand-configs", response_model=list[schemas.BrandConfig]
)
def list_brand_configs(
    project_id: int, store: DatabaseStore = Depends(get_store)
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
) -> schemas.Budget:
    try:
        return store.create_budget(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/budgets", response_model=list[schemas.Budget])
def list_budgets(
    project_id: int, store: DatabaseStore = Depends(get_store)
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
) -> schemas.Source:
    try:
        return store.create_source(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/sources", response_model=list[schemas.Source])
def list_sources(
    project_id: int, store: DatabaseStore = Depends(get_store)
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
) -> schemas.Atom:
    try:
        return store.create_atom(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/atoms", response_model=list[schemas.Atom])
def list_atoms(project_id: int, store: DatabaseStore = Depends(get_store)) -> list[
    schemas.Atom
]:
    try:
        return store.list_atoms(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/topics", response_model=schemas.Topic)
def create_topic(
    project_id: int,
    payload: schemas.TopicCreate,
    store: DatabaseStore = Depends(get_store),
) -> schemas.Topic:
    try:
        return store.create_topic(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/topics", response_model=list[schemas.Topic])
def list_topics(project_id: int, store: DatabaseStore = Depends(get_store)) -> list[
    schemas.Topic
]:
    try:
        return store.list_topics(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/content-packs", response_model=schemas.ContentPack)
def create_content_pack(
    project_id: int,
    payload: schemas.ContentPackCreate,
    store: DatabaseStore = Depends(get_store),
) -> schemas.ContentPack:
    try:
        return store.create_content_pack(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/content-packs", response_model=list[schemas.ContentPack]
)
def list_content_packs(
    project_id: int, store: DatabaseStore = Depends(get_store)
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
) -> schemas.ContentItem:
    try:
        return store.create_content_item(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/content-items", response_model=list[schemas.ContentItem]
)
def list_content_items(
    project_id: int, store: DatabaseStore = Depends(get_store)
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
) -> schemas.QcReport:
    try:
        return store.create_qc_report(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/qc-reports", response_model=list[schemas.QcReport])
def list_qc_reports(
    project_id: int, store: DatabaseStore = Depends(get_store)
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
) -> schemas.Publication:
    try:
        return store.create_publication(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/publications", response_model=list[schemas.Publication]
)
def list_publications(
    project_id: int, store: DatabaseStore = Depends(get_store)
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
) -> schemas.MetricSnapshot:
    try:
        return store.create_metric_snapshot(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/metrics", response_model=list[schemas.MetricSnapshot]
)
def list_metric_snapshots(
    project_id: int, store: DatabaseStore = Depends(get_store)
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
    project_id: int, store: DatabaseStore = Depends(get_store)
) -> list[schemas.LearningEvent]:
    try:
        return store.list_learning_events(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/pipelines/run")
def run_pipeline(
    project_id: int, topic_id: int, store: DatabaseStore = Depends(get_store)
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
) -> schemas.BudgetUsage:
    try:
        return store.create_budget_usage(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/budget-usages", response_model=list[schemas.BudgetUsage]
)
def list_budget_usages(
    project_id: int, store: DatabaseStore = Depends(get_store)
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
    project_id: int, store: DatabaseStore = Depends(get_store)
) -> list[schemas.PromptVersion]:
    try:
        return store.list_prompt_versions(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
