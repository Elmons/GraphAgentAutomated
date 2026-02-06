from __future__ import annotations

from sqlalchemy.orm import Session

from graph_agent_automated.core.config import Settings, get_settings
from graph_agent_automated.domain.enums import AgentLifecycle
from graph_agent_automated.domain.models import AgentVersionRecord, OptimizationReport, SearchConfig
from graph_agent_automated.infrastructure.evaluation.judges import HeuristicJudge, OpenAIJudge
from graph_agent_automated.infrastructure.evaluation.workflow_evaluator import (
    ReflectionWorkflowEvaluator,
)
from graph_agent_automated.infrastructure.optimization.prompt_optimizer import (
    ReflectionPromptOptimizer,
)
from graph_agent_automated.infrastructure.optimization.search_engine import (
    AFlowXSearchEngine,
    build_initial_blueprint,
    infer_intents,
)
from graph_agent_automated.infrastructure.optimization.tool_selector import IntentAwareToolSelector
from graph_agent_automated.infrastructure.persistence.repositories import (
    AgentRepository,
    list_to_dict,
    to_version_dict,
)
from graph_agent_automated.infrastructure.runtime.chat2graph_sdk_runtime import (
    Chat2GraphSDKRuntimeAdapter,
)
from graph_agent_automated.infrastructure.runtime.mock_runtime import MockRuntimeAdapter
from graph_agent_automated.infrastructure.synthesis.dynamic_synthesizer import (
    DynamicDatasetSynthesizer,
)


class AgentOptimizationService:
    """Application service orchestrating synthesis, optimization, evaluation, and persistence."""

    def __init__(self, session: Session, settings: Settings | None = None):
        self._session = session
        self._settings = settings or get_settings()

    def optimize(self, agent_name: str, task_desc: str, dataset_size: int | None = None) -> OptimizationReport:
        runtime = self._build_runtime()
        judge = self._build_judge()

        synthesizer = DynamicDatasetSynthesizer(runtime=runtime)
        data_size = dataset_size or self._settings.default_dataset_size
        dataset = synthesizer.synthesize(task_desc=task_desc, dataset_name=agent_name, size=data_size)

        tool_catalog = runtime.fetch_tool_catalog()
        selector = IntentAwareToolSelector()
        intents = infer_intents(dataset.cases)
        selected_tools = selector.rank(
            task_desc=task_desc,
            intents=[intent.value for intent in intents],
            catalog=tool_catalog,
            top_k=min(4, max(2, len(tool_catalog))),
        )

        root = build_initial_blueprint(
            app_name=agent_name,
            task_desc=task_desc,
            selected_tools=selected_tools,
        )

        evaluator = ReflectionWorkflowEvaluator(runtime=runtime, judge=judge)
        search = AFlowXSearchEngine(
            evaluator=evaluator,
            prompt_optimizer=ReflectionPromptOptimizer(),
            tool_selector=selector,
            config=SearchConfig(
                rounds=self._settings.max_search_rounds,
                expansions_per_round=self._settings.max_expansions_per_round,
            ),
        )
        result = search.optimize(
            root_blueprint=root,
            cases=dataset.cases,
            intents=intents,
            tool_catalog=tool_catalog,
        )

        artifact_dir = (
            self._settings.artifacts_path
            / "agents"
            / agent_name
            / f"{result.best_blueprint.blueprint_id}"
        )
        artifact_path = runtime.materialize(result.best_blueprint, artifact_dir)

        repo = AgentRepository(self._session)
        version_row = repo.create_version(
            agent_name=agent_name,
            blueprint=result.best_blueprint,
            evaluation=result.best_evaluation,
            artifact_path=str(artifact_path),
            lifecycle=AgentLifecycle.VALIDATED,
            notes="optimized by GraphAgentAutomated",
        )
        self._session.commit()
        registry_record = AgentVersionRecord(
            agent_name=agent_name,
            version=int(version_row.version),
            lifecycle=version_row.lifecycle,
            blueprint_id=version_row.blueprint_id,
            score=float(version_row.score),
            artifact_path=version_row.artifact_path,
            created_at=version_row.created_at.isoformat(),
            notes=version_row.notes,
        )

        return OptimizationReport(
            dataset=dataset,
            best_blueprint=result.best_blueprint,
            best_evaluation=result.best_evaluation,
            history=result.history,
            registry_record=registry_record,
        )

    def list_versions(self, agent_name: str) -> list[dict[str, object]]:
        repo = AgentRepository(self._session)
        rows = repo.list_versions(agent_name)
        return list_to_dict(rows)

    def deploy(self, agent_name: str, version: int) -> dict[str, object]:
        repo = AgentRepository(self._session)
        row = repo.update_lifecycle(agent_name, version, AgentLifecycle.DEPLOYED)
        self._session.commit()
        return to_version_dict(row)

    def rollback(self, agent_name: str, version: int) -> dict[str, object]:
        repo = AgentRepository(self._session)
        row = repo.update_lifecycle(agent_name, version, AgentLifecycle.DEPLOYED)
        self._session.commit()
        return to_version_dict(row)

    def _build_runtime(self):
        if self._settings.chat2graph_runtime_mode.lower() == "sdk":
            return Chat2GraphSDKRuntimeAdapter(self._settings)
        return MockRuntimeAdapter()

    def _build_judge(self):
        if self._settings.judge_backend.lower() == "openai":
            return OpenAIJudge(self._settings)
        return HeuristicJudge()
