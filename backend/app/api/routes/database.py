"""Database inspection and selective deletion (operator maintenance)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import database_service

router = APIRouter(prefix="/database", tags=["database"])


class DeleteRequest(BaseModel):
    ids: list[str] = Field(default_factory=list)


@router.get("/overview")
def get_overview(db: Session = Depends(get_db)) -> dict:
    return database_service.overview(db)


@router.get("/tables")
def get_tables(db: Session = Depends(get_db)) -> list[dict]:
    return database_service.list_tables(db)


@router.get("/tables/{table_name}")
def get_table_rows(
    table_name: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return database_service.table_rows(db, table_name, limit, offset)
    except database_service.UnknownTableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/tables/{table_name}/delete")
def delete_table_rows(
    table_name: str, payload: DeleteRequest, db: Session = Depends(get_db)
) -> dict:
    try:
        deleted = database_service.delete_rows(db, table_name, payload.ids)
    except database_service.UnknownTableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except database_service.DatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"table": table_name, "deleted": deleted}


@router.post("/tables/{table_name}/clear")
def clear_table(table_name: str, db: Session = Depends(get_db)) -> dict:
    try:
        deleted = database_service.clear_table(db, table_name)
    except database_service.UnknownTableError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"table": table_name, "deleted": deleted}
