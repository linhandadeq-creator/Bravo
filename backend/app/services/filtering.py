"""Candidate filtering by allowed consequences.

The allowed set is stored per project (user-editable) and falls back to the
configured default. The filtering rule itself is data, not code.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.annotation.base import AnnotationStatus
from app.core.config import settings
from app.models.filter_config import AnnotationFilterConfig


def get_filter_config(db: Session, project_id: str) -> AnnotationFilterConfig | None:
    statement = select(AnnotationFilterConfig).where(
        AnnotationFilterConfig.project_id == project_id
    )
    return db.execute(statement).scalars().first()


def get_allowed_consequences(db: Session, project_id: str) -> list[str]:
    config = get_filter_config(db, project_id)
    if config is not None and config.allowed_consequences:
        return list(config.allowed_consequences)
    return list(settings.default_allowed_consequences)


def set_allowed_consequences(
    db: Session, project_id: str, consequences: list[str]
) -> AnnotationFilterConfig:
    config = get_filter_config(db, project_id)
    if config is None:
        config = AnnotationFilterConfig(
            project_id=project_id, allowed_consequences=consequences
        )
        db.add(config)
    else:
        config.allowed_consequences = consequences
    db.commit()
    db.refresh(config)
    return config


def apply_consequence_filter(annotations, allowed_consequences: list[str]):
    """Keep only annotations whose consequence is explicitly allowed.

    ``FAILED``/``UNAVAILABLE`` annotations have no consequence and are never
    treated as ``unknown``; they are excluded unless ``unknown`` is allowed and
    the annotation actually carries the ``unknown`` consequence.
    """
    allowed = set(allowed_consequences)
    return [
        annotation
        for annotation in annotations
        if annotation.status
        not in (AnnotationStatus.FAILED.value, AnnotationStatus.UNAVAILABLE.value)
        and (annotation.consequence or "") in allowed
    ]
