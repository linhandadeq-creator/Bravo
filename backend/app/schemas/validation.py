from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ValidationCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category: str
    step: str
    name: str
    expected_result: Any = None
    actual_result: Any = None
    status: str
    critical: bool
    detail: str | None
    created_at: datetime


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    step: str
    timestamp: datetime
    input: dict | None
    output: dict | None
    provider: str | None
    version: str | None
    parameters: dict | None
    status: str
    error: str | None


class ValidationDatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    reference_build: str | None
    created_at: datetime


class ValidationReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str | None
    software_version: str
    status: str
    total_tests: int
    passed: int
    failed: int
    warnings: int
    pipeline_health: list | None
    category_summary: dict | None
    reproducibility: dict | None
    disclaimer: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class ValidationReportDetail(ValidationReportRead):
    cases: list[ValidationCaseRead] = []
    audit_logs: list[AuditLogRead] = []
