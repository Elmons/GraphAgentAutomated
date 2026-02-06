from __future__ import annotations

import os
import time
from pathlib import Path

from graph_agent_automated.infrastructure.persistence.artifact_manager import cleanup_artifacts


def _make_run_dir(base: Path, agent: str, run_id: str, age_days: int, payload_size: int = 16) -> Path:
    run_dir = base / "agents" / agent / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    payload_file = run_dir / "workflow.yml"
    payload_file.write_text("x" * payload_size, encoding="utf-8")

    timestamp = time.time() - age_days * 24 * 3600
    os.utime(payload_file, (timestamp, timestamp))
    os.utime(run_dir, (timestamp, timestamp))
    return run_dir


def test_cleanup_artifacts_dry_run_reports_without_deleting(tmp_path: Path) -> None:
    run1 = _make_run_dir(tmp_path, "agent-a", "run-1", age_days=20, payload_size=64)
    run2 = _make_run_dir(tmp_path, "agent-a", "run-2", age_days=10, payload_size=64)
    run3 = _make_run_dir(tmp_path, "agent-a", "run-3", age_days=1, payload_size=64)

    report = cleanup_artifacts(
        artifacts_root=tmp_path,
        retention_days=7,
        keep_latest_per_agent=1,
        dry_run=True,
    )

    assert report.scanned_agents == 1
    assert report.scanned_runs == 3
    assert report.deleted_runs == 2
    assert report.reclaimed_bytes >= 128
    assert str(run1) in report.deleted_paths
    assert str(run2) in report.deleted_paths
    assert run1.exists()
    assert run2.exists()
    assert run3.exists()


def test_cleanup_artifacts_deletes_old_runs_and_keeps_latest(tmp_path: Path) -> None:
    run1 = _make_run_dir(tmp_path, "agent-a", "run-1", age_days=30, payload_size=32)
    run2 = _make_run_dir(tmp_path, "agent-a", "run-2", age_days=20, payload_size=32)
    run3 = _make_run_dir(tmp_path, "agent-a", "run-3", age_days=5, payload_size=32)

    report = cleanup_artifacts(
        artifacts_root=tmp_path,
        retention_days=7,
        keep_latest_per_agent=1,
        dry_run=False,
    )

    assert report.deleted_runs == 2
    assert not run1.exists()
    assert not run2.exists()
    assert run3.exists()
