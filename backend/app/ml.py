from __future__ import annotations

from collections import Counter
from io import BytesIO

import numpy as np
from PIL import Image, ImageStat

from .domain import ExtractionResult


LABEL_KEYWORDS = {
    "insurance_certificate": ("insurance", "policy", "coverage", "insurer"),
    "tax_certificate": ("tax", "registration", "vat", "revenue"),
    "sanctions_screening": ("sanctions", "screening", "watchlist", "compliance"),
    "quality_certificate": ("quality", "iso", "certificate", "standard"),
}


def image_quality_score(content: bytes) -> float:
    try:
        image = Image.open(BytesIO(content)).convert("L")
        variance = float(ImageStat.Stat(image).var[0])
        width, height = image.size
        detail = min(1.0, variance / 900.0)
        resolution = min(1.0, (width * height) / 1_000_000)
        return round(0.35 * detail + 0.65 * resolution, 3)
    except Exception:
        return 0.3


def classify_text(text: str, quality_score: float) -> tuple[str, float, dict[str, float]]:
    normalized = text.lower()
    scores = {label: sum(normalized.count(keyword) for keyword in keywords) for label, keywords in LABEL_KEYWORDS.items()}
    label, count = max(scores.items(), key=lambda item: item[1])
    confidence = min(0.98, 0.4 + (count * 0.12) + (quality_score * 0.25))
    explanation = {keyword: round(normalized.count(keyword) / max(1, count), 3) for keyword in LABEL_KEYWORDS[label] if keyword in normalized}
    if not explanation:
        explanation = {"image_quality": quality_score}
    return label, round(confidence, 3), explanation


def extract_document(content: bytes, filename: str, hint_text: str = "") -> ExtractionResult:
    quality = image_quality_score(content)
    text = hint_text.strip() or f"Uploaded evidence file: {filename}"
    label, confidence, explanation = classify_text(text, quality)
    return ExtractionResult(text=text, quality_score=quality, classification=label, confidence=confidence, explanation=explanation)
