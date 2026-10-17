from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExpressionRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_run_id: str
    level: str
    gene_id: str | None
    gene_symbol: str | None
    transcript_id: str | None
    expression_value: float | None
    unit: str | None
    source: str | None
    raw_gene_id: str | None
    raw_transcript_id: str | None
    gene_id_changed: bool
    transcript_id_changed: bool
    gene_id_resolved: bool
    is_valid: bool
    invalid_reason: str | None
    normalization_method: str | None
    input_hash: str | None
    version: str | None
    timestamp: datetime | None
    created_at: datetime


class ExpressionStatusRead(BaseModel):
    status: str
    total: int
    valid: int
    invalid: int
    gene_level: int
    transcript_level: int
    normalized_identifiers: int
    normalization_method: str
    normalization_version: str
    message: str
    quantification: dict | None = None


class ExpressionQuantificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_run_id: str
    gene_id: str | None
    gene_symbol: str | None
    tumor_value: float | None
    normal_value: float | None
    log2_fold_change: float | None
    is_expressed: bool
    differentially_expressed: bool
    note: str | None
    unit: str | None
    method: str
    version: str | None
    pseudocount: float | None
    expression_threshold: float | None
    log2fc_threshold: float | None
    samples: dict | None
    input_hash: str | None
    created_at: datetime


class ExpressionIngestRequest(BaseModel):
    records: list[dict]
    source: str | None = None
    version: str | None = None
    unit: str | None = None
