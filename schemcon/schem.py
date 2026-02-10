from __future__ import annotations

from dataclasses import dataclass

import nbtlib


def _split_blockstate(value: str) -> tuple[str, str | None]:
    if "[" in value and value.endswith("]"):
        name, rest = value.split("[", 1)
        return name, rest[:-1]
    return value, None


def _state_from_litematic_entry(entry: nbtlib.Compound) -> str:
    name = str(entry.get("Name", "minecraft:air"))
    props = entry.get("Properties")
    if props:
        parts = [f"{key}={str(val)}" for key, val in sorted(props.items())]
        return f"{name}[{','.join(parts)}]"
    return name


@dataclass
class Schematic:
    root: nbtlib.Compound

    @property
    def palette(self) -> dict[str, int]:
        if "Palette" in self.root:
            return {str(name): int(index) for name, index in self.root["Palette"].items()}

        if "Regions" in self.root:
            merged: dict[str, int] = {}
            idx = 0
            for region in self.root["Regions"].values():
                palette = region.get("BlockStatePalette")
                if not palette:
                    continue
                for entry in palette:
                    state = _state_from_litematic_entry(entry)
                    if state not in merged:
                        merged[state] = idx
                        idx += 1
            if merged:
                return merged

        raise KeyError("Palette")

    def replace_palette(self, new_palette: dict[str, int]) -> None:
        if "Palette" in self.root:
            compound = nbtlib.Compound({name: nbtlib.Int(index) for name, index in new_palette.items()})
            self.root["Palette"] = compound
            return

        if "Regions" in self.root:
            replacement = {old: new for old, new in new_palette.items()}
            for region in self.root["Regions"].values():
                palette = region.get("BlockStatePalette")
                if not palette:
                    continue
                for entry in palette:
                    source_state = _state_from_litematic_entry(entry)
                    target_state = replacement.get(source_state, source_state)
                    target_name, _target_props = _split_blockstate(target_state)
                    if target_name != str(entry.get("Name", "minecraft:air")):
                        entry["Name"] = nbtlib.String(target_name)
            return

        raise KeyError("Palette")


def load_schematic(path: str) -> Schematic:
    root = nbtlib.load(path)
    return Schematic(root=root)


def save_schematic(schematic: Schematic, path: str) -> None:
    nbtlib.File(schematic.root).save(path)
