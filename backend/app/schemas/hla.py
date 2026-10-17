from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HLAProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_run_id: str
    allele: str | None
    allele_raw: str | None
    allele_class: str | None
    locus: str | None
    source: str | None
    method: str | None
    confidence: float | None
    version: str | None
    is_valid: bool
    is_duplicate: bool
    invalid_reason: str | None
    normalization_method: str | None
    input_hash: str | None
    timestamp: datetime | None
    created_at: datetime


class HlaStatusRead(BaseModel):
    status: str
    total: int
    valid: int
    invalid: int
    duplicate: int
    class_i: int
    class_ii: int
    normalization_method: str
    normalization_version: str
    message: str


class HlaIngestRequest(BaseModel):
    alleles: list[dict]
    source: str | None = None
    method: str | None = None
    version: str | None = None
