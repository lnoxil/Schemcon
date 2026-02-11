from __future__ import annotations

from dataclasses import dataclass
from typing import Set, Optional

from .block_gradients import find_best_block_match, get_block_category
from .categories import categorize_block


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
    best_match = find_best_block_match(source_name, target_blocks)
    
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
