from __future__ import annotations

from dataclasses import dataclass
from typing import Set, Optional

from .block_gradients import find_best_block_match, get_block_category
from .categories import categorize_block
from .strict_rules import is_safe_replacement_strict, get_block_strict_category


def _normalize_block_name(name: str) -> str:
    base = name.split("[", 1)[0]
    if ":" in base:
        return base
    return f"minecraft:{base}"


def _as_key(name: str) -> str:
    return _normalize_block_name(name).replace("minecraft:", "")


def _color_distance(left: tuple[int, int, int], right: tuple[int, int, int]) -> float:
    return sum((a - b) ** 2 for a, b in zip(left, right)) ** 0.5


def _pick_shape_safe_match(
    source_name: str,
    target_blocks: Set[str],
    gradient_map: dict[str, tuple[int, int, int]] | None = None,
) -> Optional[str]:
    """Strict fallback: keep shape/type/family first, then color.

    This prevents broken conversions like grass->water or stairs->full blocks.
    """
    source_traits = categorize_block(source_name)
    source_key = _as_key(source_name)
    src_color = None
    if gradient_map:
        src_color = gradient_map.get(source_key) or gradient_map.get(f"minecraft:{source_key}")

    best: tuple[float, str] | None = None

    for candidate in sorted(target_blocks):
        candidate_base = candidate.split("[", 1)[0]
        candidate_key = _as_key(candidate_base)
        candidate_traits = categorize_block(candidate_base)

        # ULTRA STRICT SAFETY CHECKS
        # 1. Leaves can ONLY become leaves!
        source_strict_cat = get_block_strict_category(source_name)
        target_strict_cat = get_block_strict_category(candidate_base)
        
        if source_strict_cat == "leaves" and target_strict_cat != "leaves":
            continue  # FORBIDDEN: leaves -> non-leaves
        
        # 2. Water can ONLY become water!
        if source_strict_cat == "water" and target_strict_cat != "water":
            continue  # FORBIDDEN: water -> non-water
        
        # 3. Use strict safety rules
        if not is_safe_replacement_strict(source_name, candidate_base):
            continue

        # Hard safety: do not map non-liquid blocks to liquids and vice versa.
        if source_traits.block_type == "liquid" and candidate_traits.block_type != "liquid":
            continue
        if source_traits.block_type != "liquid" and candidate_traits.block_type == "liquid":
            continue

        # Shape is the most important rule for schematic geometry.
        if source_traits.shape != candidate_traits.shape:
            continue

        score = 0.0

        # Preserve broad material behavior.
        if source_traits.block_type == candidate_traits.block_type:
            score += 5.0
        else:
            score -= 4.0

        # Preserve families (wood, stone, leaves, etc.) where possible.
        if source_traits.family == candidate_traits.family:
            score += 3.0

        # Preserve category if available.
        if source_traits.category == candidate_traits.category:
            score += 4.0

        # Try to keep color tone when texture gradients are available.
        cand_color = None
        if gradient_map:
            cand_color = gradient_map.get(candidate_key) or gradient_map.get(f"minecraft:{candidate_key}")
        if src_color and cand_color:
            score += max(0.0, 3.0 - (_color_distance(src_color, cand_color) / 90.0))

        # Token overlap helps with wood variants (oak/cherry/etc.) and similar naming.
        overlap = len(source_traits.tokens & candidate_traits.tokens)
        score += overlap * 0.6

        if best is None or score > best[0]:
            best = (score, candidate_base)

    return best[1] if best else None


def _is_risky_category(name: str) -> bool:
    traits = categorize_block(name)
    if traits.block_type == "liquid":
        return True
    return traits.family in {
        "flower",
        "sapling",
        "leaves",
        "grass",
        "mushroom",
    } or traits.category in {
        "grass_block",
        "grass_plant",
        "tall_plant",
        "flower_small",
        "flower_tall",
        "water_plant",
        "mushroom_small",
        "mushroom_block",
    }


def _pick_relaxed_safe_match(source_name: str, target_blocks: Set[str]) -> Optional[str]:
    """Fallback matcher that still enforces no liquid/non-liquid cross mapping."""
    source_traits = categorize_block(source_name)
    for candidate in sorted(target_blocks):
        candidate_base = candidate.split("[", 1)[0]
        candidate_traits = categorize_block(candidate_base)

        if source_traits.block_type == "liquid" and candidate_traits.block_type != "liquid":
            continue
        if source_traits.block_type != "liquid" and candidate_traits.block_type == "liquid":
            continue
        if source_traits.shape == candidate_traits.shape:
            return candidate_base
    return None


@dataclass(frozen=True)
class MatchResult:
    source: str
    target: str
    reason: str
    confidence: float


def pick_best_match(
    source_name: str,
    target_blocks: Set[str],
    gradient_map: dict[str, tuple[int, int, int]] | None = None,
) -> MatchResult:
    """
    Find the best matching block using the gradient-based system.
    
    IMPORTANT: If a block exists in target version, keep it EXACTLY as-is!
    Only replace blocks that don't exist in the target version.
    """
    # Extract base block name (remove properties)
    source_base = source_name.split("[", 1)[0]
    
    # Handle special cases
    if source_base == "minecraft:air":
        return MatchResult(source=source_name, target="minecraft:air", reason="air_preserved", confidence=1.0)
    
    # Check for restricted/command blocks - convert to air
    if "command_block" in source_base:
        return MatchResult(source=source_name, target="minecraft:air", reason="restricted_removed", confidence=1.0)
    
    # CRITICAL: Check if base block exists in target version
    # If yes, keep it with ALL properties intact - don't touch it!
    # NOTE: target_blocks may or may not have 'minecraft:' prefix, so check both
    source_base_clean = source_base.replace("minecraft:", "")
    if source_base in target_blocks or source_base_clean in target_blocks:
        # Block exists in target version - preserve it exactly with all properties
        return MatchResult(source=source_name, target=source_name, reason="exists_in_target", confidence=1.0)
    
    # Block doesn't exist in target - need to find replacement
    best_match = _pick_shape_safe_match(source_name, target_blocks, gradient_map=gradient_map)
    if not best_match:
        best_match = _pick_relaxed_safe_match(source_name, target_blocks)
    if not best_match and not _is_risky_category(source_name):
        # Extra fallback only for non-risky blocks.
        candidate = find_best_block_match(source_name, target_blocks)
        if candidate:
            src_type = categorize_block(source_name).block_type
            cand_type = categorize_block(candidate).block_type
            if src_type == cand_type:
                best_match = candidate
    
    if best_match:
        # Calculate confidence based on category match
        source_cat = get_block_category(source_name)
        target_cat = get_block_category(best_match)
        
        if source_cat and target_cat and source_cat == target_cat:
            confidence = 0.9
            reason = f"category_match({source_cat})"
        elif source_cat and target_cat:
            confidence = 0.7
            reason = f"fallback_match({source_cat}->{target_cat})"
        else:
            confidence = 0.6
            reason = "color_match"
        
        return MatchResult(
            source=source_name,
            target=best_match,
            reason=reason,
            confidence=confidence,
        )
    
    # No match found - return air
    return MatchResult(source=source_name, target="minecraft:air", reason="no_match", confidence=0.0)
