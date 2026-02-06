from __future__ import annotations

from pathlib import Path

import pytest

from graph_agent_automated.infrastructure.runtime.research_pipeline import (
    list_subdirs,
    resolve_new_run_dir,
    snapshot_subdir_names,
)


def test_list_subdirs_and_snapshot(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")

    subdirs = list_subdirs(tmp_path)
    names = {row.name for row in subdirs}
    assert names == {"a", "b"}
    assert snapshot_subdir_names(tmp_path) == {"a", "b"}


def test_resolve_new_run_dir_prefers_new_dir(tmp_path: Path) -> None:
    old_dir = tmp_path / "old"
    new_dir = tmp_path / "new"
    old_dir.mkdir()
    before = snapshot_subdir_names(tmp_path)
    new_dir.mkdir()

    resolved = resolve_new_run_dir(tmp_path, before)
    assert resolved == new_dir


def test_resolve_new_run_dir_fallback_latest_when_no_new(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    marker = second / "m.txt"
    marker.write_text("x", encoding="utf-8")

    resolved = resolve_new_run_dir(tmp_path, {"first", "second"})
    assert resolved == second


def test_resolve_new_run_dir_rejects_empty_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no run directories found"):
        resolve_new_run_dir(tmp_path, set())
