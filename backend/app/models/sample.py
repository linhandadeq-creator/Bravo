import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

TUMOR = "TUMOR"
NORMAL = "NORMAL"
SAMPLE_TYPES = (TUMOR, NORMAL)


class Sample(Base):
    __tablename__ = "samples"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sample_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    reference_build: Mapped[str | None] = mapped_column(String(16), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="UPLOAD")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project = relationship("Project", backref="samples")
