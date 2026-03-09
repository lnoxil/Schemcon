"""
Gradient Map Manager - automatically builds and updates gradient maps for all versions.
"""

import json
import os
from pathlib import Path
from typing import Dict, Set, List, Tuple, Optional
from dataclasses import dataclass, asdict
from .block_evolution import BlockEvolution, MINECRAFT_VERSIONS
from .gradient_map_system import (
    BLOCK_CATEGORIES_DETAILED, get_block_category, get_replacement_candidates,
    BlockShape, BlockFamily
)

@dataclass
class GradientMapEntry:
    """Entry in gradient map."""
    source: str
    target: str
    category: str
    color_distance: float
    shape_match: bool
    confidence: float
    reason: str

class GradientMapManager:
    """Manages gradient maps for all version combinations."""
    
    def __init__(self, data_root: str = "data/gradient_maps"):
        self.data_root = Path(data_root)
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.evolution = BlockEvolution()
        self._gradient_maps: Dict[str, Dict[str, GradientMapEntry]] = {}
    
    def get_gradient_map_path(self, source_ver: str, target_ver: str) -> Path:
        """Get path to gradient map file."""
        return self.data_root / f"{source_ver}_to_{target_ver}.json"
    
    def gradient_map_exists(self, source_ver: str, target_ver: str) -> bool:
        """Check if gradient map already exists."""
        return self.get_gradient_map_path(source_ver, target_ver).exists()
    
    def build_gradient_map(self, source_ver: str, target_ver: str, force_rebuild: bool = False) -> Dict[str, GradientMapEntry]:
        """
        Build gradient map for converting from source to target version.
        
        Args:
            source_ver: Source version (e.g., '1.21')
            target_ver: Target version (e.g., '1.16.5')
            force_rebuild: If True, rebuild even if exists
        
        Returns:
            Dictionary mapping source blocks to GradientMapEntry
        """
        map_path = self.get_gradient_map_path(source_ver, target_ver)
        
        # Check if already exists
        if not force_rebuild and map_path.exists():
            print(f"Loading existing gradient map: {map_path}")
            return self._load_gradient_map(source_ver, target_ver)
        
        print(f"Building gradient map: {source_ver} -> {target_ver}")
        
        # Get blocks for both versions
        source_blocks = self.evolution.version_blocks.get(source_ver, set())
        target_blocks = self.evolution.version_blocks.get(target_ver, set())
        
        if not source_blocks or not target_blocks:
            raise ValueError(f"Version data not available for {source_ver} or {target_ver}")
        
        gradient_map = {}
        
        # Find blocks that need replacement
        blocks_to_replace = source_blocks - target_blocks
        common_blocks = source_blocks & target_blocks
        
        print(f"  Common blocks: {len(common_blocks)} (will be preserved)")
        print(f"  Need replacement: {len(blocks_to_replace)}")
        
        # Process each block that needs replacement
        for i, source_block in enumerate(sorted(blocks_to_replace)):
            if i % 100 == 0:
                print(f"  Processing... {i}/{len(blocks_to_replace)}")
            
            entry = self._find_best_match(source_block, target_blocks)
            if entry:
                gradient_map[source_block] = entry
        
        # Save to file
        self._save_gradient_map(source_ver, target_ver, gradient_map)
        
        return gradient_map
    
    def _find_best_match(self, source_block: str, target_blocks: Set[str]) -> Optional[GradientMapEntry]:
        """Find best matching block in target set."""
        source_category = get_block_category(source_block)
        source_color = self._get_color_hex(source_block)
        
        candidates = []
        
        for target_block in target_blocks:
            target_category = get_block_category(target_block)
            target_color = self._get_color_hex(target_block)
            
            # Calculate scores
            category_match = self._category_similarity(source_category, target_category)
            color_distance = self._color_distance(source_color, target_color)
            shape_match = self._shape_match(source_block, target_block)
            
            # Strict rules
            if not self._is_valid_replacement(source_block, target_block, source_category, target_category):
                continue
            
            # Calculate confidence
            confidence = self._calculate_confidence(category_match, color_distance, shape_match)
            
            if confidence > 0.3:  # Minimum threshold
                candidates.append((
                    target_block, category_match, color_distance, shape_match, confidence
                ))
        
        if not candidates:
            return None
        
        # Sort by confidence (highest first)
        candidates.sort(key=lambda x: x[4], reverse=True)
        
        best = candidates[0]
        
        return GradientMapEntry(
            source=source_block,
            target=best[0],
            category=source_category,
            color_distance=best[2],
            shape_match=best[3],
            confidence=best[4],
            reason=f"category:{source_category}->category_match"
        )
    
    def _category_similarity(self, cat1: str, cat2: str) -> float:
        """Calculate similarity between categories."""
        if cat1 == cat2:
            return 1.0
        
        # Related categories
        related = {
            ("oak_wood", "birch_wood", "spruce_wood", "jungle_wood", "acacia_wood", "dark_oak_wood", "crimson_wood", "warped_wood", "mangrove_wood", "cherry_wood", "bamboo_wood"): 0.8,
            ("stone", "cobblestone", "stone_bricks", "granite", "diorite", "andesite", "deepslate", "blackstone"): 0.7,
            ("oak_leaves", "spruce_leaves", "birch_leaves", "jungle_leaves", "acacia_leaves", "dark_oak_leaves", "azalea_leaves", "mangrove_leaves", "cherry_leaves"): 0.9,
            ("dirt", "grass", "podzol", "mycelium", "mud"): 0.6,
        }
        
        for group, similarity in related.items():
            if cat1 in group and cat2 in group:
                return similarity
        
        return 0.0
    
    def _shape_match(self, block1: str, block2: str) -> bool:
        """Check if blocks have similar shapes."""
        b1 = block1.replace("minecraft:", "").split("[")[0]
        b2 = block2.replace("minecraft:", "").split("[")[0]
        
        shapes = {
            "stairs": ["_stairs"],
            "slab": ["_slab"],
            "door": ["_door"],
            "trapdoor": ["_trapdoor"],
            "fence": ["_fence"],
            "fence_gate": ["_fence_gate"],
            "wall": ["_wall"],
            "button": ["_button"],
            "pressure_plate": ["_pressure_plate"],
            "sign": ["_sign", "_hanging_sign"],
        }
        
        for shape, suffixes in shapes.items():
            has_shape_1 = any(b1.endswith(s) for s in suffixes)
            has_shape_2 = any(b2.endswith(s) for s in suffixes)
            
            if has_shape_1 and has_shape_2:
                return True
            elif has_shape_1 != has_shape_2:
                return False
        
        return True
    
    def _is_valid_replacement(self, source: str, target: str, source_cat: str, target_cat: str) -> bool:
        """Check if replacement follows strict rules."""
        # Extract base names
        s_base = source.replace("minecraft:", "").split("[")[0]
        t_base = target.replace("minecraft:", "").split("[")[0]
        
        # Leaves can only become leaves
        if "leaves" in s_base and "leaves" not in t_base:
            return False
        
        # Grass block can only become dirt-like
        if "grass_block" in s_base and not any(x in t_base for x in ["dirt", "podzol", "mycelium", "grass"]):
            return False
        
        # Water/lava should become air if not available
        if s_base in ["water", "lava"] and t_base not in ["water", "lava", "air", "cave_air", "void_air"]:
            return False
        
        # Command blocks become air
        if "command_block" in s_base and t_base != "air":
            return False
        
        return True
    
    def _calculate_confidence(self, category_match: float, color_distance: float, shape_match: bool) -> float:
        """Calculate overall confidence score."""
        score = category_match * 0.5  # Category is most important
        score += max(0, 1.0 - color_distance / 255.0) * 0.3  # Color similarity
        score += (1.0 if shape_match else 0.0) * 0.2  # Shape match bonus
        return min(1.0, max(0.0, score))
    
    def _get_color_hex(self, block: str) -> Tuple[int, int, int]:
        """Get RGB color for block."""
        category = get_block_category(block)
        color_hex = BLOCK_CATEGORIES_DETAILED.get(category, {}).get("color", "#808080")
        
        # Convert hex to RGB
        hex_clean = color_hex.lstrip("#")
        return (
            int(hex_clean[0:2], 16),
            int(hex_clean[2:4], 16),
            int(hex_clean[4:6], 16)
        )
    
    def _color_distance(self, color1: Tuple[int, int, int], color2: Tuple[int, int, int]) -> float:
        """Calculate Euclidean distance between colors."""
        return sum((a - b) ** 2 for a, b in zip(color1, color2)) ** 0.5
    
    def _save_gradient_map(self, source_ver: str, target_ver: str, gradient_map: Dict[str, GradientMapEntry]):
        """Save gradient map to file."""
        map_path = self.get_gradient_map_path(source_ver, target_ver)
        
        # Convert to serializable format
        data = {
            "source_version": source_ver,
            "target_version": target_ver,
            "entries": {
                k: asdict(v) for k, v in gradient_map.items()
            }
        }
        
        with open(map_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        print(f"Gradient map saved: {map_path}")
    
    def _load_gradient_map(self, source_ver: str, target_ver: str) -> Dict[str, GradientMapEntry]:
        """Load gradient map from file."""
        map_path = self.get_gradient_map_path(source_ver, target_ver)
        
        with open(map_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        gradient_map = {}
        for key, entry_data in data.get("entries", {}).items():
            gradient_map[key] = GradientMapEntry(**entry_data)
        
        return gradient_map
    
    def update_all_gradient_maps(self, force_rebuild: bool = False):
        """Build gradient maps for all version pairs."""
        versions = list(self.evolution.version_blocks.keys())
        
        for i, source_ver in enumerate(versions):
            for target_ver in versions[i+1:]:  # Only older versions
                try:
                    self.build_gradient_map(source_ver, target_ver, force_rebuild)
                except Exception as e:
                    print(f"Error building map {source_ver}->{target_ver}: {e}")
    
    def get_mapping(self, source_ver: str, target_ver: str) -> Dict[str, str]:
        """Get simple mapping dict for conversion."""
        gradient_map = self.build_gradient_map(source_ver, target_ver)
        return {k: v.target for k, v in gradient_map.items()}

# Global instance
_gradient_manager = None

def get_gradient_manager() -> GradientMapManager:
    """Get global GradientMapManager instance."""
    global _gradient_manager
    if _gradient_manager is None:
        _gradient_manager = GradientMapManager()
    return _gradient_manager
