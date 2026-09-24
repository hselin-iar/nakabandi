"""file_store.py — FileStore port + LocalFileStore (DOC 3 S2; DOC 2 §2.2 "local filesystem
volume for generated packs, path and SHA-256 stored in the database")."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class FileStore(Protocol):
    def save(self, relative_path: str, data: bytes) -> None: ...
    def read(self, relative_path: str) -> bytes: ...


class LocalFileStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, relative_path: str, data: bytes) -> None:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, relative_path: str) -> bytes:
        return self._resolve(relative_path).read_bytes()

    def _resolve(self, relative_path: str) -> Path:
        path = (self._root / relative_path).resolve()
        if self._root.resolve() not in path.parents and path != self._root.resolve():
            raise ValueError(f"path {relative_path!r} escapes the evidence store root")
        return path
