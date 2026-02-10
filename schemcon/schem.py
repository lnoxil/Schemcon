from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import nbtlib


CompoundLike = nbtlib.Compound


def _split_blockstate(value: str) -> tuple[str, str | None]:
    if "[" in value and value.endswith("]"):
        name, rest = value.split("[", 1)
        return name, rest[:-1]
    return value, None


def _state_from_litematic_entry(entry: CompoundLike) -> str:
    name = str(entry.get("Name", "minecraft:air"))
    props = entry.get("Properties")
    if props:
        parts = [f"{key}={str(val)}" for key, val in sorted(props.items())]
        return f"{name}[{','.join(parts)}]"
    return name


def _iter_compounds(node: object) -> Iterable[CompoundLike]:
    if isinstance(node, nbtlib.Compound):
        yield node
        for value in node.values():
            yield from _iter_compounds(value)
    elif isinstance(node, (nbtlib.List, list, tuple)):
        for value in node:
            yield from _iter_compounds(value)


def _find_named_compound(root: CompoundLike, key_name: str) -> tuple[CompoundLike, str, CompoundLike] | None:
    needle = key_name.lower()
    for compound in _iter_compounds(root):
        for key, value in compound.items():
            if key.lower() == needle and isinstance(value, nbtlib.Compound):
                return compound, key, value
    return None


def _iter_regions(root: CompoundLike) -> Iterable[CompoundLike]:
    for compound in _iter_compounds(root):
        regions = compound.get("Regions")
        if isinstance(regions, nbtlib.Compound):
            for region in regions.values():
                if isinstance(region, nbtlib.Compound):
                    yield region


@dataclass
class Schematic:
    root: nbtlib.Compound

    @property
    def palette(self) -> dict[str, int]:
        found = _find_named_compound(self.root, "Palette")
        if found is not None:
            _parent, _key, palette = found
            return {str(name): int(index) for name, index in palette.items()}

        merged: dict[str, int] = {}
        idx = 0
        for region in _iter_regions(self.root):
            palette = region.get("BlockStatePalette")
            if not palette:
                continue
            for entry in palette:
                if not isinstance(entry, nbtlib.Compound):
                    continue
                state = _state_from_litematic_entry(entry)
                if state not in merged:
                    merged[state] = idx
                    idx += 1

        if merged:
            return merged

        raise KeyError("Palette")

    def replace_palette(self, new_palette: dict[str, int]) -> None:
        found = _find_named_compound(self.root, "Palette")
        if found is not None:
            parent, key, _palette = found
            parent[key] = nbtlib.Compound({name: nbtlib.Int(index) for name, index in new_palette.items()})
            return

        replacement = {old: new for old, new in new_palette.items()}
        region_found = False
        for region in _iter_regions(self.root):
            palette = region.get("BlockStatePalette")
            if not palette:
                continue
            region_found = True
            for entry in palette:
                if not isinstance(entry, nbtlib.Compound):
                    continue
                source_state = _state_from_litematic_entry(entry)
                target_state = replacement.get(source_state, source_state)
                target_name, _target_props = _split_blockstate(target_state)
                if target_name != str(entry.get("Name", "minecraft:air")):
                    entry["Name"] = nbtlib.String(target_name)

        if region_found:
            return

        raise KeyError("Palette")


def load_schematic(path: str) -> Schematic:
    root = nbtlib.load(path)
    return Schematic(root=root)


def save_schematic(schematic: Schematic, path: str) -> None:
    nbtlib.File(schematic.root).save(path)
