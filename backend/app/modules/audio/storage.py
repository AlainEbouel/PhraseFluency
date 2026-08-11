"""AudioStorage abstraction (architecture.md, Storage abstraction).

Local V1 uses the filesystem. A future GCS/S3/Azure Blob implementation
can satisfy the same interface without touching callers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class AudioStorage(ABC):
    @abstractmethod
    def save(self, storage_key: str, content: bytes) -> None: ...

    @abstractmethod
    def read(self, storage_key: str) -> bytes: ...

    @abstractmethod
    def exists(self, storage_key: str) -> bool: ...


class LocalFilesystemAudioStorage(AudioStorage):
    def __init__(self, base_path: str) -> None:
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _resolve(self, storage_key: str) -> Path:
        safe_key = storage_key.replace("/", "_").replace("\\", "_").replace("..", "_")
        return self._base_path / safe_key

    def save(self, storage_key: str, content: bytes) -> None:
        self._resolve(storage_key).write_bytes(content)

    def read(self, storage_key: str) -> bytes:
        return self._resolve(storage_key).read_bytes()

    def exists(self, storage_key: str) -> bool:
        return self._resolve(storage_key).exists()
