from __future__ import annotations

from pydantic import BaseModel, Field


class OptimizeRequest(BaseModel):
    agent_name: str = Field(min_length=1, max_length=128)
    task_desc: str = Field(min_length=1)
    dataset_size: int | None = Field(default=None, ge=6, le=30)


class OptimizeResponse(BaseModel):
    run_id: str
    agent_name: str
    version: int
    blueprint_id: str
    train_score: float
    val_score: float | None = None
    test_score: float | None = None
    artifact_path: str
    evaluated_cases: int


class VersionDTO(BaseModel):
    id: int
    version: int
    lifecycle: str
    blueprint_id: str
    score: float
    artifact_path: str
    notes: str
    created_at: str


class MessageResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str
