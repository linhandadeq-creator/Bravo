from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.models.sample import Sample
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.schemas.sample import SampleRead

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    result = db.execute(select(Project).order_by(Project.created_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db)) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("/{project_id}/samples", response_model=list[SampleRead])
def list_project_samples(
    project_id: str, db: Session = Depends(get_db)
) -> list[Sample]:
    if db.get(Project, project_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    result = db.execute(
        select(Sample)
        .where(Sample.project_id == project_id)
        .order_by(Sample.created_at.desc())
    )
    return list(result.scalars().all())


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)
) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db)) -> None:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    # Core delete so the DB-level ON DELETE CASCADE removes children (the ORM
    # would otherwise try to null out child foreign keys).
    db.execute(delete(Project).where(Project.id == project_id))
    db.commit()
