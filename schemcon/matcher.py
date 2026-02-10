from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .categories import BlockTraits, categorize_block


@dataclass(frozen=True)
class MatchResult:
    source: str
    target: str
    reason: str
    confidence: float


def _color_distance(a: tuple[int, int, int] | None, b: tuple[int, int, int] | None) -> float:
    if a is None or b is None:
        return 40.0
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _token_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union


CRITICAL_RULES = {
    "liquid_water": {"liquid_water"},
    "liquid_lava": {"liquid_lava"},
    "air": {"air"},
    "grass_block": {"grass_block"},
    "grass_plant": {"grass_plant", "tall_plant"},
    "mushroom_small": {"mushroom_small"},
    "mushroom_block": {"mushroom_block"},
    "flower_small": {"flower_small", "grass_plant"},
    "flower_tall": {"flower_tall", "tall_plant"},
    "sapling": {"sapling"},
    "crop": {"crop", "grass_plant"},
    "water_plant": {"water_plant"},
    "vine": {"vine"},
    "roots": {"roots", "vine"},
    "bamboo": {"bamboo"},
    "potted_plant": {"potted_plant"},
    "command_block": {"air"},
}

RESTRICTED_SOURCE_BLOCKS = {
    "minecraft:command_block",
    "minecraft:chain_command_block",
    "minecraft:repeating_command_block",
}

NEVER_TARGET_PREFIXES = (
    "minecraft:potted_",
)

PREFERRED_REPLACEMENTS = {
    "grass_plant": "short_grass",
    "flower_small": "dandelion",
    "flower_tall": "sunflower",
    "mushroom_small": "red_mushroom",
    "sapling": "oak_sapling",
    "crop": "wheat",
}


def _is_category_compatible(source_category: str, target_category: str) -> bool:
    if source_category == target_category:
        return True
    if source_category in CRITICAL_RULES:
        return target_category in CRITICAL_RULES[source_category]
    return True


def _score(candidate: BlockTraits, source: BlockTraits) -> float:
    score = 0.0
    if not _is_category_compatible(source.category, candidate.category):
        score += 1000.0
    if source.block_type != candidate.block_type:
        score += 500.0
    if candidate.shape != source.shape:
        score += 150.0
    if candidate.family != source.family:
        score += 100.0
    if source.family != "wool" and candidate.family == "wool":
        score += 220.0
    if source.category != "potted_plant" and candidate.category == "potted_plant":
        score += 600.0
    if source.category != "command_block" and candidate.category == "command_block":
        score += 1200.0

    token_sim = _token_similarity(candidate.tokens, source.tokens)
    score += (1.0 - token_sim) * 50.0

    color_dist = _color_distance(candidate.color, source.color)
    score += color_dist * 2.0
    return score


def _is_safe_match(source: BlockTraits, candidate: BlockTraits, score: float) -> bool:
    if not _is_category_compatible(source.category, candidate.category):
        return False
    if source.block_type != candidate.block_type:
        return False

    token_sim = _token_similarity(source.tokens, candidate.tokens)
    same_shape = source.shape == candidate.shape
    same_family = source.family == candidate.family
    same_category = source.category == candidate.category

    if same_shape and same_family and same_category and score < 100:
        return True
    if same_shape and same_category and token_sim >= 0.5 and score < 150:
        return True
    if same_category and token_sim >= 0.7 and score < 120:
        return True
    return False


def _calculate_confidence(score: float, source: BlockTraits, candidate: BlockTraits) -> float:
    if score >= 500:
        return 0.0
    if source.category == candidate.category and source.shape == candidate.shape:
        if score < 50:
            return 1.0
        if score < 100:
            return 0.9
        if score < 150:
            return 0.8

    if source.category == candidate.category:
        if score < 100:
            return 0.7
        if score < 200:
            return 0.6

    if score < 250:
        return 0.5
    return 0.3


@lru_cache(maxsize=4096)
def _cached_traits(name: str) -> BlockTraits:
    return categorize_block(name)


def pick_best_match(source_name: str, target_blocks: set[str]) -> MatchResult:
    source_base = source_name.split("[", 1)[0]
    if source_base in RESTRICTED_SOURCE_BLOCKS:
        return MatchResult(source=source_name, target="minecraft:air", reason="restricted_removed", confidence=1.0)
    if source_base == "minecraft:air":
        return MatchResult(source=source_name, target="minecraft:air", reason="air_preserved", confidence=1.0)

    if source_name in target_blocks:
        return MatchResult(source=source_name, target=source_name, reason="exact", confidence=1.0)

    source_traits = _cached_traits(source_name)
    compatible_candidates: list[tuple[float, str, BlockTraits]] = []
    incompatible_candidates: list[tuple[float, str, BlockTraits]] = []

    for candidate_name in target_blocks:
        if candidate_name.startswith("#"):
            continue
        if any(candidate_name.startswith(prefix) for prefix in NEVER_TARGET_PREFIXES):
            continue
        candidate_traits = _cached_traits(candidate_name)
        score = _score(candidate_traits, source_traits)
        if _is_category_compatible(source_traits.category, candidate_traits.category):
            compatible_candidates.append((score, candidate_name, candidate_traits))
        else:
            incompatible_candidates.append((score, candidate_name, candidate_traits))

    compatible_candidates.sort(key=lambda x: x[0])

    if compatible_candidates:
        for score, candidate_name, candidate_traits in compatible_candidates[:10]:
            if _is_safe_match(source_traits, candidate_traits, score):
                return MatchResult(
                    source=source_name,
                    target=candidate_name,
                    reason=f"smart_match(score={score:.1f})",
                    confidence=_calculate_confidence(score, source_traits, candidate_traits),
                )

        score, candidate_name, candidate_traits = compatible_candidates[0]
        if score < 300:
            return MatchResult(
                source=source_name,
                target=candidate_name,
                reason=f"compatible_match(score={score:.1f})",
                confidence=_calculate_confidence(score, source_traits, candidate_traits),
            )

    preferred = PREFERRED_REPLACEMENTS.get(source_traits.category)
    if preferred:
        for candidate_name in target_blocks:
            if preferred in candidate_name:
                return MatchResult(
                    source=source_name,
                    target=candidate_name,
                    reason="preferred_fallback",
                    confidence=0.6,
                )

    return MatchResult(source=source_name, target="minecraft:air", reason="no_safe_match", confidence=0.0)
