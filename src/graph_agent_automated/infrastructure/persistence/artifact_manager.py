from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass
class ArtifactCleanupReport:
    scanned_agents: int
    scanned_runs: int
    deleted_runs: int
    reclaimed_bytes: int
    deleted_paths: list[str] = field(default_factory=list)


def cleanup_artifacts(
    artifacts_root: Path,
    retention_days: int,
    keep_latest_per_agent: int,
    dry_run: bool = True,
) -> ArtifactCleanupReport:
    if retention_days < 0:
        raise ValueError("retention_days must be >= 0")
    if keep_latest_per_agent < 0:
        raise ValueError("keep_latest_per_agent must be >= 0")

    agents_root = artifacts_root / "agents"
    if not agents_root.exists():
        return ArtifactCleanupReport(
            scanned_agents=0,
            scanned_runs=0,
            deleted_runs=0,
            reclaimed_bytes=0,
            deleted_paths=[],
        )

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    scanned_agents = 0
    scanned_runs = 0
    deleted_runs = 0
    reclaimed_bytes = 0
    deleted_paths: list[str] = []

    for agent_dir in sorted(agents_root.iterdir()):
        if not agent_dir.is_dir():
            continue
        scanned_agents += 1
        run_dirs = [path for path in agent_dir.iterdir() if path.is_dir()]
        scanned_runs += len(run_dirs)

        run_dirs.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        protected = set(run_dirs[:keep_latest_per_agent])

        for run_dir in run_dirs:
            if run_dir in protected:
                continue
            modified_at = datetime.fromtimestamp(run_dir.stat().st_mtime, tz=timezone.utc)
            if modified_at >= cutoff:
                continue

            run_size = _compute_directory_size(run_dir)
            deleted_runs += 1
            reclaimed_bytes += run_size
            deleted_paths.append(str(run_dir))
            if not dry_run:
                shutil.rmtree(run_dir, ignore_errors=False)

    return ArtifactCleanupReport(
        scanned_agents=scanned_agents,
        scanned_runs=scanned_runs,
        deleted_runs=deleted_runs,
        reclaimed_bytes=reclaimed_bytes,
        deleted_paths=deleted_paths,
    )


def _compute_directory_size(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        if path.is_file():
            total += path.stat().st_size
    return total
