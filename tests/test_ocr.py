"""
Tests for the scanned-PDF OCR fallback (FR-1). OCR itself needs Tesseract +
poppler, so here we pin the *decision* logic (when OCR is invoked and whether
its output is preferred) with ocr_pdf monkeypatched — no binaries required.
"""
from __future__ import annotations

import sys
import types

from app import ingest


def test_ocr_used_when_text_layer_is_empty(monkeypatch):
    monkeypatch.setattr(ingest, "_OCR_ENABLED", True)
    monkeypatch.setattr(ingest, "ocr_pdf", lambda p: "RECOVERED VIA OCR: the signed verification...")
    out = ingest._with_ocr_fallback("   ", "scan.pdf")
    assert out.startswith("RECOVERED VIA OCR")


def test_native_text_is_kept_when_present(monkeypatch):
    monkeypatch.setattr(ingest, "_OCR_ENABLED", True)
    monkeypatch.setattr(ingest, "ocr_pdf", lambda p: "should not be used")
    native = "This PDF has a real text layer with plenty of readable content."
    assert ingest._with_ocr_fallback(native, "doc.pdf") == native


def test_ocr_disabled_skips_fallback(monkeypatch):
    monkeypatch.setattr(ingest, "_OCR_ENABLED", False)
    monkeypatch.setattr(ingest, "ocr_pdf", lambda p: "should not run")
    assert ingest._with_ocr_fallback("", "scan.pdf") == ""


def test_ocr_pdf_degrades_gracefully_without_libs(monkeypatch):
    # Simulate pytesseract/pdf2image not being importable.
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name in ("pytesseract", "pdf2image"):
            raise ImportError("not installed")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert ingest.ocr_pdf("anything.pdf") == ""
    assert ingest.ocr_available() is False


def test_explicit_binary_paths_are_forwarded(monkeypatch):
    # On Windows, users point at the binaries instead of editing PATH.
    captured = {}
    fake_pdf2image = types.ModuleType("pdf2image")
    fake_pdf2image.convert_from_path = lambda path, **kw: (captured.update(kw) or ["page-image"])
    fake_pyt = types.ModuleType("pytesseract")
    fake_pyt.pytesseract = types.SimpleNamespace(tesseract_cmd=None)
    fake_pyt.image_to_string = lambda img: "OCR PAGE TEXT"

    monkeypatch.setitem(sys.modules, "pdf2image", fake_pdf2image)
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pyt)
    monkeypatch.setattr(ingest, "_POPPLER_PATH", r"C:\poppler\Library\bin")
    monkeypatch.setattr(ingest, "_TESSERACT_CMD", r"C:\Tesseract-OCR\tesseract.exe")

    out = ingest.ocr_pdf("scan.pdf")
    assert out == "OCR PAGE TEXT"
    assert captured.get("poppler_path") == r"C:\poppler\Library\bin"
    assert fake_pyt.pytesseract.tesseract_cmd == r"C:\Tesseract-OCR\tesseract.exe"
