from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.sample import SampleRead


class SyntheticRunRequest(BaseModel):
    project_id: str
    reference_build: str | None = Field(default=None)


class AnalysisRunCreate(BaseModel):
    project_id: str
    tumor_sample_id: str
    normal_sample_id: str
    reference_build: str | None = None


class AnalysisRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    tumor_sample_id: str | None
    normal_sample_id: str | None
    reference_build: str | None
    status: str
    mode: str
    error_message: str | None
    qc_summary: dict | None
    somatic_summary: dict | None
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None
    tumor_sample: SampleRead | None = None
    normal_sample: SampleRead | None = None
