from __future__ import annotations

from pathlib import Path
from time import sleep

from graph_agent_automated.core.config import Settings
from graph_agent_automated.domain.enums import Difficulty, TaskIntent, TopologyPattern
from graph_agent_automated.domain.models import (
    ActionSpec,
    ExpertBlueprint,
    OperatorBlueprint,
    SyntheticCase,
    ToolSpec,
    WorkflowBlueprint,
)
from graph_agent_automated.infrastructure.runtime.chat2graph_sdk_runtime import (
    Chat2GraphSDKRuntimeAdapter,
)


def _prepare_chat2graph_root(tmp_path: Path) -> Path:
    marker = tmp_path / "app/core/sdk/agentic_service.py"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        "class AgenticService:\n"
        "    @classmethod\n"
        "    def load(cls, yaml_path):\n"
        "        return cls()\n"
        "    def execute(self, question):\n"
        "        class _Result:\n"
        "            def get_payload(self):\n"
        "                return 'ok'\n"
        "        return _Result()\n",
        encoding="utf-8",
    )
    return tmp_path


def _build_settings(root: Path, artifacts_dir: Path, **overrides: object) -> Settings:
    base = {
        "chat2graph_root": str(root),
        "artifacts_dir": str(artifacts_dir),
        "sdk_runtime_timeout_seconds": 0.02,
        "sdk_runtime_max_retries": 0,
        "sdk_runtime_retry_backoff_seconds": 0.0,
        "sdk_runtime_circuit_failure_threshold": 3,
        "sdk_runtime_circuit_reset_seconds": 10.0,
    }
    base.update(overrides)
    return Settings(**base)


def _blueprint() -> WorkflowBlueprint:
    operator = OperatorBlueprint(
        name="worker",
        instruction="solve",
        output_schema="answer",
        actions=["use_cypherexecutor"],
    )
    expert = ExpertBlueprint(name="Expert", description="desc", operators=[operator])
    return WorkflowBlueprint(
        blueprint_id="bp-runtime",
        app_name="runtime-test",
        task_desc="query graph",
        topology=TopologyPattern.LINEAR,
        tools=[ToolSpec(name="CypherExecutor", description="query")],
        actions=[ActionSpec(name="use_cypherexecutor", description="query", tools=["CypherExecutor"])],
        experts=[expert],
        leader_actions=["use_cypherexecutor"],
    )


def _case() -> SyntheticCase:
    return SyntheticCase(
        case_id="c1",
        question="find nodes",
        verifier="ok",
        intent=TaskIntent.QUERY,
        difficulty=Difficulty.L1,
    )


class _PayloadResult:
    def __init__(self, payload: str):
        self._payload = payload

    def get_payload(self) -> str:
        return self._payload


def test_sdk_runtime_timeout_error_is_classified(tmp_path: Path) -> None:
    root = _prepare_chat2graph_root(tmp_path / "sdk_timeout_root")
    artifacts = tmp_path / "artifacts"
    settings = _build_settings(
        root=root,
        artifacts_dir=artifacts,
        sdk_runtime_timeout_seconds=0.01,
        sdk_runtime_max_retries=1,
    )
    adapter = Chat2GraphSDKRuntimeAdapter(settings=settings)

    class SlowService:
        @classmethod
        def load(cls, yaml_path: str):
            return cls()

        def execute(self, question: str):
            sleep(0.05)
            return _PayloadResult("slow")

    adapter._agentic_service_cls = SlowService
    execution = adapter.execute_case(_blueprint(), _case())

    assert execution.output.startswith("RUNTIME_ERROR[TIMEOUT]:")
    assert adapter._consecutive_failures == 1


def test_sdk_runtime_circuit_breaker_opens_after_threshold(tmp_path: Path) -> None:
    root = _prepare_chat2graph_root(tmp_path / "sdk_circuit_root")
    settings = _build_settings(
        root=root,
        artifacts_dir=tmp_path / "artifacts",
        sdk_runtime_circuit_failure_threshold=2,
        sdk_runtime_max_retries=0,
    )
    adapter = Chat2GraphSDKRuntimeAdapter(settings=settings)

    class FailingService:
        execute_calls = 0

        @classmethod
        def load(cls, yaml_path: str):
            return cls()

        def execute(self, question: str):
            type(self).execute_calls += 1
            raise RuntimeError("boom")

    adapter._agentic_service_cls = FailingService

    first = adapter.execute_case(_blueprint(), _case())
    second = adapter.execute_case(_blueprint(), _case())
    third = adapter.execute_case(_blueprint(), _case())

    assert first.output.startswith("RUNTIME_ERROR[EXECUTION_ERROR]:")
    assert second.output.startswith("RUNTIME_ERROR[EXECUTION_ERROR]:")
    assert third.output.startswith("RUNTIME_ERROR[CIRCUIT_OPEN]:")
    assert FailingService.execute_calls == 2


def test_sdk_runtime_success_resets_failure_counter(tmp_path: Path) -> None:
    root = _prepare_chat2graph_root(tmp_path / "sdk_flaky_root")
    settings = _build_settings(
        root=root,
        artifacts_dir=tmp_path / "artifacts",
        sdk_runtime_circuit_failure_threshold=3,
        sdk_runtime_max_retries=0,
    )
    adapter = Chat2GraphSDKRuntimeAdapter(settings=settings)

    class FlakyService:
        execute_calls = 0

        @classmethod
        def load(cls, yaml_path: str):
            return cls()

        def execute(self, question: str):
            type(self).execute_calls += 1
            if type(self).execute_calls == 1:
                raise RuntimeError("first call fails")
            return _PayloadResult("ok")

    adapter._agentic_service_cls = FlakyService

    failed = adapter.execute_case(_blueprint(), _case())
    assert adapter._consecutive_failures == 1
    succeeded = adapter.execute_case(_blueprint(), _case())

    assert failed.output.startswith("RUNTIME_ERROR[EXECUTION_ERROR]:")
    assert adapter._consecutive_failures == 0
    assert succeeded.output == "ok"
