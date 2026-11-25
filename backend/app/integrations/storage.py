"""Object storage. Phase 1 ships the local-disk driver; an S3 driver implements the same protocol."""

import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, Protocol

from app.core.config import get_settings


class Storage(Protocol):
    def put(self, key: str, source: BinaryIO) -> None: ...
    def open(self, key: str) -> BinaryIO: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("storage key escapes the storage root")
        return path

    def put(self, key: str, source: BinaryIO) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        with tmp.open("wb") as out:
            shutil.copyfileobj(source, out, length=1024 * 1024)
        tmp.replace(path)

    def open(self, key: str) -> BinaryIO:
        return self._path(key).open("rb")

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


def iter_file(handle: BinaryIO, chunk: int = 64 * 1024) -> Iterator[bytes]:
    with handle:
        while data := handle.read(chunk):
            yield data


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = LocalStorage(get_settings().storage_local_dir)
    return _storage


def set_storage(storage: Storage | None) -> None:
    """Swap the storage backend (used by tests)."""
    global _storage
    _storage = storage
