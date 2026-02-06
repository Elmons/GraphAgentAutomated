from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from graph_agent_automated.application.profiles import resolve_optimization_knobs
from graph_agent_automated.core.config import Settings, get_settings
from graph_agent_automated.domain.enums import AgentLifecycle, ExperimentProfile
from graph_agent_automated.domain.models import (
    AgentVersionRecord,
    CaseExecution,
    EvaluationSummary,
    ManualParityReport,
    OptimizationKnobs,
    OptimizationReport,
    SearchConfig,
    SyntheticCase,
)
from graph_agent_automated.infrastructure.evaluation.failure_taxonomy import (
    build_failure_taxonomy,
)
from graph_agent_automated.infrastructure.evaluation.judges import (
    build_default_judge_ensemble,
    build_single_judge,
)
from graph_agent_automated.infrastructure.evaluation.workflow_evaluator import (
    ReflectionWorkflowEvaluator,
)
from graph_agent_automated.infrastructure.optimization.prompt_optimizer import (
    CandidatePromptOptimizer,
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
from graph_agent_automated.infrastructure.runtime.workflow_loader import WorkflowBlueprintLoader
from graph_agent_automated.infrastructure.synthesis.dynamic_synthesizer import (
    DynamicDatasetSynthesizer,
)


class AgentOptimizationService:
    """Application service orchestrating synthesis, optimization, evaluation, and persistence."""

    def __init__(self, session: Session, settings: Settings | None = None):
        self._session = session
        self._settings = settings or get_settings()

    @property
    def settings(self) -> Settings:
        return self._settings

    def optimize(
        self,
        agent_name: str,
        task_desc: str,
        dataset_size: int | None = None,
        profile: ExperimentProfile = ExperimentProfile.FULL_SYSTEM,
        seed: int | None = None,
    ) -> OptimizationReport:
        run_id = f"run-{uuid4().hex[:12]}"
        knobs = resolve_optimization_knobs(profile)
        runtime = self._build_runtime()
        judge = (
            build_default_judge_ensemble(self._settings)
            if knobs.use_ensemble_judge
            else build_single_judge(self._settings)
        )

        synthesizer = DynamicDatasetSynthesizer(
            runtime=runtime,
            random_seed=seed if seed is not None else (None if knobs.dynamic_dataset else 7),
            train_ratio=self._settings.train_ratio,
            val_ratio=self._settings.val_ratio,
            test_ratio=self._settings.test_ratio,
            enable_hard_negatives=knobs.enable_hard_negatives,
            enable_paraphrase=knobs.enable_paraphrase,
        )
        data_size = dataset_size or self._settings.default_dataset_size
        dataset = synthesizer.synthesize(task_desc=task_desc, dataset_name=agent_name, size=data_size)

        tool_catalog = runtime.fetch_tool_catalog()
        selector = IntentAwareToolSelector()
        intents = infer_intents(dataset.cases)
        selected_tools = selector.rank(
            task_desc=task_desc,
            intents=[intent.value for intent in intents],
            catalog=tool_catalog,
            top_k=min(6, max(2, len(tool_catalog))),
        )

        root = build_initial_blueprint(
            app_name=agent_name,
            task_desc=task_desc,
            selected_tools=selected_tools,
        )

        evaluator = ReflectionWorkflowEvaluator(runtime=runtime, judge=judge)
        prompt_optimizer = CandidatePromptOptimizer(max_candidates=self._settings.max_prompt_candidates)
        search = AFlowXSearchEngine(
            evaluator=evaluator,
            prompt_optimizer=prompt_optimizer,
            tool_selector=selector,
            config=SearchConfig(
                rounds=self._settings.max_search_rounds,
                expansions_per_round=self._settings.max_expansions_per_round,
                max_prompt_candidates=self._settings.max_prompt_candidates,
                train_ratio=self._settings.train_ratio,
                val_ratio=self._settings.val_ratio,
                test_ratio=self._settings.test_ratio,
                enable_prompt_mutation=knobs.enable_prompt_mutation,
                enable_tool_mutation=knobs.enable_tool_mutation,
                enable_topology_mutation=knobs.enable_topology_mutation,
                use_holdout=knobs.use_holdout,
                enable_tool_historical_gain=knobs.enable_tool_historical_gain,
                uncertainty_penalty=knobs.uncertainty_penalty,
                generalization_penalty=knobs.generalization_penalty,
            ),
        )
        result = search.optimize(
            root_blueprint=root,
            dataset=dataset,
            intents=intents,
            tool_catalog=tool_catalog,
        )
        result.best_blueprint.metadata.update(
            {
                "profile": profile.value,
                "seed": seed,
                "run_id": run_id,
            }
        )

        artifact_dir = self._settings.artifacts_path / "agents" / agent_name / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        workflow_path = runtime.materialize(result.best_blueprint, artifact_dir)
        self._write_report_artifacts(
            artifact_dir=artifact_dir,
            result=result,
            dataset=dataset,
            run_id=run_id,
            profile=profile,
            seed=seed,
            knobs=knobs,
        )

        report = OptimizationReport(
            run_id=run_id,
            dataset=dataset,
            best_blueprint=result.best_blueprint,
            best_evaluation=result.best_evaluation,
            validation_evaluation=result.validation_evaluation,
            test_evaluation=result.test_evaluation,
            round_traces=result.round_traces,
            history=result.history,
            registry_record=None,
        )

        repo = AgentRepository(self._session)
        run_row = repo.create_optimization_run(
            agent_name=agent_name,
            task_desc=task_desc,
            artifact_dir=str(artifact_dir),
            report=report,
        )
        repo.add_round_traces(run_row.id, result.round_traces)

        version_row = repo.create_version(
            agent_name=agent_name,
            blueprint=result.best_blueprint,
            evaluation=result.validation_evaluation or result.best_evaluation,
            artifact_path=str(workflow_path),
            run_db_id=run_row.id,
            lifecycle=AgentLifecycle.VALIDATED,
            notes="optimized by GraphAgentAutomated-v2",
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
        report.registry_record = registry_record
        return report

    def benchmark_manual_parity(
        self,
        agent_name: str,
        task_desc: str,
        manual_blueprint_path: str,
        dataset_size: int | None = None,
        profile: ExperimentProfile = ExperimentProfile.FULL_SYSTEM,
        seed: int | None = None,
        parity_margin: float = 0.03,
    ) -> ManualParityReport:
        resolved_manual_blueprint_path = self._resolve_manual_blueprint_path(manual_blueprint_path)
        loader = WorkflowBlueprintLoader()
        manual_blueprint = loader.load(
            path=resolved_manual_blueprint_path,
            app_name=agent_name,
            task_desc=task_desc,
        )

        auto_report = self.optimize(
            agent_name=agent_name,
            task_desc=task_desc,
            dataset_size=dataset_size,
            profile=profile,
            seed=seed,
        )
        if auto_report.registry_record is None:
            raise ValueError("auto optimization report does not contain persisted artifact")

        knobs = resolve_optimization_knobs(profile)
        runtime = self._build_runtime()
        judge = (
            build_default_judge_ensemble(self._settings)
            if knobs.use_ensemble_judge
            else build_single_judge(self._settings)
        )
        evaluator = ReflectionWorkflowEvaluator(runtime=runtime, judge=judge)

        split, cases = self._select_parity_split(auto_report)
        manual_eval = evaluator.evaluate(manual_blueprint, cases, split=split)
        auto_eval = self._select_auto_eval(auto_report, split)

        auto_score = auto_eval.mean_score
        manual_score = manual_eval.mean_score
        score_delta = auto_score - manual_score
        parity_achieved = auto_score + parity_margin >= manual_score
        failure_taxonomy = build_failure_taxonomy(
            auto_eval=auto_eval,
            manual_eval=manual_eval,
            failure_margin=parity_margin,
        )

        artifact_path = auto_report.registry_record.artifact_path
        artifact_dir = Path(artifact_path).resolve().parent
        report_payload = {
            "run_id": auto_report.run_id,
            "profile": profile.value,
            "split": split,
            "auto_score": auto_score,
            "manual_score": manual_score,
            "score_delta": score_delta,
            "parity_margin": parity_margin,
            "parity_achieved": parity_achieved,
            "manual_blueprint_path": str(resolved_manual_blueprint_path),
            "evaluated_cases": manual_eval.total_cases,
            "auto_artifact_path": artifact_path,
            "failure_taxonomy": failure_taxonomy,
        }
        with open(artifact_dir / "manual_parity_report.json", "w", encoding="utf-8") as f:
            json.dump(report_payload, f, ensure_ascii=False, indent=2)
        with open(artifact_dir / "manual_parity_case_report.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "run_id": auto_report.run_id,
                    "split": split,
                    "parity_margin": parity_margin,
                    "auto_cases": [self._serialize_case_execution(case) for case in auto_eval.case_results],
                    "manual_cases": [
                        self._serialize_case_execution(case) for case in manual_eval.case_results
                    ],
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        return ManualParityReport(
            run_id=auto_report.run_id,
            profile=profile,
            split=split,
            auto_score=auto_score,
            manual_score=manual_score,
            score_delta=score_delta,
            parity_margin=parity_margin,
            parity_achieved=parity_achieved,
            auto_artifact_path=artifact_path,
            manual_blueprint_path=str(resolved_manual_blueprint_path),
            evaluated_cases=manual_eval.total_cases,
            failure_taxonomy=failure_taxonomy,
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

    def build_session_factory(self) -> sessionmaker[Session]:
        bind = self._session.get_bind()
        return sessionmaker(bind=bind, class_=Session, autocommit=False, autoflush=False)

    def _write_report_artifacts(
        self,
        artifact_dir: Path,
        result,
        dataset,
        run_id: str,
        profile: ExperimentProfile,
        seed: int | None,
        knobs: OptimizationKnobs,
    ) -> None:
        with open(artifact_dir / "dataset_report.json", "w", encoding="utf-8") as f:
            json.dump(dataset.synthesis_report, f, ensure_ascii=False, indent=2)

        with open(artifact_dir / "round_traces.json", "w", encoding="utf-8") as f:
            json.dump([asdict(trace) for trace in result.round_traces], f, ensure_ascii=False, indent=2)

        with open(artifact_dir / "prompt_variants.json", "w", encoding="utf-8") as f:
            json.dump([asdict(variant) for variant in result.prompt_variants], f, ensure_ascii=False, indent=2)

        summary = {
            "run_id": run_id,
            "best_blueprint_id": result.best_blueprint.blueprint_id,
            "train_score": result.best_evaluation.mean_score,
            "val_score": (
                result.validation_evaluation.mean_score
                if result.validation_evaluation is not None
                else None
            ),
            "test_score": result.test_evaluation.mean_score if result.test_evaluation else None,
            "tool_gain": result.historical_tool_gain,
            "profile": profile.value,
            "seed": seed,
            "knobs": asdict(knobs),
        }
        with open(artifact_dir / "run_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    def _build_runtime(self):
        if self._settings.chat2graph_runtime_mode.lower() == "sdk":
            return Chat2GraphSDKRuntimeAdapter(self._settings)
        return MockRuntimeAdapter()

    def _resolve_manual_blueprint_path(self, manual_blueprint_path: str) -> Path:
        allowed_root = self._settings.manual_blueprints_path.resolve()
        raw_path = Path(manual_blueprint_path).expanduser()
        resolved_path = (
            raw_path.resolve()
            if raw_path.is_absolute()
            else (allowed_root / raw_path).resolve()
        )

        if not resolved_path.is_relative_to(allowed_root):
            raise ValueError(
                f"manual blueprint path must be under MANUAL_BLUEPRINTS_DIR: {allowed_root}"
            )
        if not resolved_path.exists() or not resolved_path.is_file():
            raise ValueError(f"manual blueprint file not found: {resolved_path}")
        return resolved_path

    def _select_parity_split(
        self,
        report: OptimizationReport,
    ) -> tuple[str, list[SyntheticCase]]:
        if report.test_evaluation is not None and report.dataset.test_cases:
            return "test", list(report.dataset.test_cases)
        if report.validation_evaluation is not None and report.dataset.val_cases:
            return "val", list(report.dataset.val_cases)
        return "train", list(report.dataset.train_cases or report.dataset.cases)

    def _select_auto_eval(
        self,
        report: OptimizationReport,
        split: str,
    ) -> EvaluationSummary:
        if split == "test" and report.test_evaluation is not None:
            return report.test_evaluation
        if split == "val" and report.validation_evaluation is not None:
            return report.validation_evaluation
        return report.best_evaluation

    def _serialize_case_execution(self, case: CaseExecution) -> dict[str, object]:
        return {
            "case_id": case.case_id,
            "question": case.question,
            "expected": case.expected,
            "output": case.output,
            "score": float(case.score),
            "rationale": case.rationale,
            "latency_ms": float(case.latency_ms),
            "token_cost": float(case.token_cost),
            "confidence": float(case.confidence),
            "judge_votes": [
                {
                    "judge_name": vote.judge_name,
                    "score": float(vote.score),
                    "rationale": vote.rationale,
                }
                for vote in case.judge_votes
            ],
        }
