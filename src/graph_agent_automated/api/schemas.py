from __future__ import annotations

from pydantic import BaseModel, Field

from graph_agent_automated.domain.enums import ExperimentProfile


class OptimizeRequest(BaseModel):
    agent_name: str = Field(min_length=1, max_length=128)
    task_desc: str = Field(min_length=1)
    dataset_size: int | None = Field(default=None, ge=6, le=30)
    profile: ExperimentProfile = ExperimentProfile.FULL_SYSTEM
    seed: int | None = Field(default=None, ge=1, le=1_000_000)


class OptimizeResponse(BaseModel):
    run_id: str
    profile: ExperimentProfile
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


class ManualParityRequest(BaseModel):
    agent_name: str = Field(min_length=1, max_length=128)
    task_desc: str = Field(min_length=1)
    manual_blueprint_path: str = Field(min_length=1)
    dataset_size: int | None = Field(default=None, ge=6, le=30)
    profile: ExperimentProfile = ExperimentProfile.FULL_SYSTEM
    seed: int | None = Field(default=None, ge=1, le=1_000_000)
    parity_margin: float = Field(default=0.03, ge=0.0, le=0.2)


class ManualParityResponse(BaseModel):
    run_id: str
    profile: ExperimentProfile
    split: str
    auto_score: float
    manual_score: float
    score_delta: float
    parity_margin: float
    parity_achieved: bool
    auto_artifact_path: str
    manual_blueprint_path: str
    evaluated_cases: int
    failure_taxonomy: dict[str, object] = Field(default_factory=dict)


class AsyncJobSubmitResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    tenant_id: str
    agent_name: str
    created_at: str
    updated_at: str
    metadata: dict[str, object] = Field(default_factory=dict)


class AsyncJobStatusResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    tenant_id: str
    agent_name: str
    created_at: str
    updated_at: str
    result: dict[str, object] | None = None
    error: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class MessageResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str


class MetricsResponse(BaseModel):
    requests_total: int
    errors_total: int
    async_jobs_submitted_total: int
    async_jobs_succeeded_total: int
    async_jobs_failed_total: int
    endpoints: dict[str, dict[str, float | int]]
