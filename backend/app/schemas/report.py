from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_run_id: str
    project_id: str
    title: str
    format: str
    status: str
    summary: dict | None
    software_version: str
    generated_by: str | None
    created_at: datetime


class ReportDetail(ReportRead):
    content: str | None = None


class ReportCreate(BaseModel):
    format: str = Field(default="markdown")
    generated_by: str | None = None
