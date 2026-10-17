from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_run_id: str
    sample_id: str | None
    sample_role: str
    line_number: int | None
    chromosome: str | None
    chromosome_normalized: str | None
    chromosome_normalized_flag: bool
    position: int | None
    reference: str | None
    alternate: str | None
    quality: float | None
    filter: str | None
    depth: int | None
    allele_frequency: float | None
    genotype: str | None
    variant_type: str | None
    record_id: str | None
    is_valid: bool
    is_duplicate: bool
    is_malformed: bool
    invalid_reason: str | None
    created_at: datetime
