from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SimulationFormat = Literal["mRNA-LNP", "circRNA", "saRNA"]


class ConstructItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position: int
    label: str
    candidate_id: str | None
    spacer: str | None
    selected_by: str | None
    selected_at: datetime | None
    candidate_version: str | None


class ConstructRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    analysis_run_id: str
    name: str
    simulation_format: str
    status: str
    candidate_ids: list | None
    ordering: list | None
    construct_representation: str | None
    sequence: str | None
    selected_by: str | None
    selected_at: datetime | None
    candidate_version: str | None
    qc_summary: dict | None
    validation: dict | None
    simulation_output: dict | None
    created_at: datetime
    updated_at: datetime
    items: list[ConstructItemRead] = Field(default_factory=list)


class ConstructCreate(BaseModel):
    candidate_ids: list[str] = Field(default_factory=list)
    name: str = "Simulation Construct"
    simulation_format: SimulationFormat = "mRNA-LNP"
    selected_by: str | None = None


class SelectionUpdate(BaseModel):
    candidate_ids: list[str] = Field(default_factory=list)
    selected_by: str | None = None
