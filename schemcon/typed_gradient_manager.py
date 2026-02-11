"""
Type-Specific Gradient Map System

Each block type has its own gradient map for color-based matching within that type.
"""

import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, asdict

from .block_evolution import BlockEvolution, get_block_evolution
from .strict_block_types import (
    BLOCK_TYPES, BLOCK_FORMS, get_block_type, get_replacement_for_block, is_safe_replacement
)

@dataclass
class TypeGradientEntry:
    """Entry in type-specific gradient map."""
    source: str
    target: str
    block_type: str
    color_distance: float
    confidence: float
    reason: str

class TypedGradientMapManager:
    """Manages type-specific gradient maps for all version pairs."""
    
    def __init__(self, data_root: str = "data/typed_gradient_maps"):
        self.data_root = Path(data_root)
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.evolution = get_block_evolution()
        self._gradient_maps: Dict[str, Dict[str, TypeGradientEntry]] = {}
    
    def get_map_path(self, source_ver: str, target_ver: str) -> Path:
        """Get path to gradient map file."""
        return self.data_root / f"{source_ver}_to_{target_ver}.json"
    
    def hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_clean = hex_color.lstrip("#")
        return (
            int(hex_clean[0:2], 16),
            int(hex_clean[2:4], 16),
            int(hex_clean[4:6], 16)
        )
    
    def color_distance(self, color1: str, color2: str) -> float:
        """Calculate Euclidean distance between two hex colors."""
        rgb1 = self.hex_to_rgb(color1)
        rgb2 = self.hex_to_rgb(color2)
        return sum((a - b) ** 2 for a, b in zip(rgb1, rgb2)) ** 0.5
    
    def build_typed_gradient_map(self, source_ver: str, target_ver: str, force_rebuild: bool = False) -> Dict[str, TypeGradientEntry]:
        """Build type-specific gradient map."""
        map_path = self.get_map_path(source_ver, target_ver)
        
        if not force_rebuild and map_path.exists():
            print(f"Loading existing typed gradient map: {map_path}")
            return self._load_gradient_map(source_ver, target_ver)
        
        print(f"Building TYPED gradient map: {source_ver} -> {target_ver}")
        
        source_blocks = self.evolution.version_blocks.get(source_ver, set())
        target_blocks = self.evolution.version_blocks.get(target_ver, set())
        
        if not source_blocks or not target_blocks:
            raise ValueError(f"Version data not available")
        
        gradient_map = {}
        blocks_to_replace = source_blocks - target_blocks
        
        print(f"  Common blocks: {len(source_blocks & target_blocks)} (preserved)")
        print(f"  Need replacement: {len(blocks_to_replace)}")
        
        # Group by type
        type_groups: Dict[str, List[str]] = {}
        for block in blocks_to_replace:
            block_type = get_block_type(block)
            if block_type is None:
                block_type = "unknown"
            if block_type not in type_groups:
                type_groups[block_type] = []
            type_groups[block_type].append(block)
        
        print(f"  Block types to process: {len(type_groups)}")
        
        # Process each type group
        for type_name, blocks in type_groups.items():
            if type_name is None:
                type_name = "unknown"
            
            print(f"  Processing {type_name}: {len(blocks)} blocks")
            
            for source_block in blocks:
                entry = self._find_typed_replacement(source_block, target_blocks, type_name)
                if entry:
                    gradient_map[source_block] = entry
        
        self._save_gradient_map(source_ver, target_ver, gradient_map)
        return gradient_map
    
    def _find_typed_replacement(self, source_block: str, target_blocks: Set[str], block_type: str) -> Optional[TypeGradientEntry]:
        """Find replacement within same type using color matching."""
        source_clean = source_block.replace("minecraft:", "").split("[")[0]
        
        # Get source block info
        if block_type in BLOCK_TYPES:
            source_info = BLOCK_TYPES[block_type]
            source_color = source_info.color
        else:
            source_color = "#808080"
        
        # Get form suffix (stairs, slab, etc.)
        form_suffix = ""
        for form in BLOCK_FORMS:
            if source_clean.endswith(f"_{form}"):
                form_suffix = f"_{form}"
                break
        
        candidates = []
        
        for target_block in target_blocks:
            target_clean = target_block.replace("minecraft:", "").split("[")[0]
            target_type = get_type_for_block_in_set(target_block, target_blocks)
            
            # STRICT: Must be same type category
            if target_type != block_type:
                continue
            
            # STRICT: Must have same form
            target_form = ""
            for form in BLOCK_FORMS:
                if target_clean.endswith(f"_{form}"):
                    target_form = f"_{form}"
                    break
            
            if form_suffix != target_form:
                continue
            
            # Get target color
            if target_type in BLOCK_TYPES:
                target_info = BLOCK_TYPES[target_type]
                target_color = target_info.color
            else:
                target_color = "#808080"
            
            # Calculate color distance
            dist = self.color_distance(source_color, target_color)
            
            # Calculate confidence
            confidence = max(0.0, 1.0 - (dist / 255.0))
            
            candidates.append((target_block, dist, confidence))
        
        if not candidates:
            # Fallback: try without form matching
            return self._find_fallback_replacement(source_block, target_blocks, block_type, form_suffix)
        
        # Sort by color distance (closest first)
        candidates.sort(key=lambda x: x[1])
        
        best = candidates[0]
        
        return TypeGradientEntry(
            source=source_block,
            target=best[0],
            block_type=block_type,
            color_distance=best[1],
            confidence=best[2],
            reason=f"type:{block_type}+color_match"
        )
    
    def _find_fallback_replacement(self, source_block: str, target_blocks: Set[str], block_type: str, form_suffix: str) -> Optional[TypeGradientEntry]:
        """Find fallback replacement without form matching."""
        if block_type in BLOCK_TYPES:
            type_info = BLOCK_TYPES[block_type]
            source_color = type_info.color
            
            # Try replacements from can_replace_with list
            for replacement_base in type_info.can_replace_with:
                replacement = f"minecraft:{replacement_base}{form_suffix}"
                if replacement in target_blocks:
                    return TypeGradientEntry(
                        source=source_block,
                        target=replacement,
                        block_type=block_type,
                        color_distance=0.0,
                        confidence=0.8,
                        reason=f"type:{block_type}+fallback"
                    )
        
        return None
    
    def _save_gradient_map(self, source_ver: str, target_ver: str, gradient_map: Dict[str, TypeGradientEntry]):
        """Save gradient map to file."""
        map_path = self.get_map_path(source_ver, target_ver)
        
        data = {
            "source_version": source_ver,
            "target_version": target_ver,
            "entries": {k: asdict(v) for k, v in gradient_map.items()}
        }
        
        with open(map_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        print(f"Typed gradient map saved: {map_path}")
    
    def _load_gradient_map(self, source_ver: str, target_ver: str) -> Dict[str, TypeGradientEntry]:
        """Load gradient map from file."""
        map_path = self.get_map_path(source_ver, target_ver)
        
        with open(map_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        gradient_map = {}
        for key, entry_data in data.get("entries", {}).items():
            gradient_map[key] = TypeGradientEntry(**entry_data)
        
        return gradient_map
    
    def get_mapping(self, source_ver: str, target_ver: str) -> Dict[str, str]:
        """Get simple mapping dict."""
        gradient_map = self.build_typed_gradient_map(source_ver, target_ver)
        return {k: v.target for k, v in gradient_map.items()}

def get_type_for_block_in_set(block_name: str, block_set: Set[str]) -> str:
    """Get block type for a block that exists in target set."""
    block_type = get_block_type(block_name)
    return block_type if block_type is not None else "unknown"

# Global instance
_typed_manager = None

def get_typed_gradient_manager() -> TypedGradientMapManager:
    """Get global TypedGradientMapManager instance."""
    global _typed_manager
    if _typed_manager is None:
        _typed_manager = TypedGradientMapManager()
    return _typed_manager
