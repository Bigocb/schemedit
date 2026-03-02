"""
Greedy-meshed face-culled voxel mesh builder.

build_mesh(region, uv_map) → numpy float32 array  shape (N, 10)
  columns: x  y  z  nx  ny  nz  u  v  u0_atlas  v0_atlas

  u, v       — "world-UV": 0 → W for a merged W-block-wide quad.  The fragment
               shader tiles the atlas slot using fract(uv)*atlas_tile_size+uv0.
  u0_atlas,
  v0_atlas   — atlas slot origin (same for every vertex in a merged quad).

Greedy meshing: adjacent coplanar faces with the same texture (same atlas UV
slot) are merged into a single large quad.  For a dense uniform surface this
can reduce vertex count by 100×+.

uv_map: dict  block_id → {'top':(u0,v0,u1,v1), 'side':…, 'bottom':…}
  Built by atlas_builder.Atlas.  If None, placeholder UV (0,0,1,1) is used.
"""
from __future__ import annotations
import numpy as np
from litemapy import Region
from core.block_colors import AIR_IDS

_FALLBACK_UV = (0.0, 0.0, 1.0, 1.0)

# ── Face corner generators ────────────────────────────────────────────────────
#
# Each entry: (normal_xyz, face_key, sweep_axis, dim_a, dim_b, corners_fn)
#
# sweep_axis — axis index (0=X,1=Y,2=Z) perpendicular to the face
# dim_a, dim_b — the two axes that span the face's 2-D slice
# corners_fn(layer, a0, b0, aw, bh) → list of 4 (ix,iy,iz) in CCW order
#   when viewed from outside (from the direction of the normal).
#   For a 1×1 block these match the original mesh_builder corner lists exactly.
#
# CCW winding derivation:
#   Two tangent vectors T1,T2 must satisfy T1×T2 = normal.
#   Corners are p, p+T1*aw, p+T1*aw+T2*bh, p+T2*bh.
#
_FACE_DEFS = [
    # +Y top  —  T1=+X, T2=+Z,  T1×T2=(0,-1,0)? Verify: (1,0,0)×(0,0,1)=(0*1-0*0, 0*0-1*1, 1*0-0*0)=(0,-1,0) Hmm.
    # Original corners: (0,1,0),(1,1,0),(1,1,1),(0,1,1) = CCW from above ✓
    ((0,  1, 0), 'top',    1, 0, 2,
     lambda l, a0, b0, aw, bh: [
         (a0,    l+1, b0),    (a0+aw, l+1, b0),
         (a0+aw, l+1, b0+bh), (a0,    l+1, b0+bh)]),
    # -Y bottom  —  original: (0,0,1),(1,0,1),(1,0,0),(0,0,0)
    ((0, -1, 0), 'bottom', 1, 0, 2,
     lambda l, a0, b0, aw, bh: [
         (a0,    l, b0+bh), (a0+aw, l, b0+bh),
         (a0+aw, l, b0),    (a0,    l, b0)]),
    # +X  —  original: (1,0,0),(1,0,1),(1,1,1),(1,1,0)
    #  sweep=X, dim_a=Z, dim_b=Y
    ((1,  0, 0), 'side',   0, 2, 1,
     lambda l, a0, b0, aw, bh: [
         (l+1, b0,    a0),    (l+1, b0,    a0+aw),
         (l+1, b0+bh, a0+aw), (l+1, b0+bh, a0)]),
    # -X  —  original: (0,0,1),(0,0,0),(0,1,0),(0,1,1)
    ((-1, 0, 0), 'side',   0, 2, 1,
     lambda l, a0, b0, aw, bh: [
         (l, b0,    a0+aw), (l, b0,    a0),
         (l, b0+bh, a0),    (l, b0+bh, a0+aw)]),
    # +Z  —  original: (1,0,1),(0,0,1),(0,1,1),(1,1,1)
    #  sweep=Z, dim_a=X, dim_b=Y
    ((0,  0, 1), 'side',   2, 0, 1,
     lambda l, a0, b0, aw, bh: [
         (a0+aw, b0,    l+1), (a0,    b0,    l+1),
         (a0,    b0+bh, l+1), (a0+aw, b0+bh, l+1)]),
    # -Z  —  original: (0,0,0),(1,0,0),(1,1,0),(0,1,0)
    ((0,  0,-1), 'side',   2, 0, 1,
     lambda l, a0, b0, aw, bh: [
         (a0,    b0,    l), (a0+aw, b0,    l),
         (a0+aw, b0+bh, l), (a0,    b0+bh, l)]),
]

# UV corners for the 4 quad vertices; u goes 0→aw, v goes 0→bh
_UV_CORNERS = [(0, 0), (1, 0), (1, 1), (0, 1)]   # scaled by (aw, bh) per quad

# Triangle index pairs using CCW winding (0-indexed into the 4 corners)
_TRI = [(0, 2, 1), (0, 3, 2)]


# ── Greedy rectangle decomposition ───────────────────────────────────────────

def _greedy(mask: dict, na: int, nb: int):
    """
    Decompose a 2-D face mask into maximal axis-aligned rectangles.

    mask    — {(a, b): key} where key is the merge identifier (UV tuple);
              absent cells are empty (no face).
    na, nb  — mask dimensions: a in [0, na), b in [0, nb)

    Yields (a_start, b_start, a_width, b_height, key).
    """
    visited: set[tuple[int, int]] = set()
    for b in range(nb):
        for a in range(na):
            if (a, b) in visited or (a, b) not in mask:
                continue
            key = mask[a, b]

            # Grow in the a-direction
            aw = 1
            while (a + aw < na and
                   (a + aw, b) in mask and
                   (a + aw, b) not in visited and
                   mask[a + aw, b] == key):
                aw += 1

            # Grow in the b-direction
            bh = 1
            while b + bh < nb:
                if all(
                    (a + da, b + bh) in mask and
                    (a + da, b + bh) not in visited and
                    mask[a + da, b + bh] == key
                    for da in range(aw)
                ):
                    bh += 1
                else:
                    break

            # Mark visited
            for db in range(bh):
                for da in range(aw):
                    visited.add((a + da, b + db))

            yield a, b, aw, bh, key


# ── Main entry point ─────────────────────────────────────────────────────────

def build_mesh(
    region: Region,
    uv_map: dict[str, dict[str, tuple[float, float, float, float]]] | None = None,
) -> np.ndarray:
    """
    Build a greedy-meshed voxel mesh for the region.

    Returns float32 array of shape (V, 10):
        x  y  z  |  nx  ny  nz  |  u  v  |  u0_atlas  v0_atlas

    u, v are "world-UV" that go from 0→W (or 0→H) across a merged quad.
    The fragment shader tiles the atlas slot with:
        tiled_uv = uv0_atlas + fract(v_uv) * atlas_tile_size
    """
    xs = list(region.xrange())
    ys = list(region.yrange())
    zs = list(region.zrange())
    if not xs or not ys or not zs:
        return np.zeros((0, 10), dtype=np.float32)

    x0, y0, z0 = min(xs), min(ys), min(zs)
    NX = max(xs) - x0 + 1
    NY = max(ys) - y0 + 1
    NZ = max(zs) - z0 + 1

    # ── 1. Pre-compute solid flags and block IDs ──────────────────────────────
    is_solid = np.zeros((NX, NY, NZ), dtype=bool)
    # Block IDs stored in a 3-D list (sparse — only non-air set)
    ids: list[list[list[str | None]]] = [
        [[None] * NZ for _ in range(NY)] for _ in range(NX)
    ]

    for x in xs:
        for y in ys:
            for z in zs:
                block = region[x, y, z]
                if block.id not in AIR_IDS:
                    ix, iy, iz = x - x0, y - y0, z - z0
                    is_solid[ix, iy, iz] = True
                    ids[ix][iy][iz] = block.id

    # ── 2. UV helper ─────────────────────────────────────────────────────────
    def _uv(bid: str, face_key: str) -> tuple[float, float, float, float]:
        if uv_map and bid in uv_map:
            fuvs = uv_map[bid]
            return fuvs.get(face_key, fuvs.get('side', _FALLBACK_UV))
        return _FALLBACK_UV

    # ── 3. Sweep all 6 face directions ───────────────────────────────────────
    verts: list[tuple] = []

    for (nx, ny, nz), face_key, sweep, dim_a, dim_b, corners_fn in _FACE_DEFS:
        N_sweep = (NX, NY, NZ)[sweep]
        na      = (NX, NY, NZ)[dim_a]
        nb      = (NX, NY, NZ)[dim_b]
        sign    = nx + ny + nz            # +1 or -1

        for layer in range(N_sweep):
            # ── Build 2-D face mask for this layer ───────────────────────────
            mask: dict[tuple[int, int], tuple] = {}

            for a in range(na):
                for b in range(nb):
                    # Convert (layer, a, b) → local (ix, iy, iz)
                    coord = [0, 0, 0]
                    coord[sweep] = layer
                    coord[dim_a] = a
                    coord[dim_b] = b
                    ix, iy, iz = coord

                    if not is_solid[ix, iy, iz]:
                        continue

                    # Neighbour in the direction of the normal
                    nix = ix + nx
                    niy = iy + ny
                    niz = iz + nz
                    if (0 <= nix < NX and
                            0 <= niy < NY and
                            0 <= niz < NZ and
                            is_solid[nix, niy, niz]):
                        continue           # face hidden by solid neighbour

                    bid = ids[ix][iy][iz]
                    mask[a, b] = _uv(bid, face_key)

            if not mask:
                continue

            # ── Greedy merge and emit quads ───────────────────────────────────
            for a0, b0, aw, bh, uv in _greedy(mask, na, nb):
                u0_atl, v0_atl, u1_atl, v1_atl = uv

                # World-space corners (4 vertices of the merged quad)
                c = corners_fn(layer, a0, b0, aw, bh)
                # Translate from local-index space to world space
                c = [(cx + x0, cy + y0, cz + z0) for cx, cy, cz in c]

                # UV corners: scale by (aw, bh) so the shader can tile
                uvcs = [(float(aw) * du, float(bh) * dv) for du, dv in _UV_CORNERS]

                # Two triangles: (0,2,1) and (0,3,2) — CCW from outside
                for i0, i1, i2 in _TRI:
                    for i in (i0, i1, i2):
                        cx, cy, cz = c[i]
                        u,  v      = uvcs[i]
                        verts.append((
                            float(cx), float(cy), float(cz),
                            float(nx), float(ny), float(nz),
                            u, v,
                            u0_atl, v0_atl,
                        ))

    if not verts:
        return np.zeros((0, 10), dtype=np.float32)

    return np.array(verts, dtype=np.float32)
