"""
Ingestion and chunking (FR-1, FR-2).

Reads .pdf / .docx / .txt / .md from a per-matter folder and splits each
document into overlapping text chunks suitable for retrieval. Parsing is
best-effort: a single unreadable file never aborts a matter.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

SUPPORTED_EXTS = {".pdf", ".docx", ".txt", ".md"}


@dataclass
class Chunk:
    document: str  # source filename
    text: str
    index: int  # chunk index within the document


@dataclass
class IngestedDoc:
    filename: str
    text: str
    chunks: List[Chunk] = field(default_factory=list)


def _read_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _read_docx(path: str) -> str:
    from docx import Document  # python-docx

    doc = Document(path)
    parts: List[str] = [p.text for p in doc.paragraphs]
    # include table cell text, which legal docs use heavily
    for table in doc.tables:
        for row in table.rows:
            parts.append("\t".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def _read_pdf(path: str) -> str:
    text = ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(path)
        if reader.is_encrypted:
            # Many e-filed / "signed" PDFs are encrypted with an empty user
            # password; decrypt needs the `cryptography` package for AES.
            try:
                reader.decrypt("")
            except Exception:
                pass
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:
        # Encrypted-without-cryptography, password-protected, or corrupt: don't
        # abandon the file — fall through to OCR, which can often still render it.
        print(f"[ingest] pypdf could not extract {os.path.basename(path)} ({exc}); trying OCR.")
    # Scanned/image (or unreadable) PDFs have no usable text layer — try OCR (FR-1).
    return _with_ocr_fallback(text, path)


# --------------------------------------------------------------------------- #
# OCR fallback for scanned PDFs (FR-1). Optional + graceful: if Tesseract /
# poppler aren't installed, extraction simply returns empty and the fill's
# diagnostic flags the document — nothing crashes (NFR-3, NFR-5).
# --------------------------------------------------------------------------- #
OCR_MIN_CHARS = 40  # below this a PDF is treated as scanned and OCR is attempted
OCR_DPI = int(os.environ.get("VERBATIM_OCR_DPI", "200"))
_OCR_ENABLED = os.environ.get("VERBATIM_OCR", "1") != "0"
# Optional explicit binary locations, so a Windows host needn't edit PATH:
#   VERBATIM_TESSERACT_CMD = C:\Program Files\Tesseract-OCR\tesseract.exe
#   VERBATIM_POPPLER_PATH  = C:\poppler-24.08.0\Library\bin
_TESSERACT_CMD = os.environ.get("VERBATIM_TESSERACT_CMD")
_POPPLER_PATH = os.environ.get("VERBATIM_POPPLER_PATH")
# Where eng.traineddata lives, if not alongside tesseract.exe (e.g. a separate
# tessdata folder): VERBATIM_TESSDATA_DIR = D:\Program Files\tessdata
_TESSDATA_DIR = os.environ.get("VERBATIM_TESSDATA_DIR")


def _configure_tesseract(pytesseract) -> None:
    if _TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = _TESSERACT_CMD
    if _TESSDATA_DIR:
        os.environ["TESSDATA_PREFIX"] = _TESSDATA_DIR


def _tesseract_ok() -> bool:
    try:
        import pytesseract
        from pdf2image import convert_from_path  # noqa: F401

        _configure_tesseract(pytesseract)
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _poppler_ok() -> bool:
    """Verify poppler's pdftoppm is reachable — OCR rasterization needs it, and
    its absence is the most common reason OCR silently produces nothing."""
    import shutil

    exe = "pdftoppm"
    if _POPPLER_PATH:
        win = os.path.join(_POPPLER_PATH, exe + ".exe")
        nix = os.path.join(_POPPLER_PATH, exe)
        if os.path.isfile(win) or os.path.isfile(nix):
            return True
        return shutil.which(exe, path=_POPPLER_PATH) is not None
    return shutil.which(exe) is not None or shutil.which("pdfinfo") is not None


def ocr_available() -> bool:
    """True only if OCR can actually run: enabled, Tesseract, AND poppler."""
    return _OCR_ENABLED and _tesseract_ok() and _poppler_ok()


def ocr_pdf(path: str) -> str:
    """Rasterize a PDF and OCR each page. Returns '' if OCR isn't available."""
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except Exception as exc:
        print(f"[ingest] OCR libraries unavailable ({exc}); install pytesseract + pdf2image.")
        return ""
    _configure_tesseract(pytesseract)
    kwargs = {"dpi": OCR_DPI}
    if _POPPLER_PATH:
        kwargs["poppler_path"] = _POPPLER_PATH
    try:
        images = convert_from_path(path, **kwargs)
    except Exception as exc:
        print(
            f"[ingest] could not rasterize {path} for OCR ({exc}); is poppler installed / "
            f"VERBATIM_POPPLER_PATH set to its bin folder?"
        )
        return ""
    pages: List[str] = []
    for img in images:
        try:
            pages.append(pytesseract.image_to_string(img))
        except Exception as exc:
            print(f"[ingest] OCR failed on a page of {path}: {exc}")
    return "\n".join(pages).strip()


def _with_ocr_fallback(text: str, path: str) -> str:
    """Use OCR text when the native PDF text layer is empty/negligible."""
    if len(text.strip()) >= OCR_MIN_CHARS or not _OCR_ENABLED:
        return text
    ocr = ocr_pdf(path)
    return ocr if len(ocr.strip()) > len(text.strip()) else text


def read_document(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _read_pdf(path)
    if ext == ".docx":
        return _read_docx(path)
    if ext in (".txt", ".md"):
        return _read_txt(path)
    raise ValueError(f"unsupported extension: {ext}")


def chunk_text(text: str, document: str, size: int = 1100, overlap: int = 200) -> List[Chunk]:
    """Split into overlapping character windows, preferring paragraph breaks."""
    text = text.strip()
    if not text:
        return []
    chunks: List[Chunk] = []
    start = 0
    idx = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        # try to end on a paragraph or sentence boundary for cleaner passages
        if end < n:
            window = text[start:end]
            for sep in ("\n\n", "\n", ". "):
                cut = window.rfind(sep)
                if cut > size * 0.5:
                    end = start + cut + len(sep)
                    break
        chunks.append(Chunk(document=document, text=text[start:end].strip(), index=idx))
        idx += 1
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c.text]


def ingest_folder(folder: str) -> List[IngestedDoc]:
    """Ingest every supported document in a matter folder (non-recursive + 1 level)."""
    docs: List[IngestedDoc] = []
    if not os.path.isdir(folder):
        return docs
    for root, _dirs, files in os.walk(folder):
        for name in sorted(files):
            ext = os.path.splitext(name)[1].lower()
            if ext not in SUPPORTED_EXTS:
                continue
            path = os.path.join(root, name)
            try:
                text = read_document(path)
            except Exception as exc:  # best-effort; skip unreadable files
                text = ""
                print(f"[ingest] could not read {name}: {exc}")
            rel = os.path.relpath(path, folder)
            doc = IngestedDoc(filename=rel, text=text, chunks=chunk_text(text, rel))
            docs.append(doc)
    return docs


def total_chars(docs: List[IngestedDoc]) -> int:
    return sum(len(d.text) for d in docs)
