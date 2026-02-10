from __future__ import annotations

from dataclasses import dataclass

import nbtlib


@dataclass
class Schematic:
    root: nbtlib.Compound

    @property
    def palette(self) -> dict[str, int]:
        return {str(name): int(index) for name, index in self.root["Palette"].items()}

    def replace_palette(self, new_palette: dict[str, int]) -> None:
        compound = nbtlib.Compound({name: nbtlib.Int(index) for name, index in new_palette.items()})
        self.root["Palette"] = compound


def load_schematic(path: str) -> Schematic:
    root = nbtlib.load(path)
    return Schematic(root=root)


def save_schematic(schematic: Schematic, path: str) -> None:
    nbtlib.File(schematic.root).save(path)
