from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.enums import RunMode
from app.models.regression import RegressionComparison
from app.models.run import Run
from app.runner.engine import run_dataset_version
from app.runner.regression import compare_runs, evaluate_release_gate
from app.schemas.common import RegressionCompareRequest, RunCreate
from app.serializers import run_dict
from app.services.report_service import build_run_report, render_markdown

router = APIRouter(tags=["runs"])


@router.post("/runs")
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


@router.get("/runs")
def list_runs(project_id: str | None = None, db: Session = Depends(get_db)):
    query = db.query(Run)
    if project_id:
        query = query.filter(Run.project_id == project_id)
    runs = query.order_by(Run.started_at.desc()).all()
    return [run_dict(r, include_executions=False) for r in runs]


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    return run_dict(run)


@router.get("/runs/{run_id}/report")
def get_run_report(run_id: str, format: str = Query("json", pattern="^(json|markdown)$"), db: Session = Depends(get_db)):
    try:
        report = build_run_report(db, run_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))

    if format == "markdown":
        return PlainTextResponse(render_markdown(report), media_type="text/markdown")
    return report


@router.post("/regression/compare")
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


@router.post("/regression/release-gate")
def regression_release_gate(payload: RegressionCompareRequest, rules: dict, db: Session = Depends(get_db)):
    summary = compare_runs(db, payload.baseline_run_id, payload.candidate_run_id)
    return evaluate_release_gate(summary, rules)
