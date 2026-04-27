from __future__ import annotations

from pathlib import Path

from preprocessing.models.document import RawDocument


class BaseLoader:
    SUPPORTED_EXTENSIONS: tuple[str, ...] = ()

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"File not found: {self.path}")

    def _make_doc(self, text: str, page_num: int, extra_meta: dict | None = None) -> RawDocument:
        return RawDocument(
            source_path=str(self.path.resolve()),
            file_type=self.path.suffix.lstrip(".").lower(),
            page_num=page_num,
            raw_text=text,
            metadata=extra_meta or {},
        )
