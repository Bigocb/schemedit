from __future__ import annotations
from dataclasses import dataclass, field
from collections import Counter
from typing import Optional
from litemapy import Schematic, Region, BlockState


@dataclass
class PaletteEntry:
    block_id: str
    properties: dict
    count: int

    @property
    def display_name(self) -> str:
        name = self.block_id.replace("minecraft:", "")
        if self.properties:
            props = ",".join(f"{k}={v}" for k, v in sorted(self.properties.items()))
            return f"{name}[{props}]"
        return name

    @property
    def full_id(self) -> str:
        if self.properties:
            props = ",".join(f"{k}={v}" for k, v in sorted(self.properties.items()))
            return f"{self.block_id}[{props}]"
        return self.block_id


@dataclass
class RegionInfo:
    name: str
    region: Region
    palette_entries: list[PaletteEntry] = field(default_factory=list)

    @property
    def dimensions(self) -> tuple[int, int, int]:
        xs = list(self.region.xrange())
        ys = list(self.region.yrange())
        zs = list(self.region.zrange())
        return len(xs), len(ys), len(zs)

    @property
    def total_blocks(self) -> int:
        return sum(e.count for e in self.palette_entries if e.block_id != "minecraft:air")


class LitematicSchematic:
    """High-level wrapper around a litemapy Schematic."""

    def __init__(self, schematic: Schematic, path: Optional[str] = None):
        self.schematic = schematic
        self.path = path
        self.regions: list[RegionInfo] = []
        self._load_regions()

    @classmethod
    def load(cls, path: str) -> "LitematicSchematic":
        schematic = Schematic.load(path)
        return cls(schematic, path)

    def save(self, path: Optional[str] = None) -> None:
        save_path = path or self.path
        if save_path is None:
            raise ValueError("No save path provided")
        self.schematic.save(save_path)
        self.path = save_path

    def _load_regions(self) -> None:
        self.regions = []
        for name, region in self.schematic.regions.items():
            palette_entries = self._count_palette(region)
            info = RegionInfo(
                name=name,
                region=region,
                palette_entries=palette_entries,
            )
            self.regions.append(info)

    def _count_palette(self, region: Region) -> list[PaletteEntry]:
        counts: Counter = Counter()
        for x in region.xrange():
            for y in region.yrange():
                for z in region.zrange():
                    block = region[x, y, z]
                    key = (block.id, tuple(sorted(block.properties())))
                    counts[key] += 1

        entries = []
        for (block_id, props_tuple), count in counts.most_common():
            entries.append(PaletteEntry(
                block_id=block_id,
                properties=dict(props_tuple),
                count=count,
            ))
        return entries

    def refresh_regions(self) -> None:
        """Reload region info (e.g. after a find/replace)."""
        self._load_regions()

    @property
    def name(self) -> str:
        n = self.schematic.name
        return n if n and n != "Unnamed" else "(unnamed)"

    @property
    def author(self) -> str:
        return self.schematic.author or ""

    @property
    def description(self) -> str:
        return self.schematic.description or ""

    @property
    def mc_version(self) -> int:
        return self.schematic.mc_version
