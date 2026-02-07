from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from graph_agent_automated.core.config import Settings


@dataclass(frozen=True)
class StoredArtifact:
    uri: str
    checksum: str
    size_bytes: int
    local_path: str | None = None


class ArtifactStore(ABC):
    scheme: str

    def build_uri(self, path: str) -> str:
        normalized = normalize_artifact_path(path)
        return f"{self.scheme}://{normalized}"

    @abstractmethod
    def put(self, path: str, payload: bytes) -> StoredArtifact:
        """Write payload and return metadata with canonical URI."""

    @abstractmethod
    def get(self, uri: str) -> bytes:
        """Read payload by URI."""

    @abstractmethod
    def exists(self, uri: str) -> bool:
        """Return whether URI exists."""

    @abstractmethod
    def list(self, prefix: str) -> list[str]:
        """List artifact URIs under prefix (URI or relative path)."""

    @abstractmethod
    def delete(self, uri: str) -> None:
        """Delete URI if it exists."""


class LocalArtifactStore(ArtifactStore):
    scheme = "local"

    def __init__(self, root: Path):
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def put(self, path: str, payload: bytes) -> StoredArtifact:
        normalized_path = normalize_artifact_path(path)
        destination = self._root / normalized_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        return StoredArtifact(
            uri=self.build_uri(normalized_path),
            checksum=compute_sha256(payload),
            size_bytes=len(payload),
            local_path=str(destination),
        )

    def get(self, uri: str) -> bytes:
        file_path = self._uri_to_path(uri)
        return file_path.read_bytes()

    def exists(self, uri: str) -> bool:
        return self._uri_to_path(uri).is_file()

    def list(self, prefix: str) -> list[str]:
        normalized_prefix = self._normalize_prefix(prefix)
        base = self._root / normalized_prefix
        if base.is_file():
            return [self.build_uri(normalized_prefix)]
        if not base.exists():
            return []

        uris: list[str] = []
        for path in sorted(base.rglob("*")):
            if path.is_file():
                relative = path.relative_to(self._root).as_posix()
                uris.append(self.build_uri(relative))
        return uris

    def delete(self, uri: str) -> None:
        file_path = self._uri_to_path(uri)
        if file_path.exists():
            file_path.unlink()

    def uri_to_path(self, uri: str) -> Path:
        return self._uri_to_path(uri)

    def _uri_to_path(self, uri: str) -> Path:
        normalized_path = self._normalize_prefix(uri)
        return self._root / normalized_path

    def _normalize_prefix(self, prefix: str) -> str:
        if "://" in prefix:
            scheme, normalized_path = parse_artifact_uri(prefix)
            if scheme != self.scheme:
                raise ValueError(f"unsupported artifact scheme for local store: {scheme}")
            return normalized_path
        return normalize_artifact_path(prefix)


class InMemoryArtifactStore(ArtifactStore):
    scheme = "memory"

    def __init__(self):
        self._objects: dict[str, bytes] = {}

    def put(self, path: str, payload: bytes) -> StoredArtifact:
        normalized_path = normalize_artifact_path(path)
        self._objects[normalized_path] = bytes(payload)
        return StoredArtifact(
            uri=self.build_uri(normalized_path),
            checksum=compute_sha256(payload),
            size_bytes=len(payload),
            local_path=None,
        )

    def get(self, uri: str) -> bytes:
        normalized_path = self._normalize_uri(uri)
        try:
            return self._objects[normalized_path]
        except KeyError as exc:
            raise FileNotFoundError(uri) from exc

    def exists(self, uri: str) -> bool:
        normalized_path = self._normalize_uri(uri)
        return normalized_path in self._objects

    def list(self, prefix: str) -> list[str]:
        normalized_prefix = self._normalize_prefix(prefix)
        prefix_with_sep = f"{normalized_prefix}/"
        return [
            self.build_uri(path)
            for path in sorted(self._objects)
            if path == normalized_prefix or path.startswith(prefix_with_sep)
        ]

    def delete(self, uri: str) -> None:
        normalized_path = self._normalize_uri(uri)
        self._objects.pop(normalized_path, None)

    def _normalize_uri(self, uri: str) -> str:
        scheme, normalized_path = parse_artifact_uri(uri)
        if scheme != self.scheme:
            raise ValueError(f"unsupported artifact scheme for memory store: {scheme}")
        return normalized_path

    def _normalize_prefix(self, prefix: str) -> str:
        if "://" in prefix:
            return self._normalize_uri(prefix)
        return normalize_artifact_path(prefix)


def build_artifact_store(settings: Settings) -> ArtifactStore:
    backend = settings.artifact_store_backend.strip().lower()
    if backend == "local":
        return LocalArtifactStore(settings.artifacts_path)
    if backend in {"memory", "mock"}:
        return InMemoryArtifactStore()
    raise ValueError(f"unsupported artifact store backend: {settings.artifact_store_backend}")


def compute_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def normalize_artifact_path(path: str) -> str:
    raw = path.strip().replace("\\", "/")
    if not raw:
        raise ValueError("artifact path must not be empty")

    candidate = PurePosixPath(raw)
    if candidate.is_absolute():
        raise ValueError("artifact path must be relative")

    normalized = candidate.as_posix()
    if normalized in {".", ""}:
        raise ValueError("artifact path must not be current directory")

    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("artifact path contains illegal traversal segment")
    return normalized


def parse_artifact_uri(uri: str) -> tuple[str, str]:
    scheme, separator, payload = uri.partition("://")
    if not separator or not scheme:
        raise ValueError(f"invalid artifact URI: {uri}")
    normalized_path = normalize_artifact_path(payload)
    return scheme, normalized_path
