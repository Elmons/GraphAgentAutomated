from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from graph_agent_automated.api.dependencies import get_service
from graph_agent_automated.api.schemas import OptimizeRequest, OptimizeResponse, VersionDTO
from graph_agent_automated.application.services import AgentOptimizationService

router = APIRouter(prefix="/v1/agents", tags=["agents"])


@router.post("/optimize", response_model=OptimizeResponse)
def optimize_agent(
    request: OptimizeRequest,
    service: AgentOptimizationService = Depends(get_service),
) -> OptimizeResponse:
    report = service.optimize(
        agent_name=request.agent_name,
        task_desc=request.task_desc,
        dataset_size=request.dataset_size,
    )
    if report.registry_record is None:
        raise HTTPException(status_code=500, detail="failed to persist version record")

    return OptimizeResponse(
        run_id=report.run_id,
        agent_name=request.agent_name,
        version=report.registry_record.version,
        blueprint_id=report.best_blueprint.blueprint_id,
        train_score=report.best_evaluation.mean_score,
        val_score=(
            report.validation_evaluation.mean_score
            if report.validation_evaluation is not None
            else None
        ),
        test_score=report.test_evaluation.mean_score if report.test_evaluation is not None else None,
        artifact_path=report.registry_record.artifact_path,
        evaluated_cases=report.best_evaluation.total_cases,
    )


@router.get("/{agent_name}/versions", response_model=list[VersionDTO])
def list_versions(
    agent_name: str,
    service: AgentOptimizationService = Depends(get_service),
) -> list[VersionDTO]:
    rows = service.list_versions(agent_name)
    return [VersionDTO(**row) for row in rows]


@router.post("/{agent_name}/versions/{version}/deploy", response_model=VersionDTO)
def deploy_version(
    agent_name: str,
    version: int,
    service: AgentOptimizationService = Depends(get_service),
) -> VersionDTO:
    try:
        row = service.deploy(agent_name, version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return VersionDTO(**row)


@router.post("/{agent_name}/versions/{version}/rollback", response_model=VersionDTO)
def rollback_version(
    agent_name: str,
    version: int,
    service: AgentOptimizationService = Depends(get_service),
) -> VersionDTO:
    try:
        row = service.rollback(agent_name, version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return VersionDTO(**row)
