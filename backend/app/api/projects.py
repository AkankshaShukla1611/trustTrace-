from __future__ import annotations
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.adapters import get_adapter_class
from app.database import get_db
from app.enums import IntegrationStatus
from app.models.project import Integration, Project
from app.schemas.common import IntegrationCreate, ProjectCreate
from app.serializers import integration_dict, project_dict

router = APIRouter(tags=["projects"])


@router.post("/projects")
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(name=payload.name, description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project_dict(project)


@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    return [project_dict(p) for p in db.query(Project).all()]


@router.get("/projects/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    return project_dict(project)


@router.post("/projects/{project_id}/integrations")
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


@router.post("/integrations/{integration_id}/validate")
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
