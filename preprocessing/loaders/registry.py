"""
Loader Registry
---------------
Maps file extensions to loader classes and provides a single
`get_loader(path)` factory function used by the pipeline.

To add a new file type:
    1. Write a class that extends BaseLoader.
    2. Register it here: LOADER_REGISTRY["xyz"] = MyNewLoader
"""

from __future__ import annotations

from pathlib import Path

from preprocessing.loaders.base_loader import BaseLoader
from preprocessing.loaders.pdf_loader import PDFLoader
from preprocessing.loaders.docx_loader import DOCXLoader
from preprocessing.loaders.html_loader import HTMLLoader

# Extension → Loader class mapping
LOADER_REGISTRY: dict[str, type[BaseLoader]] = {
    "pdf": PDFLoader,
    "docx": DOCXLoader,
    "doc": DOCXLoader,
    "html": HTMLLoader,
    "htm": HTMLLoader,
}


def get_loader(path: str | Path) -> BaseLoader:
    """
    Return an instantiated loader for the given file path.

    Raises
    ------
    ValueError  if the file extension is not supported.
    FileNotFoundError  if the file does not exist.
    """
    ext = Path(path).suffix.lstrip(".").lower()
    loader_cls = LOADER_REGISTRY.get(ext)
    if loader_cls is None:
        supported = ", ".join(sorted(LOADER_REGISTRY))
        raise ValueError(
            f"Unsupported file type '.{ext}'. Supported: {supported}"
        )
    return loader_cls(path)


def supported_extensions() -> list[str]:
    return sorted(LOADER_REGISTRY.keys())
