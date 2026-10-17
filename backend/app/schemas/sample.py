from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SampleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    name: str
    sample_type: str
    reference_build: str | None
    original_filename: str | None
    file_size_bytes: int | None
    source: str
    created_at: datetime
