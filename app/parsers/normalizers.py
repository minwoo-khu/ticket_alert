from __future__ import annotations

import re


_WHITESPACE_RE = re.compile(r"\s+")
_LEADING_TRAILING_RE = re.compile(r"^[^\w가-힣]+|[^\w가-힣]+$")


def normalize_category_label(label: str) -> str:
    normalized = _WHITESPACE_RE.sub("", label or "")
    normalized = _LEADING_TRAILING_RE.sub("", normalized)
    return normalized.strip()


def normalize_summary_text(text: str) -> str:
    normalized = text.replace("\r", "\n")
    normalized = normalized.replace("·", "/").replace("|", "/")
    normalized = re.sub(r"\s*,\s*", " / ", normalized)
    normalized = re.sub(r"\s*/\s*", " / ", normalized)
    normalized = re.sub(r"\n+", " / ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()

