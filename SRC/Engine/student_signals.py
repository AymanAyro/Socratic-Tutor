"""Shared detection of student surrender / refusal phrasing (Stage 2 + legacy engine)."""

from __future__ import annotations

import re

_SUBSTRING_SURRENDER = (
    "i don't know",
    "dont know",
    "idk",
    "tell me",
    "just tell me",
    "not sure",
)


def is_student_surrender(text: str) -> bool:
    normalized = " ".join((text or "").lower().split())
    if any(p in normalized for p in _SUBSTRING_SURRENDER):
        return True
    if normalized in ("no", "nope", "nah"):
        return True
    if re.fullmatch(r"no[.!?,\s]*", normalized):
        return True
    return False
