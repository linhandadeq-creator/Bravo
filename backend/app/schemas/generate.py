from pydantic import BaseModel


class PipelineStage(BaseModel):
    step: str
    status: str
    detail: str | None = None


class OneClickResult(BaseModel):
    status: str
    message: str
    project_id: str
    analysis_run_id: str | None = None
    construct_id: str | None = None
    report_id: str | None = None
    candidate_count: int = 0
    stages: list[PipelineStage] = []
    blueprint: dict | None = None
    report_formats: list[str] = []
    disclaimer: str
