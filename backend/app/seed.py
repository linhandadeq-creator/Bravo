"""Seed the database with a demo project.

Usage:
    python -m app.seed
"""
from sqlalchemy import select

from app.db.session import Base, SessionLocal, engine
from app.models.project import Project

DEMO_PROJECT = {
    "name": "Demo Cancer Project",
    "description": (
        "Demonstration project for Bravo — a personalized neoantigen analysis platform."
    ),
    "status": "active",
}


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        existing = db.execute(
            select(Project).where(Project.name == DEMO_PROJECT["name"])
        ).scalar_one_or_none()
        if existing is not None:
            print(f"Demo project already exists: {existing.id}")
            return
        project = Project(**DEMO_PROJECT)
        db.add(project)
        db.commit()
        db.refresh(project)
        print(f"Created demo project: {project.id}")


if __name__ == "__main__":
    seed()
