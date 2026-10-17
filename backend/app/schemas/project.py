from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    patient_name: str | None = Field(default=None, max_length=255)
    age: int | None = Field(default=None, ge=0, le=150)
    sex: str | None = Field(default=None, max_length=16)
    cancer_type: str | None = Field(default=None, max_length=128)
    stage: str | None = Field(default=None, max_length=64)
    diagnosis: str | None = None
    description: str | None = None
    status: str = Field(default="active", max_length=50)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    patient_name: str | None = Field(default=None, max_length=255)
    age: int | None = Field(default=None, ge=0, le=150)
    sex: str | None = Field(default=None, max_length=16)
    cancer_type: str | None = Field(default=None, max_length=128)
    stage: str | None = Field(default=None, max_length=64)
    diagnosis: str | None = None
    description: str | None = None
    status: str | None = Field(default=None, max_length=50)


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class ProjectFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    kind: str
    filename: str
    file_size_bytes: int
    input_hash: str | None
    created_at: datetime


class NoteCreate(BaseModel):
    content: str = Field(..., min_length=1)


class NoteUpdate(BaseModel):
    content: str = Field(..., min_length=1)


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    content: str
    created_at: datetime
    updated_at: datetime


class ReminderCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    due_at: datetime | None = None


class ReminderUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    due_at: datetime | None = None
    done: bool | None = None


class ReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    title: str
    due_at: datetime | None
    done: bool
    created_at: datetime
    updated_at: datetime
