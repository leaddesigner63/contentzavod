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


@app.get("/projects/{project_id}", response_model=schemas.Project)
def get_project(project_id: int) -> schemas.Project:
    try:
        return store.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

@app.post("/projects/{project_id}/brand-configs", response_model=schemas.BrandConfig)
def create_brand_config(
    project_id: int, payload: schemas.BrandConfigCreate
) -> schemas.BrandConfig:
    try:
        return store.create_brand_config(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(
    "/projects/{project_id}/brand-configs", response_model=list[schemas.BrandConfig]
)
def list_brand_configs(project_id: int) -> list[schemas.BrandConfig]:
    try:
        return store.list_brand_configs(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/budgets", response_model=schemas.Budget)
def create_budget(project_id: int, payload: schemas.BudgetCreate) -> schemas.Budget:
    try:
        return store.create_budget(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/budgets", response_model=list[schemas.Budget])
def list_budgets(project_id: int) -> list[schemas.Budget]:
    try:
        return store.list_budgets(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/sources", response_model=schemas.Source)
def create_source(project_id: int, payload: schemas.SourceCreate) -> schemas.Source:
    try:
        return store.create_source(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/sources", response_model=list[schemas.Source])
def list_sources(project_id: int) -> list[schemas.Source]:
    try:
        return store.list_sources(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/atoms", response_model=schemas.Atom)
def create_atom(project_id: int, payload: schemas.AtomCreate) -> schemas.Atom:
    try:
        return store.create_atom(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/atoms", response_model=list[schemas.Atom])
def list_atoms(project_id: int) -> list[schemas.Atom]:
    try:
        return store.list_atoms(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/topics", response_model=schemas.Topic)
def create_topic(project_id: int, payload: schemas.TopicCreate) -> schemas.Topic:
    try:
        return store.create_topic(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/projects/{project_id}/topics", response_model=list[schemas.Topic])
def list_topics(project_id: int) -> list[schemas.Topic]:
    try:
        return store.list_topics(project_id)
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


@app.get(
    "/projects/{project_id}/content-packs", response_model=list[schemas.ContentPack]
)
def list_content_packs(project_id: int) -> list[schemas.ContentPack]:
    try:
        return store.list_content_packs(project_id)
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


@app.get(
    "/projects/{project_id}/content-items", response_model=list[schemas.ContentItem]
)
def list_content_items(project_id: int) -> list[schemas.ContentItem]:
    try:
        return store.list_content_items(project_id)
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


@app.get("/projects/{project_id}/qc-reports", response_model=list[schemas.QcReport])
def list_qc_reports(project_id: int) -> list[schemas.QcReport]:
    try:
        return store.list_qc_reports(project_id)
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


@app.get(
    "/projects/{project_id}/publications", response_model=list[schemas.Publication]
)
def list_publications(project_id: int) -> list[schemas.Publication]:
    try:
        return store.list_publications(project_id)
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


@app.get(
    "/projects/{project_id}/metrics", response_model=list[schemas.MetricSnapshot]
)
def list_metric_snapshots(project_id: int) -> list[schemas.MetricSnapshot]:
    try:
        return store.list_metric_snapshots(project_id)
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


@app.get(
    "/projects/{project_id}/learning-events",
    response_model=list[schemas.LearningEvent],
)
def list_learning_events(project_id: int) -> list[schemas.LearningEvent]:
    try:
        return store.list_learning_events(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/projects/{project_id}/pipelines/run")
def run_pipeline(project_id: int, topic_id: int) -> dict:
    try:
        return pipeline.run(project_id, topic_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
