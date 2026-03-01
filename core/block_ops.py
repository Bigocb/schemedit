from __future__ import annotations
from litemapy import Region, BlockState


def find_replace(
    region: Region,
    find_id: str,
    replace_id: str,
    find_properties: dict | None = None,
    replace_properties: dict | None = None,
) -> int:
    """
    Iterate every position in a region and replace blocks matching find_id
    (and optionally find_properties) with a new BlockState.

    Returns the number of blocks changed.
    """
    find_props = find_properties or {}
    replace_props = replace_properties or {}
    new_block = BlockState(replace_id, **replace_props)

    changed = 0
    for x in region.xrange():
        for y in region.yrange():
            for z in region.zrange():
                block = region[x, y, z]
                if block.id != find_id:
                    continue
                if find_props and not _props_match(dict(block.properties()), find_props):
                    continue
                region[x, y, z] = new_block
                changed += 1
    return changed


def count_block(region: Region, block_id: str) -> int:
    """Count occurrences of a given block ID in a region."""
    total = 0
    for x in region.xrange():
        for y in region.yrange():
            for z in region.zrange():
                if region[x, y, z].id == block_id:
                    total += 1
    return total


def delete_at(region: Region, x: int, y: int, z: int) -> None:
    """Replace a single block position with air."""
    region[x, y, z] = BlockState("minecraft:air")


def _props_match(block_props: dict, filter_props: dict) -> bool:
    for k, v in filter_props.items():
        if block_props.get(k) != v:
            return False
    return True
