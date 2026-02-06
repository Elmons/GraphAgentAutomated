from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from graph_agent_automated.api.dependencies import (
    AuthContext,
    get_job_queue,
    get_service,
    require_permission,
    to_tenant_scoped_agent_name,
)
from graph_agent_automated.api.schemas import (
    AsyncJobStatusResponse,
    AsyncJobSubmitResponse,
    ManualParityRequest,
    ManualParityResponse,
    OptimizeRequest,
    OptimizeResponse,
    VersionDTO,
)
from graph_agent_automated.application.services import AgentOptimizationService
from graph_agent_automated.domain.models import OptimizationReport
from graph_agent_automated.infrastructure.runtime.job_queue import AsyncJobRecord, InMemoryJobQueue

router = APIRouter(prefix="/v1/agents", tags=["agents"])


@router.post("/optimize", response_model=OptimizeResponse)
def optimize_agent(
    request: OptimizeRequest,
    service: AgentOptimizationService = Depends(get_service),
    auth: AuthContext = Depends(require_permission("optimize:run")),
) -> OptimizeResponse:
    report = service.optimize(
        agent_name=to_tenant_scoped_agent_name(request.agent_name, auth),
        task_desc=request.task_desc,
        dataset_size=request.dataset_size,
        profile=request.profile,
        seed=request.seed,
    )
    if report.registry_record is None:
        raise HTTPException(status_code=500, detail="failed to persist version record")

    return OptimizeResponse(
        **_build_optimize_response_payload(
            report=report,
            agent_name=request.agent_name,
            profile=request.profile.value,
        ),
    )


@router.post("/optimize/async", response_model=AsyncJobSubmitResponse, status_code=status.HTTP_202_ACCEPTED)
def optimize_agent_async(
    request: OptimizeRequest,
    service: AgentOptimizationService = Depends(get_service),
    job_queue: InMemoryJobQueue = Depends(get_job_queue),
    auth: AuthContext = Depends(require_permission("optimize:run")),
) -> AsyncJobSubmitResponse:
    tenant_scoped_name = to_tenant_scoped_agent_name(request.agent_name, auth)
    session_factory = service.build_session_factory()

    def runner() -> dict[str, object]:
        child_session = session_factory()
        try:
            child_service = AgentOptimizationService(session=child_session, settings=service.settings)
            report = child_service.optimize(
                agent_name=tenant_scoped_name,
                task_desc=request.task_desc,
                dataset_size=request.dataset_size,
                profile=request.profile,
                seed=request.seed,
            )
            if report.registry_record is None:
                raise ValueError("failed to persist version record")
            return _build_optimize_response_payload(
                report=report,
                agent_name=request.agent_name,
                profile=request.profile.value,
            )
        finally:
            child_session.close()

    job = job_queue.submit(
        job_type="optimize",
        tenant_id=auth.tenant_id,
        agent_name=request.agent_name,
        metadata={"profile": request.profile.value, "seed": request.seed},
        runner=runner,
    )
    return _to_async_submit_response(job)


@router.get("/{agent_name}/versions", response_model=list[VersionDTO])
def list_versions(
    agent_name: str,
    service: AgentOptimizationService = Depends(get_service),
    auth: AuthContext = Depends(require_permission("versions:read")),
) -> list[VersionDTO]:
    rows = service.list_versions(to_tenant_scoped_agent_name(agent_name, auth))
    return [VersionDTO(**row) for row in rows]


@router.post("/{agent_name}/versions/{version}/deploy", response_model=VersionDTO)
def deploy_version(
    agent_name: str,
    version: int,
    service: AgentOptimizationService = Depends(get_service),
    auth: AuthContext = Depends(require_permission("versions:deploy")),
) -> VersionDTO:
    try:
        row = service.deploy(to_tenant_scoped_agent_name(agent_name, auth), version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return VersionDTO(**row)


@router.post("/{agent_name}/versions/{version}/rollback", response_model=VersionDTO)
def rollback_version(
    agent_name: str,
    version: int,
    service: AgentOptimizationService = Depends(get_service),
    auth: AuthContext = Depends(require_permission("versions:rollback")),
) -> VersionDTO:
    try:
        row = service.rollback(to_tenant_scoped_agent_name(agent_name, auth), version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return VersionDTO(**row)


@router.post("/benchmark/manual-parity", response_model=ManualParityResponse)
def benchmark_manual_parity(
    request: ManualParityRequest,
    service: AgentOptimizationService = Depends(get_service),
    auth: AuthContext = Depends(require_permission("parity:run")),
) -> ManualParityResponse:
    try:
        report = service.benchmark_manual_parity(
            agent_name=to_tenant_scoped_agent_name(request.agent_name, auth),
            task_desc=request.task_desc,
            manual_blueprint_path=request.manual_blueprint_path,
            dataset_size=request.dataset_size,
            profile=request.profile,
            seed=request.seed,
            parity_margin=request.parity_margin,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ManualParityResponse(
        run_id=report.run_id,
        profile=report.profile,
        split=report.split,
        auto_score=report.auto_score,
        manual_score=report.manual_score,
        score_delta=report.score_delta,
        parity_margin=report.parity_margin,
        parity_achieved=report.parity_achieved,
        auto_artifact_path=report.auto_artifact_path,
        manual_blueprint_path=report.manual_blueprint_path,
        evaluated_cases=report.evaluated_cases,
    )


@router.post(
    "/benchmark/manual-parity/async",
    response_model=AsyncJobSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def benchmark_manual_parity_async(
    request: ManualParityRequest,
    service: AgentOptimizationService = Depends(get_service),
    job_queue: InMemoryJobQueue = Depends(get_job_queue),
    auth: AuthContext = Depends(require_permission("parity:run")),
) -> AsyncJobSubmitResponse:
    tenant_scoped_name = to_tenant_scoped_agent_name(request.agent_name, auth)
    session_factory = service.build_session_factory()

    def runner() -> dict[str, object]:
        child_session = session_factory()
        try:
            child_service = AgentOptimizationService(session=child_session, settings=service.settings)
            report = child_service.benchmark_manual_parity(
                agent_name=tenant_scoped_name,
                task_desc=request.task_desc,
                manual_blueprint_path=request.manual_blueprint_path,
                dataset_size=request.dataset_size,
                profile=request.profile,
                seed=request.seed,
                parity_margin=request.parity_margin,
            )
        finally:
            child_session.close()
        return {
            "run_id": report.run_id,
            "profile": report.profile.value,
            "split": report.split,
            "auto_score": report.auto_score,
            "manual_score": report.manual_score,
            "score_delta": report.score_delta,
            "parity_margin": report.parity_margin,
            "parity_achieved": report.parity_achieved,
            "auto_artifact_path": report.auto_artifact_path,
            "manual_blueprint_path": report.manual_blueprint_path,
            "evaluated_cases": report.evaluated_cases,
        }

    job = job_queue.submit(
        job_type="manual_parity",
        tenant_id=auth.tenant_id,
        agent_name=request.agent_name,
        metadata={"profile": request.profile.value, "seed": request.seed},
        runner=runner,
    )
    return _to_async_submit_response(job)


@router.get("/jobs/{job_id}", response_model=AsyncJobStatusResponse)
def get_async_job_status(
    job_id: str,
    job_queue: InMemoryJobQueue = Depends(get_job_queue),
    auth: AuthContext = Depends(require_permission("versions:read")),
) -> AsyncJobStatusResponse:
    job = job_queue.get(job_id)
    if job is None or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="job not found")
    return _to_async_status_response(job)


def _build_optimize_response_payload(
    report: OptimizationReport,
    agent_name: str,
    profile: str,
) -> dict[str, object]:
    if report.registry_record is None:
        raise ValueError("failed to persist version record")
    return {
        "run_id": report.run_id,
        "profile": profile,
        "agent_name": agent_name,
        "version": report.registry_record.version,
        "blueprint_id": report.best_blueprint.blueprint_id,
        "train_score": report.best_evaluation.mean_score,
        "val_score": (
            report.validation_evaluation.mean_score
            if report.validation_evaluation is not None
            else None
        ),
        "test_score": report.test_evaluation.mean_score if report.test_evaluation is not None else None,
        "artifact_path": report.registry_record.artifact_path,
        "evaluated_cases": report.best_evaluation.total_cases,
    }


def _to_async_submit_response(job: AsyncJobRecord) -> AsyncJobSubmitResponse:
    return AsyncJobSubmitResponse(
        job_id=job.job_id,
        job_type=job.job_type,
        status=job.status,
        tenant_id=job.tenant_id,
        agent_name=job.agent_name,
        created_at=job.created_at,
        updated_at=job.updated_at,
        metadata=job.metadata,
    )


def _to_async_status_response(job: AsyncJobRecord) -> AsyncJobStatusResponse:
    return AsyncJobStatusResponse(
        job_id=job.job_id,
        job_type=job.job_type,
        status=job.status,
        tenant_id=job.tenant_id,
        agent_name=job.agent_name,
        created_at=job.created_at,
        updated_at=job.updated_at,
        result=job.result,
        error=job.error,
        metadata=job.metadata,
    )
