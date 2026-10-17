from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.variant import VariantRead


class ProviderRead(BaseModel):
    name: str
    provider: str
    provider_version: str
    reference_build: str
    annotation_version: str
    transcript_source: str
    description: str | None = None
    available: bool


class AnnotateRequest(BaseModel):
    provider: str | None = None
    parameters: dict | None = None


class AnnotationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    annotation_run_id: str
    variant_id: str | None
    analysis_run_id: str
    status: str
    consequence: str | None
    impact: str | None
    gene: str | None
    gene_id: str | None
    transcript: str | None
    transcript_id: str | None
    protein_change: str | None
    cds_position: int | None
    protein_position: int | None
    mutated_peptide: str | None
    known_variants: list | None = None
    clinical_significance: str | None = None
    hgvs_c: str | None = None
    hgvs_p: str | None = None
    failed_reason: str | None
    provider: str | None
    provider_version: str | None
    reference_build: str | None
    annotation_version: str | None
    transcript_source: str | None
    parameters: dict | None
    input_hash: str | None
    annotation_timestamp: datetime | None
    created_at: datetime


class AnnotationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_run_id: str
    provider: str
    provider_version: str | None
    reference_build: str | None
    annotation_version: str | None
    transcript_source: str | None
    status: str
    variant_count: int
    annotated_count: int
    partial_count: int
    failed_count: int
    parameters: dict | None
    compatibility: dict | None
    input_hash: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class AnnotatedVariantRead(BaseModel):
    variant_id: str
    sample_role: str
    chromosome: str | None
    position: int | None
    reference: str | None
    alternate: str | None
    variant_type: str | None
    status: str | None
    gene: str | None
    gene_id: str | None
    transcript: str | None
    transcript_id: str | None
    consequence: str | None
    impact: str | None
    protein_change: str | None
    cds_position: int | None
    protein_position: int | None


class VariantDetailRead(BaseModel):
    variant: VariantRead
    tumor_evidence: VariantRead | None
    normal_evidence: VariantRead | None
    annotation: AnnotationRead | None
    annotation_run: AnnotationRunRead | None
    evidence: list | None = None


class FilterConfigRead(BaseModel):
    project_id: str
    allowed_consequences: list[str]


class FilterConfigUpdate(BaseModel):
    allowed_consequences: list[str] = Field(default_factory=list)
