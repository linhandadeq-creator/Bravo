from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SomaticCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_run_id: str
    chromosome: str
    position: int
    reference: str
    alternate: str
    classification: str
    tumor_allele_frequency: float | None
    normal_allele_frequency: float | None
    tumor_depth: int | None
    normal_depth: int | None
    tumor_genotype: str | None
    normal_genotype: str | None
    note: str | None
    created_at: datetime
