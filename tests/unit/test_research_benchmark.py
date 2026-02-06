from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from graph_agent_automated.infrastructure.runtime.research_benchmark import (
    MIN_TOTAL_TASKS,
    REQUIRED_TASK_CATEGORIES,
    load_research_benchmark,
    resolve_manual_blueprint_path,
)


def test_load_research_benchmark_v1_and_resolve_manual_blueprints() -> None:
    benchmark_path = Path("docs/benchmarks/research_benchmark_v1.json")
    manual_root = Path("docs/manual_blueprints/research_benchmark_v1")

    spec = load_research_benchmark(benchmark_path)
    assert spec.benchmark_id == "research_benchmark_v1"
    assert len(spec.task_items) >= MIN_TOTAL_TASKS

    category_counter = Counter(task.category for task in spec.task_items)
    for category in REQUIRED_TASK_CATEGORIES:
        assert category_counter[category] >= 3

    for task in spec.task_items:
        resolved = resolve_manual_blueprint_path(task, manual_root)
        assert resolved.exists()
        assert resolved.is_file()


def test_research_benchmark_rejects_missing_category_coverage(tmp_path: Path) -> None:
    bad_payload = {
        "benchmark_id": "bad-benchmark",
        "version": "1.0.0",
        "default_seeds": [1, 2, 3],
        "task_items": [
            {
                "task_id": f"q{i}",
                "category": "query",
                "task_desc": f"query task {i}",
                "manual_blueprint": "query_manual.yml",
            }
            for i in range(1, 13)
        ],
    }
    file_path = tmp_path / "bad_benchmark.json"
    file_path.write_text(json.dumps(bad_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(ValueError, match="requires at least 3 tasks for category analytics"):
        load_research_benchmark(file_path)
