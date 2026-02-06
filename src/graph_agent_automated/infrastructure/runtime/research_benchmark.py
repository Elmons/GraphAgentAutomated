from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REQUIRED_TASK_CATEGORIES = ("query", "analytics", "hybrid", "schema")
MIN_TOTAL_TASKS = 12
MIN_TASKS_PER_CATEGORY = 3


@dataclass(frozen=True)
class BenchmarkTaskSpec:
    task_id: str
    category: str
    task_desc: str
    manual_blueprint: str


@dataclass(frozen=True)
class ResearchBenchmarkSpec:
    benchmark_id: str
    version: str
    default_seeds: list[int]
    task_items: list[BenchmarkTaskSpec]


def load_research_benchmark(path: str | Path) -> ResearchBenchmarkSpec:
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists() or not file_path.is_file():
        raise ValueError(f"research benchmark file not found: {file_path}")
    if file_path.suffix.lower() != ".json":
        raise ValueError("research benchmark file must be .json")

    with open(file_path, encoding="utf-8") as f:
        payload: Any = json.load(f)

    if not isinstance(payload, dict):
        raise ValueError("research benchmark payload must be a JSON object")

    benchmark_id = str(payload.get("benchmark_id") or "").strip()
    version = str(payload.get("version") or "").strip()
    task_rows = payload.get("task_items")
    default_seed_rows = payload.get("default_seeds")
    if not benchmark_id:
        raise ValueError("research benchmark requires benchmark_id")
    if not version:
        raise ValueError("research benchmark requires version")
    if not isinstance(task_rows, list):
        raise ValueError("research benchmark requires task_items list")
    if not isinstance(default_seed_rows, list):
        raise ValueError("research benchmark requires default_seeds list")

    default_seeds: list[int] = []
    for row in default_seed_rows:
        if isinstance(row, bool) or not isinstance(row, int) or row <= 0:
            raise ValueError("default_seeds must be a list of positive integers")
        default_seeds.append(row)

    task_items: list[BenchmarkTaskSpec] = []
    for row in task_rows:
        if not isinstance(row, dict):
            raise ValueError("task_items entries must be objects")
        task_id = str(row.get("task_id") or "").strip()
        category = str(row.get("category") or "").strip().lower()
        task_desc = str(row.get("task_desc") or "").strip()
        manual_blueprint = str(row.get("manual_blueprint") or "").strip()
        task_items.append(
            BenchmarkTaskSpec(
                task_id=task_id,
                category=category,
                task_desc=task_desc,
                manual_blueprint=manual_blueprint,
            )
        )

    spec = ResearchBenchmarkSpec(
        benchmark_id=benchmark_id,
        version=version,
        default_seeds=default_seeds,
        task_items=task_items,
    )
    validate_research_benchmark(spec)
    return spec


def validate_research_benchmark(spec: ResearchBenchmarkSpec) -> None:
    if not spec.default_seeds:
        raise ValueError("research benchmark requires non-empty default_seeds")
    if len(set(spec.default_seeds)) != len(spec.default_seeds):
        raise ValueError("default_seeds must be unique")

    if len(spec.task_items) < MIN_TOTAL_TASKS:
        raise ValueError(f"research benchmark requires at least {MIN_TOTAL_TASKS} tasks")

    task_ids = [item.task_id for item in spec.task_items]
    if any(not task_id for task_id in task_ids):
        raise ValueError("every task item requires non-empty task_id")
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("task_id must be unique in research benchmark")

    for item in spec.task_items:
        if item.category not in REQUIRED_TASK_CATEGORIES:
            raise ValueError(f"unsupported task category: {item.category}")
        if not item.task_desc:
            raise ValueError(f"task_desc must not be empty for task {item.task_id}")
        if not item.manual_blueprint:
            raise ValueError(f"manual_blueprint must not be empty for task {item.task_id}")

    category_counter = Counter(item.category for item in spec.task_items)
    for category in REQUIRED_TASK_CATEGORIES:
        if category_counter.get(category, 0) < MIN_TASKS_PER_CATEGORY:
            raise ValueError(
                f"research benchmark requires at least {MIN_TASKS_PER_CATEGORY} tasks for category {category}"
            )


def resolve_manual_blueprint_path(task: BenchmarkTaskSpec, manual_blueprints_root: Path) -> Path:
    root = manual_blueprints_root.expanduser().resolve()
    raw_path = Path(task.manual_blueprint).expanduser()
    resolved = raw_path.resolve() if raw_path.is_absolute() else (root / raw_path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"manual blueprint for task {task.task_id} is outside root: {resolved}")
    if not resolved.exists() or not resolved.is_file():
        raise ValueError(f"manual blueprint for task {task.task_id} not found: {resolved}")
    if resolved.suffix.lower() not in {".yml", ".yaml", ".json"}:
        raise ValueError(
            f"manual blueprint for task {task.task_id} must be .yml/.yaml/.json: {resolved}"
        )
    return resolved
