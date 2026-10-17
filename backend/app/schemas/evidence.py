from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EvidenceProviderRead(BaseModel):
    name: str
    provider_name: str
    provider_version: str
    is_mock: bool
    supported_builds: list[str]
    status: str
    description: str


class EvidenceRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_run_id: str
    variant_id: str
    provider: str
    source: str
    provider_version: str
    status: str
    population_frequency: float | None
    known_driver: bool | None
    clinical_significance: str | None
    identifiers: list | None
    detail: dict | None
    created_at: datetime


class EvidenceAnnotateRequest(BaseModel):
    providers: list[str] | None = None
    variant_ids: list[str] | None = None
