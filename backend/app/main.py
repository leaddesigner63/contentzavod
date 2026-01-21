from fastapi import FastAPI, HTTPException

from . import schemas
from .services.pipeline import PipelineService
from .storage import InMemoryStore

app = FastAPI(title="ContentZavod MVP")
store = InMemoryStore()
pipeline = PipelineService(store)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/projects", response_model=schemas.Project)
def create_project(payload: schemas.ProjectCreate) -> schemas.Project:
    return store.create_project(payload)


@app.get("/projects", response_model=list[schemas.Project])
def list_projects() -> list[schemas.Project]:
    return store.list_projects()


@app.post("/projects/{project_id}/brand-configs", response_model=schemas.BrandConfig)
def create_brand_config(
    project_id: int, payload: schemas.BrandConfigCreate
) -> schemas.BrandConfig:
    try:
        return store.create_brand_config(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/budgets", response_model=schemas.Budget)
def create_budget(project_id: int, payload: schemas.BudgetCreate) -> schemas.Budget:
    try:
        return store.create_budget(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/sources", response_model=schemas.Source)
def create_source(project_id: int, payload: schemas.SourceCreate) -> schemas.Source:
    try:
        return store.create_source(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/topics", response_model=schemas.Topic)
def create_topic(project_id: int, payload: schemas.TopicCreate) -> schemas.Topic:
    try:
        return store.create_topic(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/content-packs", response_model=schemas.ContentPack)
def create_content_pack(
    project_id: int, payload: schemas.ContentPackCreate
) -> schemas.ContentPack:
    try:
        return store.create_content_pack(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/content-items", response_model=schemas.ContentItem
)
def create_content_item(
    project_id: int, payload: schemas.ContentItemCreate
) -> schemas.ContentItem:
    try:
        return store.create_content_item(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/qc-reports", response_model=schemas.QcReport)
def create_qc_report(
    project_id: int, payload: schemas.QcReportCreate
) -> schemas.QcReport:
    try:
        return store.create_qc_report(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/publications", response_model=schemas.Publication
)
def create_publication(
    project_id: int, payload: schemas.PublicationCreate
) -> schemas.Publication:
    try:
        return store.create_publication(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/metrics", response_model=schemas.MetricSnapshot
)
def create_metric_snapshot(
    project_id: int, payload: schemas.MetricSnapshotCreate
) -> schemas.MetricSnapshot:
    try:
        return store.create_metric_snapshot(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/projects/{project_id}/learning-events", response_model=schemas.LearningEvent
)
def create_learning_event(
    project_id: int, payload: schemas.LearningEventCreate
) -> schemas.LearningEvent:
    try:
        return store.create_learning_event(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/pipelines/run")
def run_pipeline(project_id: int, topic_id: int) -> dict:
    try:
        return pipeline.run(project_id, topic_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
