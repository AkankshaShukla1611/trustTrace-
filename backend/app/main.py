from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.adapters import get_adapter_class
from app.database import get_db, init_db
from app.enums import IntegrationStatus, RunMode
from app.models.project import Integration, Project
from app.models.regression import RegressionComparison
from app.models.run import Run
from app.runner.engine import run_dataset_version
from app.runner.regression import compare_runs, evaluate_release_gate
from app.schemas.common import IntegrationCreate, ProjectCreate, RegressionCompareRequest, RunCreate
from app.serializers import integration_dict, project_dict, run_dict


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="TrustTrace API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/projects")
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=payload.name, description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project_dict(project)


@app.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    return [project_dict(p) for p in db.query(Project).all()]


@app.get("/projects/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    return project_dict(project)


@app.post("/projects/{project_id}/integrations")
def create_integration(project_id: str, payload: IntegrationCreate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")

    try:
        adapter_class = get_adapter_class(payload.adapter_type)
    except KeyError:
        raise HTTPException(400, f"unknown adapter_type '{payload.adapter_type}'")

    integration = Integration(
        project_id=project_id,
        name=payload.name,
        adapter_type=payload.adapter_type,
        config=payload.config,
        status=IntegrationStatus.CONFIGURED,
    )
    adapter = adapter_class(integration.config)
    integration.capabilities = adapter.get_capabilities().as_dict()
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return integration_dict(integration)


@app.post("/integrations/{integration_id}/validate")
def validate_integration(integration_id: str, db: Session = Depends(get_db)):
    integration = db.get(Integration, integration_id)
    if integration is None:
        raise HTTPException(404, "integration not found")

    adapter_class = get_adapter_class(integration.adapter_type)
    adapter = adapter_class(integration.config)
    result = adapter.validate_config()

    integration.status = IntegrationStatus.CONNECTED if result.ok else IntegrationStatus.FAILED
    integration.last_validation_message = result.message
    integration.last_validated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(integration)
    return integration_dict(integration)


@app.post("/runs")
def create_run(payload: RunCreate, db: Session = Depends(get_db)):
    try:
        run = run_dataset_version(
            db,
            project_id=payload.project_id,
            integration_id=payload.integration_id,
            dataset_version_id=payload.dataset_version_id,
            mode=RunMode(payload.mode),
            test_case_ids=payload.test_case_ids,
            label=payload.label,
            baseline_run_id=payload.baseline_run_id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return run_dict(run)


@app.get("/runs")
def list_runs(project_id: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Run)
    if project_id:
        query = query.filter(Run.project_id == project_id)
    runs = query.order_by(Run.started_at.desc()).all()
    return [run_dict(r, include_executions=False) for r in runs]


@app.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    return run_dict(run)


@app.post("/regression/compare")
def regression_compare(payload: RegressionCompareRequest, db: Session = Depends(get_db)):
    try:
        summary = compare_runs(db, payload.baseline_run_id, payload.candidate_run_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    comparison = RegressionComparison(
        baseline_run_id=payload.baseline_run_id, candidate_run_id=payload.candidate_run_id, summary=summary
    )
    db.add(comparison)
    db.commit()
    db.refresh(comparison)
    return {"id": comparison.id, **summary}


@app.post("/regression/release-gate")
def regression_release_gate(payload: RegressionCompareRequest, rules: dict, db: Session = Depends(get_db)):
    summary = compare_runs(db, payload.baseline_run_id, payload.candidate_run_id)
    return evaluate_release_gate(summary, rules)
