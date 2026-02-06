from __future__ import annotations

from pathlib import Path


def list_subdirs(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return [item for item in path.iterdir() if item.is_dir()]


def snapshot_subdir_names(path: Path) -> set[str]:
    return {item.name for item in list_subdirs(path)}


def resolve_new_run_dir(path: Path, before_names: set[str]) -> Path:
    current_subdirs = list_subdirs(path)
    if not current_subdirs:
        raise ValueError(f"no run directories found under: {path}")

    def _sort_key(item: Path) -> tuple[float, str]:
        return (item.stat().st_mtime, item.name)

    new_subdirs = [item for item in current_subdirs if item.name not in before_names]
    if new_subdirs:
        return max(new_subdirs, key=_sort_key)
    return max(current_subdirs, key=_sort_key)
