"""
3D Texture Color Extractor

Extracts colors from all 6 sides of block textures for accurate 3D matching.
"""

import json
import zipfile
from pathlib import Path
from typing import Dict, Tuple, List, Optional
from PIL import Image
import io

class Block3DColorExtractor:
    """Extract 3D colors from Minecraft block textures."""
    
    def __init__(self, client_jar_path: str):
        self.jar_path = Path(client_jar_path)
        self._cache: Dict[str, Dict[str, Tuple[int, int, int]]] = {}
        self._jar_zip = None
    
    def __enter__(self):
        self._jar_zip = zipfile.ZipFile(self.jar_path, 'r')
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._jar_zip:
            self._jar_zip.close()
            self._jar_zip = None
    
    def _get_texture_path(self, block_name: str) -> Optional[str]:
        """Get texture path for a block from blockstate."""
        block_clean = block_name.replace("minecraft:", "")
        
        # Try blockstate
        blockstate_path = f"assets/minecraft/blockstates/{block_clean}.json"
        if blockstate_path in self._jar_zip.namelist():
            try:
                with self._jar_zip.open(blockstate_path) as f:
                    blockstate = json.load(f)
                
                # Get first variant
                variants = blockstate.get("variants", {})
                if variants:
                    first_variant = list(variants.values())[0]
                    if isinstance(first_variant, list):
                        first_variant = first_variant[0]
                    model_path = first_variant.get("model", "")
                    if model_path:
                        return model_path.replace("minecraft:", "")
            except:
                pass
        
        return None
    
    def _get_model_textures(self, model_path: str) -> List[str]:
        """Get all texture paths from a model."""
        if not model_path:
            return []
        
        # Remove namespace if present
        model_clean = model_path.replace("minecraft:", "")
        if not model_clean.startswith("block/"):
            model_clean = f"block/{model_clean}"
        
        model_file = f"assets/minecraft/models/{model_clean}.json"
        
        if model_file not in self._jar_zip.namelist():
            return []
        
        try:
            with self._jar_zip.open(model_file) as f:
                model = json.load(f)
            
            textures = []
            texture_dict = model.get("textures", {})
            
            for key, texture_path in texture_dict.items():
                if key in ["all", "side", "end", "top", "bottom", "front", "back", "north", "south", "east", "west"]:
                    if texture_path.startswith("minecraft:"):
                        texture_path = texture_path[10:]  # Remove "minecraft:"
                    if not texture_path.startswith("block/"):
                        texture_path = f"block/{texture_path}"
                    textures.append(texture_path)
            
            # Handle parent models
            parent = model.get("parent", "")
            if parent and "cube" in parent:
                # It's a cube, get textures from parent if needed
                if not textures and parent != "block/block":
                    parent_clean = parent.replace("minecraft:", "")
                    textures.extend(self._get_model_textures(parent_clean))
            
            return list(set(textures))  # Remove duplicates
        except:
            return []
    
    def _extract_texture_color(self, texture_path: str) -> Optional[Tuple[int, int, int]]:
        """Extract average color from a texture."""
        texture_file = f"assets/minecraft/textures/{texture_path}.png"
        
        if texture_file not in self._jar_zip.namelist():
            return None
        
        try:
            with self._jar_zip.open(texture_file) as f:
                img = Image.open(io.BytesIO(f.read()))
                img = img.convert("RGBA")
                
                # Get all non-transparent pixels
                pixels = []
                for x in range(img.width):
                    for y in range(img.height):
                        r, g, b, a = img.getpixel((x, y))
                        if a > 128:  # Not too transparent
                            pixels.append((r, g, b))
                
                if not pixels:
                    return None
                
                # Average color
                avg_r = sum(p[0] for p in pixels) // len(pixels)
                avg_g = sum(p[1] for p in pixels) // len(pixels)
                avg_b = sum(p[2] for p in pixels) // len(pixels)
                
                return (avg_r, avg_g, avg_b)
        except:
            return None
    
    def get_block_3d_color(self, block_name: str) -> Optional[Dict[str, Tuple[int, int, int]]]:
        """
        Get 3D color representation of a block.
        Returns dict with texture names and their colors.
        """
        if block_name in self._cache:
            return self._cache[block_name]
        
        block_clean = block_name.replace("minecraft:", "")
        
        # Get model path from blockstate
        model_path = self._get_texture_path(block_name)
        if not model_path:
            # Try direct texture
            texture_paths = [f"block/{block_clean}"]
        else:
            # Get textures from model
            texture_paths = self._get_model_textures(model_path)
        
        if not texture_paths:
            return None
        
        colors = {}
        for texture_path in texture_paths:
            color = self._extract_texture_color(texture_path)
            if color:
                texture_name = texture_path.split("/")[-1]
                colors[texture_name] = color
        
        if colors:
            self._cache[block_name] = colors
            return colors
        
        return None
    
    def get_average_color(self, block_name: str) -> Optional[Tuple[int, int, int]]:
        """Get single average color for a block (from all sides)."""
        colors_3d = self.get_block_3d_color(block_name)
        if not colors_3d:
            return None
        
        all_colors = list(colors_3d.values())
        if not all_colors:
            return None
        
        avg_r = sum(c[0] for c in all_colors) // len(all_colors)
        avg_g = sum(c[1] for c in all_colors) // len(all_colors)
        avg_b = sum(c[2] for c in all_colors) // len(all_colors)
        
        return (avg_r, avg_g, avg_b)


def build_3d_color_map(client_jar: str, blocks: List[str], output_path: str):
    """Build 3D color map for a set of blocks."""
    print(f"Building 3D color map from {client_jar}...")
    print(f"Processing {len(blocks)} blocks...")
    
    color_map = {}
    
    with Block3DColorExtractor(client_jar) as extractor:
        for i, block in enumerate(blocks):
            if i % 100 == 0:
                print(f"  Processed {i}/{len(blocks)} blocks...")
            
            avg_color = extractor.get_average_color(block)
            if avg_color:
                color_map[block] = avg_color
    
    # Save to JSON
    with open(output_path, 'w') as f:
        json.dump(color_map, f, indent=2)
    
    print(f"3D color map saved: {output_path}")
    print(f"Total blocks with colors: {len(color_map)}")
    
    return color_map


# Example usage
if __name__ == "__main__":
    import sys
    sys.path.insert(0, 'C:/Users/ilnar/Desktop/schem')
    
    from schemcon.block_evolution import get_block_evolution
    
    evolution = get_block_evolution()
    blocks_1_21 = list(evolution.version_blocks.get("1.21", []))
    
    jar_path = "data/versions/1.21/1.21.client.jar"
    output = "data/3d_colors_1.21.json"
    
    if Path(jar_path).exists():
        build_3d_color_map(jar_path, blocks_1_21, output)
    else:
        print(f"Jar not found: {jar_path}")
