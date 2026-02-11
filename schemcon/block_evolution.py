"""
Block Evolution System - tracks which blocks exist in which Minecraft versions.
This creates a "family tree" of blocks showing when they appeared/disappeared.
"""

import json
import os
from pathlib import Path
from typing import Dict, Set, List, Tuple

# Version history (newest to oldest)
MINECRAFT_VERSIONS = [
    "1.21", "1.20", "1.19", "1.18", "1.17", "1.16.5", "1.16", "1.15", "1.14", "1.13", "1.12"
]

class BlockEvolution:
    """Tracks block availability across Minecraft versions."""
    
    def __init__(self, versions_root: str = "data/versions"):
        self.versions_root = Path(versions_root)
        self.version_blocks: Dict[str, Set[str]] = {}
        self.block_versions: Dict[str, List[str]] = {}  # block -> list of versions where it exists
        self._load_all_versions()
    
    def _load_all_versions(self):
        """Load blocks.json for all available versions."""
        for version in MINECRAFT_VERSIONS:
            blocks_file = self.versions_root / version / "blocks.json"
            if blocks_file.exists():
                with open(blocks_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Extract just the block names
                    self.version_blocks[version] = set(data.keys())
                    print(f"Loaded {len(data)} blocks for {version}")
    
    def get_blocks_added_in_version(self, version: str) -> Set[str]:
        """Get blocks that were added in a specific version (not in previous)."""
        if version not in self.version_blocks:
            return set()
        
        # Find previous version
        idx = MINECRAFT_VERSIONS.index(version)
        if idx >= len(MINECRAFT_VERSIONS) - 1:
            return self.version_blocks[version]  # Oldest version, all blocks are "new"
        
        previous_version = MINECRAFT_VERSIONS[idx + 1]
        if previous_version not in self.version_blocks:
            return self.version_blocks[version]
        
        return self.version_blocks[version] - self.version_blocks[previous_version]
    
    def get_blocks_removed_in_version(self, version: str) -> Set[str]:
        """Get blocks that were removed in a specific version (existed before but not now)."""
        if version not in self.version_blocks:
            return set()
        
        # Find newer version
        idx = MINECRAFT_VERSIONS.index(version)
        if idx == 0:
            return set()  # Newest version, nothing removed yet
        
        newer_version = MINECRAFT_VERSIONS[idx - 1]
        if newer_version not in self.version_blocks:
            return set()
        
        return self.version_blocks[newer_version] - self.version_blocks[version]
    
    def block_exists_in_version(self, block: str, target_version: str) -> bool:
        """Check if a block exists in a specific version.
        
        Args:
            block: Block name (with or without 'minecraft:' prefix)
            target_version: Version string (e.g., '1.16.5')
        
        Returns:
            True if block exists in that version
        """
        if target_version not in self.version_blocks:
            return False
        
        # Normalize block name
        block_clean = block.replace("minecraft:", "")
        
        # Check both with and without prefix
        return block in self.version_blocks[target_version] or f"minecraft:{block_clean}" in self.version_blocks[target_version]
    
    def get_blocks_not_in_version(self, block: str, target_version: str) -> bool:
        """Check if a block exists in a specific version."""
        return self.block_exists_in_version(block, target_version)
    
    def get_replacement_candidates(self, source_version: str, target_version: str) -> Dict[str, Set[str]]:
        """
        Get all blocks that need replacement when downgrading from source to target version.
        Returns: {block_name: set_of_versions_where_it_exists}
        """
        if source_version not in self.version_blocks or target_version not in self.version_blocks:
            return {}
        
        source_blocks = self.version_blocks[source_version]
        target_blocks = self.version_blocks[target_version]
        
        # Blocks in source but not in target need replacement
        need_replacement = source_blocks - target_blocks
        
        result = {}
        for block in need_replacement:
            # Find all versions where this block exists
            versions_with_block = []
            for version in MINECRAFT_VERSIONS:
                if version in self.version_blocks and block in self.version_blocks[version]:
                    versions_with_block.append(version)
            result[block] = set(versions_with_block)
        
        return result
    
    def build_version_diff_report(self, source_ver: str, target_ver: str) -> Dict:
        """Build a detailed report of differences between two versions."""
        if source_ver not in self.version_blocks or target_ver not in self.version_blocks:
            return {"error": "Version data not available"}
        
        source_blocks = self.version_blocks[source_ver]
        target_blocks = self.version_blocks[target_ver]
        
        added = target_blocks - source_blocks  # In target but not source (newer blocks)
        removed = source_blocks - target_blocks  # In source but not target (need replacement)
        common = source_blocks & target_blocks  # Exist in both
        
        return {
            "source_version": source_ver,
            "target_version": target_ver,
            "source_total": len(source_blocks),
            "target_total": len(target_blocks),
            "blocks_added_in_target": sorted(added),
            "blocks_removed_in_target": sorted(removed),
            "blocks_common": sorted(common),
            "count_added": len(added),
            "count_removed": len(removed),
            "count_common": len(common),
        }
    
    def print_diff_summary(self, source_ver: str, target_ver: str):
        """Print a readable summary of version differences."""
        report = self.build_version_diff_report(source_ver, target_ver)
        
        print(f"\n{'='*80}")
        print(f"VERSION DIFFERENCE: {source_ver} -> {target_ver}")
        print(f"{'='*80}")
        print(f"Source ({source_ver}): {report['source_total']} blocks")
        print(f"Target ({target_ver}): {report['target_total']} blocks")
        print(f"Common blocks: {report['count_common']}")
        print(f"Need replacement: {report['count_removed']} blocks")
        print(f"\nBlocks that need replacement (exist in {source_ver} but not in {target_ver}):")
        
        # Group by category/family
        families = {}
        for block in report['blocks_removed_in_target'][:50]:  # Show first 50
            base = block.replace('minecraft:', '').split('_')[0]
            if base not in families:
                families[base] = []
            families[base].append(block.replace('minecraft:', ''))
        
        for family, blocks in sorted(families.items())[:10]:
            print(f"\n  {family.upper()}:")
            for block in blocks[:5]:
                print(f"    - {block}")
            if len(blocks) > 5:
                print(f"    ... and {len(blocks) - 5} more")

# Global instance
evolution = BlockEvolution()

def get_block_evolution() -> BlockEvolution:
    """Get the global BlockEvolution instance."""
    return evolution

if __name__ == "__main__":
    # Test
    evo = BlockEvolution()
    evo.print_diff_summary("1.21", "1.16.5")
    
    # Save detailed report
    report = evo.build_version_diff_report("1.21", "1.16.5")
    with open("block_evolution_report.json", "w", encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print("\nDetailed report saved to block_evolution_report.json")
