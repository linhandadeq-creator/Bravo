import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

FILE_KIND_TUMOR_VCF = "TUMOR_VCF"
FILE_KIND_NORMAL_VCF = "NORMAL_VCF"
FILE_KIND_HLA = "HLA"
FILE_KIND_EXPRESSION = "EXPRESSION"

SUPPORTED_FILE_KINDS = (
    FILE_KIND_TUMOR_VCF,
    FILE_KIND_NORMAL_VCF,
    FILE_KIND_HLA,
    FILE_KIND_EXPRESSION,
)


class ProjectFile(Base):
    """A file attached to a project during patient registration.

    Used to auto-fill the module uploads (VCF QC, HLA, expression): the file
    content is served back to the UI so the user can attach it to an analysis
    run without re-uploading it.
    """

    __tablename__ = "project_files"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project = relationship("Project", backref="files")
