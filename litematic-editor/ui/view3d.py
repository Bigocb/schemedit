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


# -- GLSL shaders --------------------------------------------------------------

_VERT_SRC = """
#version 330
in vec3 in_position;
in vec3 in_normal;
in vec3 in_color;
uniform mat4 mvp;
out vec3 v_color;
out vec3 v_normal;
void main() {
    gl_Position = mvp * vec4(in_position, 1.0);
    v_color  = in_color;
    v_normal = in_normal;
}
"""

_FRAG_SRC = """
#version 330
in vec3 v_color;
in vec3 v_normal;
out vec4 fragColor;
void main() {
    vec3 light = normalize(vec3(1.0, 2.0, 1.0));
    float d = max(dot(v_normal, light), 0.0);
    fragColor = vec4(v_color * (0.35 + 0.65 * d), 1.0);
}
"""


# -- Main widget ---------------------------------------------------------------

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

        # -- ModernGL objects (set in initializeGL) --
        self.ctx: moderngl.Context | None = None
        self.prog: moderngl.Program | None = None
        self._vbo: moderngl.Buffer | None = None
        self._vao: moderngl.VertexArray | None = None
        self._vertex_count = 0
        self._schematic: LitematicSchematic | None = None
        # Mesh data buffered here if load() is called before initializeGL()
        self._pending_data: np.ndarray | None = None

        # -- Camera --
        self._cam_pos = glm.vec3(8.0, 8.0, 30.0)
        self._yaw   = -90.0   # degrees
        self._pitch = -20.0   # degrees

        # -- Projection --
        self._projection = glm.mat4(1.0)

        # -- Input state --
        self._right_btn_held = False
        self._last_mouse_x = 0
        self._last_mouse_y = 0
        self._keys_held: set[Qt.Key] = set()
        self._move_speed = 10.0   # blocks per second

        # -- Tick timer (fly movement) --
        self._timer = QTimer(self)
        self._timer.setInterval(16)   # ~60 fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

        # -- Hint overlay label --
        self._hint = QLabel(
            "Open a schematic, then click here to move the camera.\n"
            "Right-drag: look  |  WASD: fly  |  Q/E: up/down  |  Scroll: speed",
            self,
        )
        self._hint.setStyleSheet(
            "color: white; background: rgba(0,0,0,160); padding: 6px; font-size: 11px;"
        )
        self._hint.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._hint.adjustSize()

    # -- OpenGL lifecycle ------------------------------------------------------

    def initializeGL(self) -> None:
        try:
            self.ctx = moderngl.create_context()
        except Exception as e:
            print(f"[View3D] Failed to create moderngl context: {e}")
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

        # Upload any mesh data that arrived before the GL context existed
        if self._pending_data is not None:
            self._upload_mesh(self._pending_data)
            self._pending_data = None
            self.update()

    def resizeGL(self, w: int, h: int) -> None:
        if h == 0:
            h = 1
        self._projection = glm.perspective(glm.radians(60.0), w / h, 0.1, 2000.0)
        if self.ctx:
            self.ctx.viewport = (0, 0, w, h)

    def paintGL(self) -> None:
        if self.ctx is None or self.prog is None:
            return

        self.ctx.clear(0.15, 0.17, 0.20)
        self.ctx.enable(moderngl.DEPTH_TEST)

        if self._vao is None or self._vertex_count == 0:
            return

        mvp = self._projection * self._view_matrix()
        self.prog['mvp'].write(bytes(mvp))
        self._vao.render(moderngl.TRIANGLES, self._vertex_count)

    # -- Public API ------------------------------------------------------------

    def load(self, schematic: LitematicSchematic) -> None:
        """Build mesh from schematic and upload to GPU. Reset camera to a good vantage."""
        if not schematic or not schematic.regions:
            self.clear()
            return

        region = schematic.regions[0].region
        data = build_mesh(region)
        self._schematic = schematic

        # Position camera to frame the whole schematic
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
            dist = max(diagonal * 0.8, 20.0)
            self._cam_pos = glm.vec3(cx, cy + diagonal * 0.2, cz + dist)
            self._yaw   = -90.0
            self._pitch = -15.0

        if self.ctx is not None:
            self._upload_mesh(data)
            self.update()
        else:
            self._pending_data = data

    def refresh(self) -> None:
        """Rebuild mesh after edits (keeps camera position)."""
        if self._schematic is not None and self._schematic.regions:
            region = self._schematic.regions[0].region
            data = build_mesh(region)
            if self.ctx is not None:
                self._upload_mesh(data)
                self.update()
            else:
                self._pending_data = data

    def clear(self) -> None:
        """Release GPU buffers."""
        self._free_buffers()
        self._vertex_count = 0
        self.update()

    # -- Camera helpers --------------------------------------------------------

    def _forward(self) -> glm.vec3:
        yaw_r   = math.radians(self._yaw)
        pitch_r = math.radians(self._pitch)
        x = math.cos(pitch_r) * math.cos(yaw_r)
        y = math.sin(pitch_r)
        z = math.cos(pitch_r) * math.sin(yaw_r)
        return glm.normalize(glm.vec3(x, y, z))

    def _right(self) -> glm.vec3:
        return glm.normalize(glm.cross(self._forward(), glm.vec3(0, 1, 0)))

    def _view_matrix(self) -> glm.mat4:
        fwd = self._forward()
        return glm.lookAt(self._cam_pos, self._cam_pos + fwd, glm.vec3(0, 1, 0))

    # -- Tick (movement) -------------------------------------------------------

    def _tick(self) -> None:
        if not self._keys_held:
            return
        dt = 0.016
        speed = self._move_speed * dt
        fwd   = self._forward()
        right = self._right()
        up    = glm.vec3(0, 1, 0)

        if Qt.Key.Key_W in self._keys_held:
            self._cam_pos += fwd   * speed
        if Qt.Key.Key_S in self._keys_held:
            self._cam_pos -= fwd   * speed
        if Qt.Key.Key_A in self._keys_held:
            self._cam_pos -= right * speed
        if Qt.Key.Key_D in self._keys_held:
            self._cam_pos += right * speed
        if Qt.Key.Key_Q in self._keys_held:
            self._cam_pos -= up    * speed
        if Qt.Key.Key_E in self._keys_held:
            self._cam_pos += up    * speed

        self.update()

    # -- Input events ----------------------------------------------------------

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
            self._yaw   += dx * 0.2
            self._pitch -= dy * 0.2
            self._pitch = max(-89.0, min(89.0, self._pitch))
            self.update()
        super().mouseMoveEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.angleDelta().y() > 0:
            self._move_speed = min(self._move_speed * 1.2, 500.0)
        else:
            self._move_speed = max(self._move_speed / 1.2, 0.5)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        self._keys_held.add(Qt.Key(event.key()))
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        self._keys_held.discard(Qt.Key(event.key()))
        super().keyReleaseEvent(event)

    # -- GPU buffer management -------------------------------------------------

    def _upload_mesh(self, data: np.ndarray) -> None:
        """Upload a float32 (N, 9) vertex array to the GPU."""
        self.makeCurrent()
        if self.ctx is None or self.prog is None:
            return

        self._free_buffers()

        if len(data) == 0:
            self._vertex_count = 0
            return

        self._vbo = self.ctx.buffer(data.tobytes())
        self._vao = self.ctx.vertex_array(
            self.prog,
            [(self._vbo, '3f 3f 3f', 'in_position', 'in_normal', 'in_color')],
        )
        self._vertex_count = len(data)
        self._hint.hide()

    def _free_buffers(self) -> None:
        if self._vao is not None:
            self._vao.release()
            self._vao = None
        if self._vbo is not None:
            self._vbo.release()
            self._vbo = None

    def __del__(self):
        try:
            self._free_buffers()
        except Exception:
            pass
