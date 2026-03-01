"""
Face-culled voxel mesh builder.

build_mesh(region) → numpy float32 array  shape (N, 9)
  columns: x  y  z  nx  ny  nz  r  g  b
  one row per vertex; 6 vertices per visible quad face (2 triangles, CCW winding).
  Only faces adjacent to air / out-of-bounds are emitted.
"""
from __future__ import annotations
import numpy as np
from litemapy import Region
from core.block_colors import block_rgb, AIR_IDS

# ------------------------------------------------------------------
# Face definitions: (normal, 4 corner offsets in CCW order when
# viewed from outside the cube)
# Each corner offset is (dx, dy, dz) added to the block position.
# We split each quad into 2 triangles: [0,1,2] and [0,2,3].
# ------------------------------------------------------------------
_FACES: list[tuple[tuple[float, float, float], list[tuple[int, int, int]], tuple[int, int, int]]] = [
    # (normal,  quad corners,                              neighbour offset)
    ((0, 1, 0),  [(0,1,0),(1,1,0),(1,1,1),(0,1,1)],  (0, 1, 0)),   # top    +Y
    ((0,-1, 0),  [(0,0,1),(1,0,1),(1,0,0),(0,0,0)],  (0,-1, 0)),   # bottom -Y
    ((1, 0, 0),  [(1,0,0),(1,0,1),(1,1,1),(1,1,0)],  (1, 0, 0)),   # right  +X
    ((-1,0, 0),  [(0,0,1),(0,0,0),(0,1,0),(0,1,1)],  (-1,0, 0)),   # left   -X
    ((0, 0, 1),  [(1,0,1),(0,0,1),(0,1,1),(1,1,1)],  (0, 0, 1)),   # front  +Z
    ((0, 0,-1),  [(0,0,0),(1,0,0),(1,1,0),(0,1,0)],  (0, 0,-1)),   # back   -Z
]


def _is_solid(region: Region, x: int, y: int, z: int,
               xs: set[int], ys: set[int], zs: set[int]) -> bool:
    """Return True if the position is in-bounds and non-air."""
    if x not in xs or y not in ys or z not in zs:
        return False
    return region[x, y, z].id not in AIR_IDS


def build_mesh(region: Region) -> np.ndarray:
    """
    Build a face-culled voxel mesh for the region.
    Returns a float32 numpy array of shape (V, 9) or shape (0, 9) if empty.
    Columns: x, y, z, nx, ny, nz, r, g, b  (RGB in 0.0–1.0 range)
    """
    xs_list = list(region.xrange())
    ys_list = list(region.yrange())
    zs_list = list(region.zrange())
    xs_set = set(xs_list)
    ys_set = set(ys_list)
    zs_set = set(zs_list)

    vertices: list[tuple] = []

    for x in xs_list:
        for y in ys_list:
            for z in zs_list:
                block = region[x, y, z]
                if block.id in AIR_IDS:
                    continue

                r8, g8, b8 = block_rgb(block.id)
                r, g, b = r8 / 255.0, g8 / 255.0, b8 / 255.0

                for (nx, ny, nz), corners, (ox, oy, oz) in _FACES:
                    # Skip face if neighbour is solid (face would be hidden)
                    if _is_solid(region, x + ox, y + oy, z + oz, xs_set, ys_set, zs_set):
                        continue

                    # Quad corners in world space
                    c = [(x + dx, y + dy, z + dz) for dx, dy, dz in corners]

                    # Triangles use reversed order (c[0],c[2],c[1] / c[0],c[3],c[2])
                    # to produce CCW winding when viewed from outside the cube.
                    for cx, cy, cz in (c[0], c[2], c[1]):
                        vertices.append((cx, cy, cz, nx, ny, nz, r, g, b))
                    for cx, cy, cz in (c[0], c[3], c[2]):
                        vertices.append((cx, cy, cz, nx, ny, nz, r, g, b))

    if not vertices:
        return np.zeros((0, 9), dtype=np.float32)

    return np.array(vertices, dtype=np.float32)
