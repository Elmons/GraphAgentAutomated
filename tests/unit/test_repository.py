from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from graph_agent_automated.domain.enums import (
    AgentLifecycle,
    TopologyPattern,
)
from graph_agent_automated.domain.models import (
    ActionSpec,
    CaseExecution,
    EvaluationSummary,
    ExpertBlueprint,
    OperatorBlueprint,
    OptimizationReport,
    SearchRoundTrace,
    SyntheticDataset,
    ToolSpec,
    WorkflowBlueprint,
)
from graph_agent_automated.infrastructure.persistence.models import Base
from graph_agent_automated.infrastructure.persistence.repositories import AgentRepository


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    maker = sessionmaker(bind=engine, class_=Session, autocommit=False, autoflush=False)
    return maker()


def _blueprint(blueprint_id: str) -> WorkflowBlueprint:
    op = OperatorBlueprint("worker", "do", "answer", ["use_cypherexecutor"])
    expert = ExpertBlueprint(name="Expert", description="desc", operators=[op])
    return WorkflowBlueprint(
        blueprint_id=blueprint_id,
        app_name="agentA",
        task_desc="task",
        topology=TopologyPattern.LINEAR,
        tools=[ToolSpec(name="CypherExecutor")],
        actions=[ActionSpec(name="use_cypherexecutor", description="d", tools=["CypherExecutor"])],
        experts=[expert],
        leader_actions=["use_cypherexecutor"],
    )


def _evaluation(blueprint_id: str, score: float) -> EvaluationSummary:
    case = CaseExecution(
        case_id="c1",
        question="q",
        expected="a",
        output="a",
        score=score,
        rationale="ok",
        latency_ms=10,
        token_cost=0.001,
    )
    return EvaluationSummary(
        blueprint_id=blueprint_id,
        mean_score=score,
        mean_latency_ms=10,
        mean_token_cost=0.001,
        total_cases=1,
        reflection="ok",
        case_results=[case],
    )


def test_repository_version_and_deploy_flow() -> None:
    session = _session()
    repo = AgentRepository(session)

    v1 = repo.create_version(
        agent_name="agentA",
        blueprint=_blueprint("bp-1"),
        evaluation=_evaluation("bp-1", 0.7),
        artifact_path="/tmp/a.yml",
        lifecycle=AgentLifecycle.VALIDATED,
    )
    session.commit()

    assert v1.version == 1

    v2 = repo.create_version(
        agent_name="agentA",
        blueprint=_blueprint("bp-2"),
        evaluation=_evaluation("bp-2", 0.8),
        artifact_path="/tmp/b.yml",
        lifecycle=AgentLifecycle.VALIDATED,
    )
    session.commit()
    assert v2.version == 2

    deployed = repo.update_lifecycle("agentA", 2, AgentLifecycle.DEPLOYED)
    session.commit()
    assert deployed.lifecycle == AgentLifecycle.DEPLOYED

    versions = repo.list_versions("agentA")
    assert len(versions) == 2

    first = repo.get_version("agentA", 1)
    assert first.blueprint_id == "bp-1"


def test_repository_persists_optimization_run_and_traces() -> None:
    session = _session()
    repo = AgentRepository(session)
    blueprint = _blueprint("bp-run")
    evaluation = _evaluation("bp-run", 0.82)
    dataset = SyntheticDataset(name="d", task_desc="t", cases=[])
    report = OptimizationReport(
        run_id="run-test",
        dataset=dataset,
        best_blueprint=blueprint,
        best_evaluation=evaluation,
        validation_evaluation=evaluation,
        test_evaluation=evaluation,
        round_traces=[],
        history=[evaluation],
    )

    run = repo.create_optimization_run(
        agent_name="agentA",
        task_desc="task",
        artifact_dir="/tmp/run",
        report=report,
    )
    repo.add_round_traces(
        run.id,
        [
            SearchRoundTrace(
                round_num=1,
                selected_node_id="n1",
                selected_blueprint_id="bp-run",
                mutation="prompt:optimize(worker)",
                train_objective=0.7,
                val_objective=0.68,
                best_train_objective=0.7,
                best_val_objective=0.68,
                improvement=0.03,
                regret=0.0,
            )
        ],
    )
    session.commit()

    version = repo.create_version(
        agent_name="agentA",
        blueprint=blueprint,
        evaluation=evaluation,
        artifact_path="/tmp/bp-run.yml",
        run_db_id=run.id,
    )
    session.commit()

    assert run.run_id == "run-test"
    assert version.run_id == run.id
