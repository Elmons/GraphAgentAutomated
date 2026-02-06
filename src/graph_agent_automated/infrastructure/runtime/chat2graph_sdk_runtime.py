from __future__ import annotations

import importlib.util
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path
from time import monotonic, perf_counter, sleep

import yaml

from graph_agent_automated.core.config import Settings
from graph_agent_automated.domain.models import (
    CaseExecution,
    SyntheticCase,
    ToolSpec,
    WorkflowBlueprint,
)
from graph_agent_automated.infrastructure.runtime.yaml_renderer import Chat2GraphYamlRenderer


class _RuntimeExecutionTimeoutError(RuntimeError):
    """Raised when one runtime execution attempt exceeds timeout."""


class Chat2GraphSDKRuntimeAdapter:
    """External adapter that treats chat2graph as an out-of-process SDK/runtime."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._root = Path(settings.chat2graph_root).resolve()
        self._renderer = Chat2GraphYamlRenderer()
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

        if not self._root.exists():
            raise ValueError(
                "chat2graph_root does not exist. Set CHAT2GRAPH_ROOT to a valid external repository path."
            )

        self._ensure_importable(self._root)
        from app.core.sdk.agentic_service import AgenticService  # type: ignore

        self._agentic_service_cls = AgenticService

    def fetch_schema_snapshot(self) -> dict[str, object]:
        schema_file = self._settings.chat2graph_schema_file
        if schema_file:
            path = Path(schema_file)
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    payload = json.load(f)
                if isinstance(payload, dict):
                    return payload

        return {
            "labels": ["Node"],
            "relations": ["RELATED_TO"],
            "source": "fallback",
        }

    def fetch_tool_catalog(self) -> list[ToolSpec]:
        config_path = self._root / "app/core/sdk/chat2graph.yml"
        if not config_path.exists():
            return []

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        tools = config.get("tools", [])
        output: list[ToolSpec] = []
        for row in tools:
            if not isinstance(row, dict):
                continue
            output.append(
                ToolSpec(
                    name=str(row.get("name", "")),
                    module_path=str(row.get("module_path", "")),
                    description=str(row.get("desc", "")),
                    tags=[str(row.get("type", ""))],
                    tool_type=str(row.get("type", "LOCAL_TOOL")),
                )
            )
        return output

    def execute_case(self, blueprint: WorkflowBlueprint, case: SyntheticCase) -> CaseExecution:
        runtime_dir = Path(self._settings.artifacts_dir) / "runtime_tmp" / blueprint.blueprint_id
        runtime_dir.mkdir(parents=True, exist_ok=True)
        workflow_path = self.materialize(blueprint, runtime_dir)

        started = perf_counter()
        circuit_error = self._check_circuit_open()
        if circuit_error is not None:
            return self._build_runtime_error(case=case, started=started, category="CIRCUIT_OPEN", detail=circuit_error)

        max_attempts = self._settings.sdk_runtime_max_retries + 1
        last_error = "unknown runtime failure"
        last_category = "EXECUTION_ERROR"

        for attempt in range(1, max_attempts + 1):
            try:
                output_text = self._execute_once_with_timeout(workflow_path, case.question)
                self._record_success()
                return self._build_runtime_result(case=case, started=started, output_text=output_text)
            except _RuntimeExecutionTimeoutError as exc:
                last_category = "TIMEOUT"
                last_error = str(exc)
            except Exception as exc:  # pragma: no cover - depends on external runtime
                last_category = "EXECUTION_ERROR"
                last_error = str(exc)

            if attempt < max_attempts:
                delay_seconds = self._settings.sdk_runtime_retry_backoff_seconds * (2 ** (attempt - 1))
                if delay_seconds > 0:
                    sleep(delay_seconds)

        self._record_failure()
        return self._build_runtime_error(
            case=case,
            started=started,
            category=last_category,
            detail=last_error,
        )

    def materialize(self, blueprint: WorkflowBlueprint, output_dir: Path) -> Path:
        return self._renderer.render(blueprint, output_dir / "workflow.yml")

    def _execute_once_with_timeout(self, workflow_path: Path, question: str) -> str:
        timeout_seconds = self._settings.sdk_runtime_timeout_seconds
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self._execute_once, workflow_path, question)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError as exc:
            future.cancel()
            raise _RuntimeExecutionTimeoutError(
                f"chat2graph execution timed out after {timeout_seconds:.2f}s"
            ) from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _execute_once(self, workflow_path: Path, question: str) -> str:
        service = self._agentic_service_cls.load(yaml_path=str(workflow_path))
        result = service.execute(question)
        payload_getter = getattr(result, "get_payload", None)
        if callable(payload_getter):
            return str(payload_getter())
        return str(result)

    def _check_circuit_open(self) -> str | None:
        now = monotonic()
        if now < self._circuit_open_until:
            remaining = self._circuit_open_until - now
            return f"chat2graph circuit open, retry after {remaining:.2f}s"
        return None

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._circuit_open_until = 0.0

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._settings.sdk_runtime_circuit_failure_threshold:
            self._circuit_open_until = (
                monotonic() + self._settings.sdk_runtime_circuit_reset_seconds
            )

    def _build_runtime_result(
        self,
        case: SyntheticCase,
        started: float,
        output_text: str,
    ) -> CaseExecution:
        return CaseExecution(
            case_id=case.case_id,
            question=case.question,
            expected=case.verifier,
            output=output_text,
            score=0.0,
            rationale="runtime output before LLM judge",
            latency_ms=(perf_counter() - started) * 1000,
            token_cost=0.0,
        )

    def _build_runtime_error(
        self,
        case: SyntheticCase,
        started: float,
        category: str,
        detail: str,
    ) -> CaseExecution:
        return CaseExecution(
            case_id=case.case_id,
            question=case.question,
            expected=case.verifier,
            output=f"RUNTIME_ERROR[{category}]: {detail}",
            score=0.0,
            rationale="runtime output before LLM judge",
            latency_ms=(perf_counter() - started) * 1000,
            token_cost=0.0,
        )

    def _ensure_importable(self, root: Path) -> None:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

        marker = root / "app/core/sdk/agentic_service.py"
        if not marker.exists():
            raise ValueError(
                "chat2graph sdk entry not found at app/core/sdk/agentic_service.py under CHAT2GRAPH_ROOT"
            )

        spec = importlib.util.spec_from_file_location("chat2graph_marker", marker)
        if spec is None:
            raise ValueError("unable to inspect chat2graph sdk marker module")
