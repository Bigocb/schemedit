"""
3D OpenGL voxel viewer embedded in a QOpenGLWidget.

Controls:
  Right-click (stationary) — block context menu (replace / delete / place)
  Right-drag               — look around (yaw / pitch)
  W / S        — fly forward / back
  A / D        — strafe left / right
  Q / E        — move down / up
  Scroll       — adjust move speed
"""
from __future__ import annotations
import math
import numpy as np
import moderngl
import glm
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import QLabel, QMenu, QDialog
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QWheelEvent, QMouseEvent, QKeyEvent, QSurfaceFormat, QCursor, QAction
from core.schematic import LitematicSchematic
from core.mesh_builder import build_mesh
from core.atlas_builder import Atlas
from core.block_colors import AIR_IDS
from core import texture_cache as _tex
from core import settings as _cfg


# ── GLSL shaders ──────────────────────────────────────────────────────────────

_VERT_SRC = """
#version 330
in vec3 in_position;
in vec3 in_normal;
in vec2 in_uv;
uniform mat4 mvp;
out vec3 v_normal;
out vec2 v_uv;
void main() {
    gl_Position = mvp * vec4(in_position, 1.0);
    v_normal = in_normal;
    v_uv     = in_uv;
}
"""

_FRAG_SRC = """
#version 330
in vec3 v_normal;
in vec2 v_uv;
uniform sampler2D tex;
out vec4 fragColor;
void main() {
    vec3 light = normalize(vec3(1.0, 2.0, 1.0));
    float d    = max(dot(v_normal, light), 0.0);
    vec4 color = texture(tex, v_uv);
    fragColor  = vec4(color.rgb * (0.35 + 0.65 * d), 1.0);
}
"""


# ── Hover-highlight shaders (thin wire-frame cube drawn over hovered block) ────

_HIGHLIGHT_VERT = """
#version 330
in vec3 in_pos;
uniform mat4 mvp;
void main() { gl_Position = mvp * vec4(in_pos, 1.0); }
"""

_HIGHLIGHT_FRAG = """
#version 330
out vec4 fragColor;
void main() { fragColor = vec4(1.0, 1.0, 0.25, 1.0); }
"""

# 12 edges of a unit cube as 24 vertices for GL_LINES
_WIRE_VERTS: np.ndarray = np.array([
    # bottom face (y = 0)
    0,0,0, 1,0,0,   1,0,0, 1,0,1,   1,0,1, 0,0,1,   0,0,1, 0,0,0,
    # top face (y = 1)
    0,1,0, 1,1,0,   1,1,0, 1,1,1,   1,1,1, 0,1,1,   0,1,1, 0,1,0,
    # vertical edges
    0,0,0, 0,1,0,   1,0,0, 1,1,0,   1,0,1, 1,1,1,   0,0,1, 0,1,1,
], dtype=np.float32).reshape(-1, 3)


# ── Main widget ────────────────────────────────────────────────────────────────

class View3D(QOpenGLWidget):
    """3D voxel renderer embedded in the Qt tab widget."""

    # Same surface as LayerView so MainWindow can connect the same handlers
    block_clicked       = pyqtSignal(str, int, int, int)  # block_id, x, y, z
    replace_requested   = pyqtSignal(str, dict)
    delete_requested    = pyqtSignal(str, dict)
    delete_at_requested = pyqtSignal(int, int, int)
    set_block_at        = pyqtSignal(int, int, int, str)

    def __init__(self, parent=None):
        # Request an OpenGL 3.3 Core profile context
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setDepthBufferSize(24)
        QSurfaceFormat.setDefaultFormat(fmt)

        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(400, 300)

        # ── ModernGL objects (set in initializeGL) ──
        self.ctx: moderngl.Context | None = None
        self.prog: moderngl.Program | None = None
        self._vbo: moderngl.Buffer | None = None
        self._vao: moderngl.VertexArray | None = None
        self._texture: moderngl.Texture | None = None
        self._vertex_count = 0
        self._schematic: LitematicSchematic | None = None
        # Mesh / atlas data buffered here if load() is called before initializeGL()
        self._pending_data: np.ndarray | None = None
        self._pending_atlas: Atlas | None = None
        self._atlas: Atlas | None = None   # current atlas (CPU side)

        # ── Camera ──
        self._cam_pos = glm.vec3(8.0, 8.0, 30.0)
        self._yaw   = -90.0   # degrees — look roughly toward -Z initially
        self._pitch = -20.0   # degrees — look slightly down

        # ── Projection ──
        self._projection = glm.mat4(1.0)

        # ── Input state ──
        self._right_btn_held = False
        self._last_mouse_x = 0
        self._last_mouse_y = 0
        self._right_press_x = 0.0   # where right-button went down (drag detection)
        self._right_press_y = 0.0
        self._keys_held: set[Qt.Key] = set()
        self._move_speed = _cfg.move_speed()
        self._velocity = glm.vec3(0.0, 0.0, 0.0)  # for smooth damped movement
        # Key bindings — populated after _hint is created below
        self._fly_keys: dict[str, Qt.Key] = {}

        # ── Hover highlight ──
        self._hovered_voxel: tuple[int, int, int] | None = None
        # Highlight GL objects (created in initializeGL)
        self._highlight_prog: moderngl.Program | None = None
        self._highlight_vbo:  moderngl.Buffer | None = None
        self._highlight_vao:  moderngl.VertexArray | None = None

        # ── Tick timer (fly movement) ──
        self._timer = QTimer(self)
        self._timer.setInterval(16)   # ~60 fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        # ── Hint overlay label (shown before any schematic is loaded) ──
        self._hint = QLabel("", self)   # text set by _reload_fly_keys() below
        self._hint.setStyleSheet(
            "color: white; background: rgba(0,0,0,160); padding: 6px; font-size: 11px;"
        )
        self._hint.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        # Load key bindings from settings now that _hint exists
        self._reload_fly_keys()

        # Refresh atlas slots when background texture downloads complete
        _tex._manager.batch_ready.connect(self._on_textures_ready)

    # ── OpenGL lifecycle ───────────────────────────────────────────────────────

    def initializeGL(self) -> None:
        try:
            self.ctx = moderngl.create_context()
        except Exception as e:
            print(f"[View3D] Failed to create OpenGL context: {e}")
            return

        try:
            self.prog = self.ctx.program(
                vertex_shader=_VERT_SRC,
                fragment_shader=_FRAG_SRC,
            )
        except Exception as e:
            print(f"[View3D] Shader compilation error: {e}")
            self.ctx = None
            return

        # Highlight (wireframe cube) program
        try:
            self._highlight_prog = self.ctx.program(
                vertex_shader=_HIGHLIGHT_VERT,
                fragment_shader=_HIGHLIGHT_FRAG,
            )
            wire = np.ascontiguousarray(_WIRE_VERTS, dtype=np.float32)
            self._highlight_vbo = self.ctx.buffer(wire.tobytes())
            self._highlight_vao = self.ctx.vertex_array(
                self._highlight_prog,
                [(self._highlight_vbo, '3f', 'in_pos')],
            )
        except Exception as e:
            print(f"[View3D] highlight shader error: {e}")

        # Upload any atlas / mesh data that arrived before the GL context existed
        if self._pending_atlas is not None:
            self._upload_atlas(self._pending_atlas)
            self._pending_atlas = None
        if self._pending_data is not None:
            self._upload_mesh(self._pending_data)
            self._pending_data = None
            self.update()

    def resizeGL(self, w: int, h: int) -> None:
        if h == 0:
            h = 1
        dpr = self.devicePixelRatio()
        pw, ph = int(w * dpr), int(h * dpr)
        self._projection = glm.perspective(glm.radians(60.0), pw / ph, 0.1, 2000.0)
        if self.ctx:
            self.ctx.viewport = (0, 0, pw, ph)

    def paintGL(self) -> None:
        if self.ctx is None or self.prog is None:
            return

        # Upload any pending atlas / mesh data inside the Qt GL callback.
        if self._pending_atlas is not None:
            self._upload_atlas(self._pending_atlas)
            self._pending_atlas = None

        if self._pending_data is not None:
            self._upload_mesh(self._pending_data)
            self._pending_data = None

        # Qt composites via an internal FBO — render into it, not FBO 0.
        qt_fbo = self.ctx.detect_framebuffer(self.defaultFramebufferObject())
        qt_fbo.use()
        qt_fbo.clear(0.15, 0.17, 0.20, 1.0)

        if self._vao is None or self._vertex_count == 0:
            return

        dpr = self.devicePixelRatio()
        self.ctx.viewport = (0, 0, int(self.width() * dpr), int(self.height() * dpr))
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.depth_func = '<'
        self.ctx.disable_direct(0x0C11)  # GL_SCISSOR_TEST — prevent Qt from clipping

        # Bind atlas texture to unit 0
        if self._texture:
            self._texture.use(0)

        # bytes(glm.mat4) is row-major; GL expects column-major, so transpose first.
        mvp = self._projection * self._view_matrix()
        self.prog['mvp'].write(bytes(glm.transpose(mvp)))
        self.prog['tex'].value = 0
        self._vao.render(moderngl.TRIANGLES, self._vertex_count)

        # Hover highlight — yellow wire-frame cube around the pointed-at block
        if (self._hovered_voxel is not None
                and self._highlight_prog is not None
                and self._highlight_vao is not None):
            bx, by, bz = self._hovered_voxel
            translate = glm.translate(glm.mat4(1.0), glm.vec3(bx, by, bz))
            h_mvp = self._projection * self._view_matrix() * translate
            self._highlight_prog['mvp'].write(bytes(glm.transpose(h_mvp)))
            try:
                self.ctx.line_width = 2.0
            except Exception:
                pass
            self._highlight_vao.render(moderngl.LINES, 24)

    # ── Public API ─────────────────────────────────────────────────────────────

    def load(self, schematic: LitematicSchematic) -> None:
        """Build mesh from schematic and upload to GPU. Reset camera to a good vantage."""
        if not schematic or not schematic.regions:
            self.clear()
            return

        # Build mesh on the CPU (may take a moment for large schematics)
        region = schematic.regions[0].region

        # Collect unique block IDs, build texture atlas, then build UV mesh
        unique_ids = {
            region[x, y, z].id
            for x in region.xrange()
            for y in region.yrange()
            for z in region.zrange()
        }
        atlas = Atlas(list(unique_ids))
        data  = build_mesh(region, atlas.uv_map)

        self._schematic = schematic

        # Center camera on the schematic
        xs = list(region.xrange())
        ys = list(region.yrange())
        zs = list(region.zrange())
        if xs and ys and zs:
            cx = (min(xs) + max(xs)) / 2
            cy = (min(ys) + max(ys)) / 2
            cz = (min(zs) + max(zs)) / 2
            diagonal = math.sqrt(
                (max(xs) - min(xs)) ** 2 +
                (max(ys) - min(ys)) ** 2 +
                (max(zs) - min(zs)) ** 2
            )
            dist = max(diagonal * 1.1, 25.0)
            self._cam_pos = glm.vec3(cx, cy + diagonal * 0.2, cz + dist)
            self._yaw   = -90.0
            self._pitch = -15.0
            # Save for R-key reset
            self._cam_start_pos   = glm.vec3(self._cam_pos)
            self._cam_start_yaw   = self._yaw
            self._cam_start_pitch = self._pitch

        # Always buffer — upload happens inside paintGL (safe Qt GL callback)
        self._atlas        = atlas
        self._pending_atlas = atlas
        self._pending_data  = data
        self.update()

    def refresh(self) -> None:
        """Rebuild mesh after edits (keeps camera position)."""
        if self._schematic is not None and self._schematic.regions:
            region = self._schematic.regions[0].region
            unique_ids = {
                region[x, y, z].id
                for x in region.xrange()
                for y in region.yrange()
                for z in region.zrange()
            }
            atlas = Atlas(list(unique_ids))
            data  = build_mesh(region, atlas.uv_map)
            self._atlas         = atlas
            self._pending_atlas = atlas
            self._pending_data  = data
            self.update()

    def clear(self) -> None:
        """Release GPU buffers and show placeholder."""
        self._free_buffers()
        self._vertex_count = 0
        self.update()

    # ── Camera helpers ─────────────────────────────────────────────────────────

    def _forward(self) -> glm.vec3:
        yaw_r   = math.radians(self._yaw)
        pitch_r = math.radians(self._pitch)
        x = math.cos(pitch_r) * math.cos(yaw_r)
        y = math.sin(pitch_r)
        z = math.cos(pitch_r) * math.sin(yaw_r)
        return glm.normalize(glm.vec3(x, y, z))

    def _forward_horizontal(self) -> glm.vec3:
        """Forward direction projected onto the XZ plane — WASD stays horizontal
        regardless of camera pitch (like Minecraft creative flight)."""
        yaw_r = math.radians(self._yaw)
        return glm.normalize(glm.vec3(math.cos(yaw_r), 0.0, math.sin(yaw_r)))

    def _right_from_yaw(self) -> glm.vec3:
        """Right vector derived from yaw only — stable at all pitch values."""
        fwd_h = self._forward_horizontal()
        return glm.normalize(glm.cross(fwd_h, glm.vec3(0.0, 1.0, 0.0)))

    def _right(self) -> glm.vec3:
        return self._right_from_yaw()

    def _view_matrix(self) -> glm.mat4:
        """
        Build the view matrix.  The camera-up vector is derived from yaw only
        (cross of yaw-right × forward) so lookAt stays well-defined even when
        forward ≈ ±world-Y (i.e. looking straight up or straight down).
        """
        fwd   = self._forward()
        right = self._right_from_yaw()
        up    = glm.normalize(glm.cross(right, fwd))
        return glm.lookAt(self._cam_pos, self._cam_pos + fwd, up)

    def _reset_camera(self) -> None:
        """Return camera to the initial overview position (R key)."""
        if hasattr(self, '_cam_start_pos'):
            self._cam_pos   = glm.vec3(self._cam_start_pos)
            self._yaw       = self._cam_start_yaw
            self._pitch     = self._cam_start_pitch
            self.update()

    # ── Settings ───────────────────────────────────────────────────────────────

    def _reload_fly_keys(self) -> None:
        """Load key bindings from settings into self._fly_keys."""
        raw = _cfg.get_fly_keys()
        self._fly_keys = {}
        for action, key_str in raw.items():
            # Try exact name first (e.g. "W" → Key_W, "Space" → Key_Space)
            qt_key = getattr(Qt.Key, f"Key_{key_str}", None)
            # Fallback: try uppercase (handles lowercase stored values)
            if qt_key is None:
                qt_key = getattr(Qt.Key, f"Key_{key_str.upper()}", None)
            if qt_key is not None:
                self._fly_keys[action] = qt_key
        # Update hint text to show current bindings
        fk = raw
        self._hint.setText(
            "Open a schematic, then click here to move the camera.\n"
            f"Right-drag: look  |  {fk.get('forward','W')}/{fk.get('backward','S')}: fwd/back  |  "
            f"{fk.get('left','A')}/{fk.get('right','D')}: strafe  |  "
            f"{fk.get('up','E')}/{fk.get('down','Q')}: up/down  |  "
            "Scroll: zoom  |  Ctrl+Scroll: speed  |  "
            f"{fk.get('reset','R')}: reset view"
        )
        self._hint.adjustSize()

    def reload_settings(self) -> None:
        """Re-read settings (call after settings dialog closes)."""
        self._reload_fly_keys()
        self._move_speed = _cfg.move_speed()

    # ── Tick (movement) ────────────────────────────────────────────────────────

    def _tick(self) -> None:
        dt    = 0.016  # seconds per frame (matches 16ms timer)
        fwd_h = self._forward_horizontal()   # XZ-plane only — no pitch drift
        right = glm.normalize(glm.cross(fwd_h, glm.vec3(0, 1, 0)))
        up    = glm.vec3(0.0, 1.0, 0.0)

        K = self._fly_keys   # shortcut

        # Build target velocity from held keys (zero if no keys pressed)
        target = glm.vec3(0.0, 0.0, 0.0)
        if K.get("forward")  in self._keys_held: target += fwd_h * self._move_speed
        if K.get("backward") in self._keys_held: target -= fwd_h * self._move_speed
        if K.get("left")     in self._keys_held: target -= right  * self._move_speed
        if K.get("right")    in self._keys_held: target += right  * self._move_speed
        if K.get("down")     in self._keys_held: target -= up     * self._move_speed
        if K.get("up")       in self._keys_held: target += up     * self._move_speed

        # Soft lerp toward target — gives smooth acceleration and deceleration
        self._velocity = glm.mix(self._velocity, target, 0.22)

        vel_len = glm.length(self._velocity)
        if vel_len > 0.01:
            self._cam_pos += self._velocity * dt
            self.update()

    # ── Input events ───────────────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._right_btn_held = True
            self._right_press_x  = event.position().x()
            self._right_press_y  = event.position().y()
            self._last_mouse_x   = self._right_press_x
            self._last_mouse_y   = self._right_press_y
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._right_btn_held = False
            dx = event.position().x() - self._right_press_x
            dy = event.position().y() - self._right_press_y
            # If the mouse barely moved, treat as a context-menu click
            if dx * dx + dy * dy < 25:
                self._on_right_click(event.position().x(), event.position().y())
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._right_btn_held:
            dx = event.position().x() - self._last_mouse_x
            dy = event.position().y() - self._last_mouse_y
            self._last_mouse_x = event.position().x()
            self._last_mouse_y = event.position().y()

            sensitivity = _cfg.mouse_sensitivity()
            self._yaw   += dx * sensitivity
            self._pitch -= dy * sensitivity
            # No pitch clamp — full 360° vertical look is supported because
            # _view_matrix derives "up" from yaw rather than world-Y.
            self.update()
        else:
            # Update hover highlight as the cursor moves over blocks
            hit = self._cast_ray(event.position().x(), event.position().y())
            new_hover = hit[1] if hit else None
            if new_hover != self._hovered_voxel:
                self._hovered_voxel = new_hover
                self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        """Clear hover highlight when cursor leaves the widget."""
        if self._hovered_voxel is not None:
            self._hovered_voxel = None
            self.update()
        super().leaveEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Ctrl + Scroll — adjust fly speed
            if delta > 0:
                self._move_speed = min(self._move_speed * 1.2, 500.0)
            else:
                self._move_speed = max(self._move_speed / 1.2, 0.5)
        else:
            # Scroll — dolly zoom along the look direction
            step = self._move_speed * 0.25
            self._cam_pos += self._forward() * (step if delta > 0 else -step)
            self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        pressed = Qt.Key(event.key())
        if pressed == self._fly_keys.get("reset", Qt.Key.Key_R):
            self._reset_camera()
            return
        self._keys_held.add(pressed)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        self._keys_held.discard(Qt.Key(event.key()))
        super().keyReleaseEvent(event)

    # ── Ray casting & interaction ──────────────────────────────────────────────

    def _cast_ray(self, mx: float, my: float):
        """
        Cast a ray from the camera through screen pixel (mx, my) and return the
        first non-air voxel hit, or None.

        Returns (block, (ix,iy,iz), (px,py,pz)) where (px,py,pz) is the last
        air cell before the hit — useful for placing a block on a face.
        """
        if not self._schematic or not self._schematic.regions:
            return None
        region = self._schematic.regions[0].region
        xs = list(region.xrange())
        ys = list(region.yrange())
        zs = list(region.zrange())
        if not xs or not ys or not zs:
            return None
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        z_min, z_max = min(zs), max(zs)

        w, h = self.width(), self.height()
        if w == 0 or h == 0:
            return None

        # Convert screen pixel → world-space ray direction
        ndc_x =  (2.0 * mx / w) - 1.0
        ndc_y = -(2.0 * my / h) + 1.0   # Qt y-down → NDC y-up
        half_h = math.tan(math.radians(60.0) / 2.0)
        half_w = half_h * (w / h)

        fwd    = self._forward()
        right  = self._right_from_yaw()
        cam_up = glm.normalize(glm.cross(right, fwd))
        ray_dir = glm.normalize(
            fwd + (ndc_x * half_w) * right + (ndc_y * half_h) * cam_up
        )

        # Amanatides & Woo DDA voxel traversal
        ox, oy, oz = self._cam_pos.x, self._cam_pos.y, self._cam_pos.z
        dx, dy, dz = ray_dir.x, ray_dir.y, ray_dir.z

        ix = int(math.floor(ox))
        iy = int(math.floor(oy))
        iz = int(math.floor(oz))

        def _axis(o, d, i):
            if abs(d) < 1e-10:
                return float('inf'), float('inf'), 0
            s = 1 if d > 0 else -1
            t = ((i + (1 if d > 0 else 0)) - o) / d
            return t, abs(1.0 / d), s

        tx, dtx, sx = _axis(ox, dx, ix)
        ty, dty, sy = _axis(oy, dy, iy)
        tz, dtz, sz = _axis(oz, dz, iz)

        prev_ix, prev_iy, prev_iz = ix, iy, iz
        for _ in range(400):
            if (x_min <= ix <= x_max and
                    y_min <= iy <= y_max and
                    z_min <= iz <= z_max):
                try:
                    block = region[ix, iy, iz]
                    if block.id not in AIR_IDS:
                        return block, (ix, iy, iz), (prev_ix, prev_iy, prev_iz)
                except Exception:
                    pass
            prev_ix, prev_iy, prev_iz = ix, iy, iz
            if tx <= ty and tx <= tz:
                ix += sx; tx += dtx
            elif ty <= tz:
                iy += sy; ty += dty
            else:
                iz += sz; tz += dtz
        return None

    def _on_right_click(self, mx: float, my: float) -> None:
        """Build and show the block context menu at the clicked position."""
        hit = self._cast_ray(mx, my)
        if hit is None:
            return
        block, (bx, by, bz), (px, py, pz) = hit
        props   = dict(block.properties())
        display = block.id.replace("minecraft:", "")
        _bid    = block.id

        menu = QMenu(self)

        replace_one = QAction(f"Replace this block…  ({bx}, {by}, {bz})", self)
        replace_one.triggered.connect(
            lambda checked=False, x=bx, y=by, z=bz: self._prompt_set_block_3d(x, y, z)
        )
        menu.addAction(replace_one)

        menu.addSeparator()

        del_one = QAction(f"Delete this block  ({bx}, {by}, {bz})", self)
        del_one.triggered.connect(
            lambda checked=False, x=bx, y=by, z=bz: self.delete_at_requested.emit(x, y, z)
        )
        menu.addAction(del_one)

        menu.addSeparator()

        rep_all = QAction(f"Replace all '{display}'…", self)
        rep_all.triggered.connect(
            lambda checked=False, b=_bid, p=props: self.replace_requested.emit(b, p)
        )
        menu.addAction(rep_all)

        del_all = QAction(f"Delete all '{display}'…", self)
        del_all.triggered.connect(
            lambda checked=False, b=_bid, p=props: self.delete_requested.emit(b, p)
        )
        menu.addAction(del_all)

        # Offer "place block" on the face just in front of the hit, if it is air
        if (px, py, pz) != (bx, by, bz) and self._schematic:
            region = self._schematic.regions[0].region
            rxs = list(region.xrange())
            rys = list(region.yrange())
            rzs = list(region.zrange())
            if (rxs and rys and rzs and
                    min(rxs) <= px <= max(rxs) and
                    min(rys) <= py <= max(rys) and
                    min(rzs) <= pz <= max(rzs)):
                try:
                    prev_block = region[px, py, pz]
                    if prev_block.id in AIR_IDS:
                        menu.addSeparator()
                        place_act = QAction(
                            f"Place block here…  ({px}, {py}, {pz})", self
                        )
                        place_act.triggered.connect(
                            lambda checked=False, x=px, y=py, z=pz:
                                self._prompt_set_block_3d(x, y, z)
                        )
                        menu.addAction(place_act)
                except Exception:
                    pass

        menu.exec(QCursor.pos())
        # Redraw after menu closes (hover state may have changed)
        self.update()

    def _prompt_set_block_3d(self, x: int, y: int, z: int) -> None:
        """Show autocomplete block-chooser dialog and emit set_block_at."""
        from ui.layer_view import _BlockChooserDialog
        dlg = _BlockChooserDialog(
            title="Place / Replace Block",
            prompt=f"Block ID to place at ({x}, {y}, {z}):",
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        block_id = dlg.block_id()
        if block_id:
            self.set_block_at.emit(x, y, z, block_id)

    # ── GPU buffer management ──────────────────────────────────────────────────

    def _upload_atlas(self, atlas: Atlas) -> None:
        """Upload the texture atlas as a GPU texture.
        Must only be called from initializeGL or paintGL (Qt GL callbacks).
        """
        if self.ctx is None:
            return
        if self._texture is not None:
            self._texture.release()
            self._texture = None
        try:
            rgba = atlas.get_rgba()
            h, w = rgba.shape[:2]
            self._texture = self.ctx.texture((w, h), 4, rgba.tobytes())
            # NEAREST filtering preserves Minecraft's pixel-art look
            self._texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        except Exception as e:
            print(f"[View3D] atlas upload error: {type(e).__name__}: {e}")

    def _on_textures_ready(self) -> None:
        """Called (on main thread) when background downloads finish a batch.
        Refreshes any placeholder slots in the atlas and re-uploads to GPU.
        """
        if self._atlas is None or self.ctx is None or self._texture is None:
            return
        if self._atlas.refresh_textures():
            # Re-upload the full atlas texture with updated pixels
            try:
                rgba = self._atlas.get_rgba()
                h, w = rgba.shape[:2]
                self._texture.write(rgba.tobytes())
                self.update()
            except Exception as e:
                print(f"[View3D] atlas refresh error: {type(e).__name__}: {e}")

    def _upload_mesh(self, data: np.ndarray) -> None:
        """Upload a float32 (N, 8) vertex array to the GPU.
        Columns: x y z  nx ny nz  u v
        Must only be called from initializeGL or paintGL (Qt GL callbacks).
        """
        if self.ctx is None or self.prog is None:
            return

        # Only release VAO/VBO, not the texture
        if self._vao is not None:
            self._vao.release()
            self._vao = None
        if self._vbo is not None:
            self._vbo.release()
            self._vbo = None

        if len(data) == 0:
            self._vertex_count = 0
            return

        try:
            self._vbo = self.ctx.buffer(data.tobytes())
            self._vao = self.ctx.vertex_array(
                self.prog,
                [(self._vbo, '3f 3f 2f', 'in_position', 'in_normal', 'in_uv')],
            )
            self._vertex_count = len(data)
            self._hint.hide()
        except Exception as e:
            print(f"[View3D] mesh upload error: {type(e).__name__}: {e}")

    def _free_buffers(self) -> None:
        if self._vao is not None:
            self._vao.release();          self._vao = None
        if self._vbo is not None:
            self._vbo.release();          self._vbo = None
        if self._texture is not None:
            self._texture.release();      self._texture = None
        if self._highlight_vao is not None:
            self._highlight_vao.release(); self._highlight_vao = None
        if self._highlight_vbo is not None:
            self._highlight_vbo.release(); self._highlight_vbo = None

    def __del__(self):
        try:
            self._free_buffers()
        except Exception:
            pass
