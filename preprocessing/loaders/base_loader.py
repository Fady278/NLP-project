from __future__ import annotations

import hashlib
from pathlib import Path

from preprocessing.models.document import RawDocument


class BaseLoader:
    SUPPORTED_EXTENSIONS: tuple[str, ...] = ()

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"File not found: {self.path}")
        self._file_hash = None

    @property
    def file_hash(self) -> str:
        if self._file_hash is None:
            file_bytes = self.path.read_bytes()
            self._file_hash = hashlib.sha256(file_bytes).hexdigest()
        return self._file_hash

    def _make_doc(self, text: str, page_num: int, extra_meta: dict | None = None) -> RawDocument:
        return RawDocument(
            source_path=str(self.path.resolve()),
            file_type=self.path.suffix.lstrip(".").lower(),
            page_num=page_num,
            raw_text=text,
            metadata=extra_meta or {},
            file_hash=self.file_hash,
        )
