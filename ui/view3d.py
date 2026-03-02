"""
3D OpenGL voxel viewer embedded in a QOpenGLWidget.

Controls:
  Right-drag   — look around (yaw / pitch)
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
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QWheelEvent, QMouseEvent, QKeyEvent, QSurfaceFormat
from core.schematic import LitematicSchematic
from core.mesh_builder import build_mesh
from core.atlas_builder import Atlas
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


# ── Main widget ────────────────────────────────────────────────────────────────

class View3D(QOpenGLWidget):
    """3D voxel renderer embedded in the Qt tab widget."""

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
        self._keys_held: set[Qt.Key] = set()
        self._move_speed = _cfg.move_speed()
        self._velocity = glm.vec3(0.0, 0.0, 0.0)  # for smooth damped movement
        # Key bindings — populated after _hint is created below
        self._fly_keys: dict[str, Qt.Key] = {}

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
            try:
                # QKeySequence("W").toString() == "W"; reverse: parse from string
                seq = QKeySequence.fromString(key_str)
                if not seq.isEmpty():
                    self._fly_keys[action] = Qt.Key(seq[0].key())
            except Exception:
                pass
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
            self._last_mouse_x = event.position().x()
            self._last_mouse_y = event.position().y()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._right_btn_held = False
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
        super().mouseMoveEvent(event)

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
            self._vao.release()
            self._vao = None
        if self._vbo is not None:
            self._vbo.release()
            self._vbo = None
        if self._texture is not None:
            self._texture.release()
            self._texture = None

    def __del__(self):
        try:
            self._free_buffers()
        except Exception:
            pass
