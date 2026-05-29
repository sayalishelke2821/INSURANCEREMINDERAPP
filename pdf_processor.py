"""
pdf_processor.py
Converts each PDF page to an image (PyMuPDF) then uses EasyOCR
(free, offline, no API key needed) to extract insurance renewal fields.

NOTE: On the very first run, EasyOCR downloads ~100 MB of language models.
After that it works completely offline.
"""

import re
from functools import lru_cache

import fitz          # PyMuPDF
import numpy as np


# ── OCR reader (singleton, loaded once) ─────────────────────────────────────

@lru_cache(maxsize=1)
def _get_reader():
    import easyocr
    return easyocr.Reader(["en"], gpu=False, verbose=False)


# ── PDF → numpy image ────────────────────────────────────────────────────────

def _page_to_numpy(page: fitz.Page) -> np.ndarray:
    mat = fitz.Matrix(2.5, 2.5)          # ~180 DPI — good balance of speed/accuracy
    pix = page.get_pixmap(matrix=mat, alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    return arr


# ── OCR ──────────────────────────────────────────────────────────────────────

def _ocr_page(page: fitz.Page) -> str:
    img    = _page_to_numpy(page)
    reader = _get_reader()
    results = reader.readtext(img, detail=1, paragraph=False)
    # Sort top→bottom, left→right so nearby text flows naturally
    results.sort(key=lambda r: (r[0][0][1], r[0][0][0]))
    return " ".join(r[1] for r in results)


# ── Field extraction ─────────────────────────────────────────────────────────

def _clean(s: str) -> str:
    return " ".join(s.split()).strip() if s else s


def _extract_fields(text: str) -> dict:
    """Parse insurance renewal fields from raw OCR text using regex."""

    # Policy Number  e.g. 1629043123P102099475
    m = re.search(r"\b(\d{6,12}[A-Z]\d{6,12})\b", text)
    policy_number = m.group(1) if m else None

    # Vehicle Registration  e.g. AR 06 B 5670
    m = re.search(r"\b([A-Z]{2}[\s\-]?\d{2}[\s\-]?[A-Z]{1,3}[\s\-]?\d{4})\b", text)
    vehicle_number = _clean(m.group(1)) if m else None

    # All DD/MM/YYYY dates in document
    all_dates = re.findall(r"\b(\d{2}/\d{2}/\d{4})\b", text)

    # Payment due date — look for "Pay by" first
    m = re.search(r"[Pp]ay\s*[Bb]y\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})", text)
    payment_due_date = m.group(1) if m else (all_dates[-1] if all_dates else None)
    renewal_date     = all_dates[0] if all_dates else None

    # Premium  e.g. Rs. 1,85,305.00
    m = re.search(r"(?:Rs\.?|INR|₹)\s*([0-9,]+(?:\.[0-9]{2})?)", text)
    if m:
        premium = re.sub(r"\.00$", "", m.group(1).replace(",", ""))
    else:
        premium = None

    # Mobile — 10-digit Indian number starting with 6-9
    m = re.search(r"\b([6-9]\d{9})\b", text)
    mobile_number = m.group(1) if m else None

    # Chassis Number — labelled, or standalone 17-char VIN
    m = re.search(r"[Cc]hassis\s*[Nn]o\.?\s*[:\-]?\s*([A-Z0-9]{10,20})", text)
    if not m:
        m = re.search(r"\b([A-Z0-9]{17})\b", text)
    chassis_number = m.group(1) if m else None

    # Engine Number
    m = re.search(r"[Ee]ngine\s*[Nn]o\.?\s*[:\-]?\s*([A-Z0-9]{8,20})", text)
    engine_number = m.group(1) if m else None

    # Owner Name  — starts with a salutation
    m = re.search(
        r"\b((?:MR|MRS|MS|DR|SHRI|SMT)\.?\s+[A-Z][A-Z\s]{2,50})",
        text, re.IGNORECASE,
    )
    owner_name = _clean(m.group(1)) if m else None

    # Vehicle Make / Model
    m = re.search(
        r"[Mm]ake\s*[/\-]?\s*[Mm]odel\s*[:\-]?\s*([A-Z0-9][A-Z0-9\s\/\-]{2,30})",
        text, re.IGNORECASE,
    )
    vehicle_make_model = _clean(m.group(1)) if m else None

    # Issuing Office code
    m = re.search(r"[Ii]ssuing\s*[Oo]ffice\s*[:\-]?\s*(\d{4,8})", text)
    issuing_office = m.group(1) if m else None

    return {
        "owner_name":         owner_name,
        "mobile_number":      mobile_number,
        "policy_number":      policy_number,
        "vehicle_number":     vehicle_number,
        "chassis_number":     chassis_number,
        "engine_number":      engine_number,
        "renewal_date":       renewal_date,
        "payment_due_date":   payment_due_date,
        "premium_amount":     premium,
        "vehicle_make_model": vehicle_make_model,
        "issuing_office":     issuing_office,
    }


# ── Merge pages ───────────────────────────────────────────────────────────────

def _merge(pages: list[dict]) -> dict:
    """First non-null value per field wins across all pages."""
    fields = list(pages[0].keys())
    merged = {}
    for field in fields:
        for page in pages:
            val = page.get(field)
            if val and str(val).strip().lower() not in ("null", "none", ""):
                merged[field] = val
                break
        if field not in merged:
            merged[field] = None
    return merged


# ── Public entry point ────────────────────────────────────────────────────────

def extract_insurance_data(pdf_path: str) -> dict:
    """
    Open a PDF, OCR every page, extract insurance fields.
    Returns a single merged dict.
    """
    doc   = fitz.open(pdf_path)
    pages = []

    for page in doc:
        text = _ocr_page(page)
        pages.append(_extract_fields(text))

    doc.close()

    if not pages:
        return {}
    return _merge(pages)
