"""Project module extras: attached files, notes and reminders."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.project import Project
from app.models.project_file import SUPPORTED_FILE_KINDS, ProjectFile
from app.models.project_notes import ProjectNote, ProjectReminder
from app.schemas.project import (
    NoteCreate,
    NoteRead,
    NoteUpdate,
    ProjectFileRead,
    ReminderCreate,
    ReminderRead,
    ReminderUpdate,
)
from app.services.uploads import UploadTooLargeError, copy_limited

router = APIRouter(prefix="/projects", tags=["project-module"])


def _get_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_filename(name: str) -> str:
    return "".join(
        ch if ch.isalnum() or ch in (".", "-", "_") else "_"
        for ch in Path(name or "file").name
    ) or "file"


# ------------------------------------------------------------- files ---------


@router.get("/{project_id}/files", response_model=list[ProjectFileRead])
def list_files(project_id: str, db: Session = Depends(get_db)) -> list[ProjectFile]:
    _get_project(db, project_id)
    result = db.execute(
        select(ProjectFile)
        .where(ProjectFile.project_id == project_id)
        .order_by(ProjectFile.kind, ProjectFile.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/{project_id}/files", response_model=ProjectFileRead, status_code=status.HTTP_201_CREATED
)
def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    kind: str = Form(default="TUMOR_VCF"),
    db: Session = Depends(get_db),
) -> ProjectFile:
    _get_project(db, project_id)
    if kind not in SUPPORTED_FILE_KINDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file kind '{kind}'. Supported: {', '.join(SUPPORTED_FILE_KINDS)}",
        )
    filename = _safe_filename(file.filename or "upload")
    directory = settings.storage_path / "project_files" / project_id
    directory.mkdir(parents=True, exist_ok=True)
    row = ProjectFile(
        project_id=project_id, kind=kind, filename=filename, storage_path="", file_size_bytes=0
    )
    db.add(row)
    db.flush()
    destination = directory / f"{row.id}_{filename}"
    try:
        size = copy_limited(file.file, destination)
    except UploadTooLargeError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    row.storage_path = str(destination)
    row.file_size_bytes = size
    row.input_hash = _sha256(destination)
    db.commit()
    db.refresh(row)
    return row


@router.get("/{project_id}/files/{file_id}")
def download_file(
    project_id: str, file_id: str, db: Session = Depends(get_db)
) -> FileResponse:
    _get_project(db, project_id)
    row = db.get(ProjectFile, file_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    path = Path(row.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing on disk")
    return FileResponse(path, filename=row.filename, media_type="application/octet-stream")


@router.delete("/{project_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(project_id: str, file_id: str, db: Session = Depends(get_db)) -> Response:
    _get_project(db, project_id)
    row = db.get(ProjectFile, file_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    try:
        Path(row.storage_path).unlink(missing_ok=True)
    except OSError:
        pass
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -------------------------------------------------------------- notes ---------


@router.get("/{project_id}/notes", response_model=list[NoteRead])
def list_notes(project_id: str, db: Session = Depends(get_db)) -> list[ProjectNote]:
    _get_project(db, project_id)
    result = db.execute(
        select(ProjectNote)
        .where(ProjectNote.project_id == project_id)
        .order_by(ProjectNote.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{project_id}/notes", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(project_id: str, payload: NoteCreate, db: Session = Depends(get_db)) -> ProjectNote:
    _get_project(db, project_id)
    note = ProjectNote(project_id=project_id, content=payload.content)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.patch("/{project_id}/notes/{note_id}", response_model=NoteRead)
def update_note(
    project_id: str, note_id: str, payload: NoteUpdate, db: Session = Depends(get_db)
) -> ProjectNote:
    _get_project(db, project_id)
    note = db.get(ProjectNote, note_id)
    if note is None or note.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    note.content = payload.content
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{project_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(project_id: str, note_id: str, db: Session = Depends(get_db)) -> Response:
    _get_project(db, project_id)
    note = db.get(ProjectNote, note_id)
    if note is None or note.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    db.delete(note)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------- reminders ---------


@router.get("/{project_id}/reminders", response_model=list[ReminderRead])
def list_reminders(project_id: str, db: Session = Depends(get_db)) -> list[ProjectReminder]:
    _get_project(db, project_id)
    result = db.execute(
        select(ProjectReminder)
        .where(ProjectReminder.project_id == project_id)
        .order_by(ProjectReminder.done, ProjectReminder.due_at)
    )
    return list(result.scalars().all())


@router.post(
    "/{project_id}/reminders",
    response_model=ReminderRead,
    status_code=status.HTTP_201_CREATED,
)
def create_reminder(
    project_id: str, payload: ReminderCreate, db: Session = Depends(get_db)
) -> ProjectReminder:
    _get_project(db, project_id)
    reminder = ProjectReminder(project_id=project_id, title=payload.title, due_at=payload.due_at)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.patch("/{project_id}/reminders/{reminder_id}", response_model=ReminderRead)
def update_reminder(
    project_id: str,
    reminder_id: str,
    payload: ReminderUpdate,
    db: Session = Depends(get_db),
) -> ProjectReminder:
    _get_project(db, project_id)
    reminder = db.get(ProjectReminder, reminder_id)
    if reminder is None or reminder.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(reminder, field, value)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.delete(
    "/{project_id}/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_reminder(
    project_id: str, reminder_id: str, db: Session = Depends(get_db)
) -> Response:
    _get_project(db, project_id)
    reminder = db.get(ProjectReminder, reminder_id)
    if reminder is None or reminder.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    db.delete(reminder)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
