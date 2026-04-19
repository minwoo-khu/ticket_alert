from __future__ import annotations

from dataclasses import dataclass, field
import re

from app.parsers.normalizers import normalize_category_label, normalize_summary_text


_SEGMENT_RE = re.compile(
    r"(?P<label>.+?)\s*(?P<count>\d+)\s*(?:석|매|席|seat|seats)?$",
    re.IGNORECASE,
)
_GLOBAL_RE = re.compile(
    r"(?P<label>[가-힣A-Za-z0-9][가-힣A-Za-z0-9\s()+/_-]*?)\s*(?P<count>\d+)\s*(?:석|매|席|seat|seats)?(?=\s*(?:/|,|$))",
    re.IGNORECASE,
)


@dataclass
class ParseResult:
    counts: dict[str, int]
    normalized_text: str
    matches: list[tuple[str, int]] = field(default_factory=list)
    error: str | None = None


def _split_segments(text: str) -> list[str]:
    if not text:
        return []
    return [segment.strip() for segment in text.split(" / ") if segment.strip()]


def parse_seat_summary(text: str) -> ParseResult:
    normalized_text = normalize_summary_text(text)
    if not normalized_text:
        return ParseResult(counts={}, normalized_text="", error="empty input")

    counts: dict[str, int] = {}
    matches: list[tuple[str, int]] = []

    for segment in _split_segments(normalized_text):
        match = _SEGMENT_RE.search(segment)
        if not match:
            continue
        label = normalize_category_label(match.group("label"))
        if not label:
            continue
        count = int(match.group("count"))
        counts[label] = count
        matches.append((label, count))

    if not counts:
        for match in _GLOBAL_RE.finditer(normalized_text):
            label = normalize_category_label(match.group("label"))
            if not label:
                continue
            count = int(match.group("count"))
            counts[label] = count
            matches.append((label, count))

    error = None if counts else "no categories found"
    return ParseResult(counts=counts, normalized_text=normalized_text, matches=matches, error=error)


def parse_counts(text: str) -> dict[str, int]:
    return parse_seat_summary(text).counts

