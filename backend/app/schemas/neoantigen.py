from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.annotation import AnnotationRead
from app.schemas.variant import VariantRead


class PredictionProviderRead(BaseModel):
    name: str
    provider_name: str
    provider_version: str
    is_mock: bool
    supported_hla: list[str]
    status: str
    description: str


class PredictionResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    candidate_id: str
    hla: str | None
    prediction_value: float | None
    metric_name: str | None
    provider: str | None
    provider_version: str | None
    status: str | None
    input_hash: str | None
    detail: dict | None
    timestamp: datetime | None


class NeoantigenCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_run_id: str
    variant_id: str | None
    gene: str | None
    gene_id: str | None
    transcript: str | None
    transcript_id: str | None
    protein_change: str | None
    consequence: str | None
    impact: str | None
    peptide_representation: str
    peptide_sequence: str | None
    hla_allele: str | None
    hla_class: str | None
    expression_evidence: dict | None
    mutation_evidence: dict | None
    prediction_status: str
    status: str
    ranking_score: float | None
    ranking_evidence: dict | None
    ranking_configuration_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class RankingConfigRead(BaseModel):
    id: str
    project_id: str
    name: str
    weights: dict
    version: str
    disclaimer: str


class RankingConfigUpdate(BaseModel):
    weights: dict[str, float] = Field(default_factory=dict)


class NeoantigenRunRequest(BaseModel):
    provider: str | None = None
    weights: dict[str, float] | None = None


class NeoantigenRunSummary(BaseModel):
    generated: int
    rejected: int
    prediction: dict
    ranking: dict


class CandidateDetailRead(BaseModel):
    candidate: NeoantigenCandidateRead
    variant: VariantRead | None
    annotation: AnnotationRead | None
    predictions: list[PredictionResultRead]
    provider: str | None
    provider_version: str | None
    provider_is_mock: bool
    disclaimer: str
