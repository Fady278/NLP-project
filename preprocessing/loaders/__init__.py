from .docx_loader import DOCXLoader
from .html_loader import HTMLLoader
from .pdf_loader import PDFLoader
from .registry import get_loader, supported_extensions

__all__ = ["PDFLoader", "DOCXLoader", "HTMLLoader", "get_loader", "supported_extensions"]
