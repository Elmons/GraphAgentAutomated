#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from graph_agent_automated.core.config import get_settings
from graph_agent_automated.infrastructure.persistence.artifact_manager import cleanup_artifacts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cleanup old GraphAgentAutomated artifacts.")
    parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Delete runs older than this age (days), excluding latest kept runs.",
    )
    parser.add_argument(
        "--keep-latest-per-agent",
        type=int,
        default=10,
        help="Always keep latest N runs per agent.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print cleanup report without deleting files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    report = cleanup_artifacts(
        artifacts_root=settings.artifacts_path,
        retention_days=args.retention_days,
        keep_latest_per_agent=args.keep_latest_per_agent,
        dry_run=args.dry_run,
    )
    print(json.dumps(report.__dict__, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
