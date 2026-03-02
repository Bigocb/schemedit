"""
Face-culled voxel mesh builder.

build_mesh(region, uv_map) → numpy float32 array  shape (N, 8)
  columns: x  y  z  nx  ny  nz  u  v
  one row per vertex; 6 vertices per visible quad face (2 triangles, CCW winding).
  Only faces adjacent to air / out-of-bounds are emitted.

uv_map: dict  block_id → {'top': (u0,v0,u1,v1), 'side': (u0,v0,u1,v1), 'bottom': ...}
  Built by atlas_builder.Atlas.  If None, a placeholder UV (0,0,1,1) is used.
"""
from __future__ import annotations
import numpy as np
from litemapy import Region
from core.block_colors import AIR_IDS

# ------------------------------------------------------------------
# Face definitions: (normal, 4 corner offsets in CCW order when
# viewed from outside the cube, neighbour offset, face_key)
# ------------------------------------------------------------------
_FACES = [
    # (normal,            quad corners,                           neighbour,   face_key)
    ((0,  1, 0),  [(0,1,0),(1,1,0),(1,1,1),(0,1,1)],  (0, 1, 0),  'top'),
    ((0, -1, 0),  [(0,0,1),(1,0,1),(1,0,0),(0,0,0)],  (0,-1, 0),  'bottom'),
    ((1,  0, 0),  [(1,0,0),(1,0,1),(1,1,1),(1,1,0)],  (1, 0, 0),  'side'),
    ((-1, 0, 0),  [(0,0,1),(0,0,0),(0,1,0),(0,1,1)],  (-1,0, 0),  'side'),
    ((0,  0, 1),  [(1,0,1),(0,0,1),(0,1,1),(1,1,1)],  (0, 0, 1),  'side'),
    ((0,  0,-1),  [(0,0,0),(1,0,0),(1,1,0),(0,1,0)],  (0, 0,-1),  'side'),
]

# Fallback UV when no atlas is provided (covers whole texture)
_FALLBACK_UV = (0.0, 0.0, 1.0, 1.0)


def _is_solid(region: Region, x: int, y: int, z: int,
               xs: set[int], ys: set[int], zs: set[int]) -> bool:
    """Return True if the position is in-bounds and non-air."""
    if x not in xs or y not in ys or z not in zs:
        return False
    return region[x, y, z].id not in AIR_IDS


def build_mesh(
    region: Region,
    uv_map: dict[str, dict[str, tuple[float, float, float, float]]] | None = None,
) -> np.ndarray:
    """
    Build a face-culled voxel mesh for the region.

    Returns float32 array of shape (V, 8): x y z  nx ny nz  u v
    Each face quad → 6 vertices (2 CCW triangles).

    uv_map: atlas UV lookup built by atlas_builder.Atlas.uv_map.
            Pass None to use a placeholder UV (white square).
    """
    xs_list = list(region.xrange())
    ys_list = list(region.yrange())
    zs_list = list(region.zrange())
    xs_set  = set(xs_list)
    ys_set  = set(ys_list)
    zs_set  = set(zs_list)

    vertices: list[tuple] = []

    for x in xs_list:
        for y in ys_list:
            for z in zs_list:
                block = region[x, y, z]
                if block.id in AIR_IDS:
                    continue

                face_uvs = uv_map.get(block.id) if uv_map else None

                for (nx, ny, nz), corners, (ox, oy, oz), face_key in _FACES:
                    # Skip face if neighbour is solid (face would be hidden)
                    if _is_solid(region, x + ox, y + oy, z + oz, xs_set, ys_set, zs_set):
                        continue

                    # UV for this face
                    if face_uvs:
                        u0, v0, u1, v1 = face_uvs.get(face_key, face_uvs.get('side', _FALLBACK_UV))
                    else:
                        u0, v0, u1, v1 = _FALLBACK_UV

                    # Quad corners in world space
                    c = [(x + dx, y + dy, z + dz) for dx, dy, dz in corners]

                    # UV corners: c0→(u0,v0)  c1→(u1,v0)  c2→(u1,v1)  c3→(u0,v1)
                    uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]

                    # Triangle 1: c[0], c[2], c[1]  (CCW from outside)
                    for i in (0, 2, 1):
                        cx, cy, cz = c[i]
                        u, v = uv[i]
                        vertices.append((cx, cy, cz, nx, ny, nz, u, v))

                    # Triangle 2: c[0], c[3], c[2]
                    for i in (0, 3, 2):
                        cx, cy, cz = c[i]
                        u, v = uv[i]
                        vertices.append((cx, cy, cz, nx, ny, nz, u, v))

    if not vertices:
        return np.zeros((0, 8), dtype=np.float32)

    return np.array(vertices, dtype=np.float32)
