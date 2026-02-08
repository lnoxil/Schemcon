from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .categories import BlockTraits, categorize_block


@dataclass(frozen=True)
class MatchResult:
    source: str
    target: str
    reason: str


def _color_distance(a: tuple[int, int, int] | None, b: tuple[int, int, int] | None) -> float:
    if a is None or b is None:
        return 1e6
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _token_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union


def _score(candidate: BlockTraits, source: BlockTraits) -> float:
    score = 0.0
    if candidate.shape != source.shape:
        score += 120.0
    if candidate.family != source.family:
        score += 60.0
    score += (1.0 - _token_similarity(candidate.tokens, source.tokens)) * 25.0
    score += _color_distance(candidate.color, source.color)
    return score


@lru_cache(maxsize=4096)
def _cached_traits(name: str) -> BlockTraits:
    return categorize_block(name)


def pick_best_match(source_name: str, target_blocks: set[str]) -> MatchResult:
    if source_name in target_blocks:
        return MatchResult(source=source_name, target=source_name, reason="exact")

    source_traits = _cached_traits(source_name)
    best = None
    for candidate_name in target_blocks:
        candidate_traits = _cached_traits(candidate_name)
        score = _score(candidate_traits, source_traits)
        if best is None or score < best[0]:
            best = (score, candidate_name)

    if best is None:
        return MatchResult(source=source_name, target=source_name, reason="fallback")

    return MatchResult(source=source_name, target=best[1], reason="nearest")
