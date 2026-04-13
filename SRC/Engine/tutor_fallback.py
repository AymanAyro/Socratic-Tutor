"""Rotating fallback tutor questions when generation fails guard or repetition checks."""

from __future__ import annotations

from difflib import SequenceMatcher


def is_near_duplicate_question(new_q: str, prior: list[str], threshold: float) -> bool:
    n = new_q.lower().strip()
    if len(n) < 14:
        return False
    for p in prior:
        if not p:
            continue
        if SequenceMatcher(None, n, p.lower().strip()).ratio() >= threshold:
            return True
    return False


# Templates use {concept} for concept name.
_FALLBACK_TEMPLATES: tuple[str, ...] = (
    "What is one concrete example from the material that relates to {concept}?",
    "Which definition or property from your reading is most central to {concept}?",
    "What is one operation or step you would apply when working with {concept}?",
    "How would you connect {concept} to something you already know from the notes?",
    "What is one distinction the material draws that helps clarify {concept}?",
)


def pick_fallback_question(
    concept_name: str,
    prior_q_texts: list[str],
    threshold: float,
    *,
    rotation_seed: int = 0,
) -> str:
    """
    Return a fallback question that is not too similar to prior tutor lines.
    rotation_seed (e.g. number of prior turns) varies which template we try first.
    """
    n = len(_FALLBACK_TEMPLATES)
    start = rotation_seed % n
    order = list(range(start, n)) + list(range(0, start))
    for i in order:
        candidate = _FALLBACK_TEMPLATES[i].format(concept=concept_name)
        if not is_near_duplicate_question(candidate, prior_q_texts, threshold):
            return candidate
    # All templates collide with priors (unlikely): least bad is shortest variant with suffix.
    base = _FALLBACK_TEMPLATES[start].format(concept=concept_name)
    suffix = " Try a different angle than before."
    candidate = base + suffix
    if not is_near_duplicate_question(candidate, prior_q_texts, threshold):
        return candidate
    return base
