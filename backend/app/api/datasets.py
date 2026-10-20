from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dataset import Dataset, DatasetVersion
from app.models.evaluation_pack import EvaluationPack
from app.models.project import Project
from app.schemas.dataset import DatasetCreate
from app.schemas.evaluation_pack import EvaluationPackCreate
from app.serializers import dataset_dict, dataset_version_dict, evaluation_pack_dict
from app.services.dataset_service import create_dataset_version

router = APIRouter(tags=["datasets"])


@router.post("/evaluation-packs")
def create_evaluation_pack(payload: EvaluationPackCreate, db: Session = Depends(get_db)):
    existing = db.query(EvaluationPack).filter(EvaluationPack.slug == payload.slug).first()
    if existing:
        raise HTTPException(409, f"evaluation pack with slug '{payload.slug}' already exists")

    pack = EvaluationPack(**payload.model_dump())
    db.add(pack)
    db.commit()
    db.refresh(pack)
    return evaluation_pack_dict(pack)


@router.get("/evaluation-packs")
def list_evaluation_packs(db: Session = Depends(get_db)):
    return [evaluation_pack_dict(p) for p in db.query(EvaluationPack).all()]


@router.post("/projects/{project_id}/datasets")
def create_dataset(project_id: str, payload: DatasetCreate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")

    pack = db.get(EvaluationPack, payload.evaluation_pack_id)
    if pack is None:
        raise HTTPException(404, "evaluation pack not found")

    dataset = Dataset(
        project_id=project_id, evaluation_pack_id=payload.evaluation_pack_id,
        name=payload.name, description=payload.description,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset_dict(dataset)


@router.get("/projects/{project_id}/datasets")
def list_datasets(project_id: str, db: Session = Depends(get_db)):
    datasets = db.query(Dataset).filter(Dataset.project_id == project_id).all()
    return [dataset_dict(d) for d in datasets]


@router.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str, db: Session = Depends(get_db)):
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, "dataset not found")
    return dataset_dict(dataset)


@router.post("/datasets/{dataset_id}/versions")
def create_version(dataset_id: str, db: Session = Depends(get_db)):
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, "dataset not found")
    version = create_dataset_version(db, dataset_id)
    return dataset_version_dict(version)


@router.get("/datasets/{dataset_id}/versions")
def list_versions(dataset_id: str, db: Session = Depends(get_db)):
    versions = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_id == dataset_id)
        .order_by(DatasetVersion.version_number.desc())
        .all()
    )
    return [dataset_version_dict(v) for v in versions]
