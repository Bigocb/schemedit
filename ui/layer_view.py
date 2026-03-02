from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QSlider, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QSizePolicy, QMenu,
    QCheckBox, QLineEdit, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap, QImage, QPainter, QWheelEvent, QMouseEvent, QCursor, QAction
from PyQt6.QtCore import QTimer
from core.schematic import LitematicSchematic, RegionInfo
from core.block_colors import block_qcolor as _block_color, AIR_IDS as _AIR_IDS
from core import texture_cache as _tex

# Pixels per block cell at 1× zoom.
# 16 matches the native Minecraft texture resolution so textures render crisp.
CELL_SIZE = 16


# ──────────────────────────────────────────────────────────────────────────────
# Zoomable graphics view
# ──────────────────────────────────────────────────────────────────────────────

class _SchematicGraphicsView(QGraphicsView):
    """QGraphicsView with mouse-wheel zoom and middle-click pan."""

    block_hovered = pyqtSignal(int, int)   # x, z (scene coords → caller converts)
    block_clicked = pyqtSignal(int, int)   # x, z on left click
    block_right_clicked = pyqtSignal(int, int)

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)
        self._zoom = 1.0

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._zoom *= factor
        self._zoom = max(0.1, min(self._zoom, 20.0))
        self.scale(factor, factor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = self.mapToScene(event.pos())
        x = int(pos.x() // CELL_SIZE)
        z = int(pos.y() // CELL_SIZE)
        self.block_hovered.emit(x, z)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self.mapToScene(event.pos())
            x = int(pos.x() // CELL_SIZE)
            z = int(pos.y() // CELL_SIZE)
            self.block_clicked.emit(x, z)
        elif event.button() == Qt.MouseButton.RightButton:
            pos = self.mapToScene(event.pos())
            x = int(pos.x() // CELL_SIZE)
            z = int(pos.y() // CELL_SIZE)
            self.block_right_clicked.emit(x, z)
        super().mousePressEvent(event)


# ──────────────────────────────────────────────────────────────────────────────
# Main layer view widget
# ──────────────────────────────────────────────────────────────────────────────

class LayerView(QWidget):
    """2D top-down layer viewer for a Litematica schematic."""

    # Emitted when the user left-clicks a block — (block_id, x, y, z)
    block_clicked = pyqtSignal(str, int, int, int)
    # Emitted from the right-click context menu
    replace_requested  = pyqtSignal(str, dict)      # block_id, properties
    delete_requested   = pyqtSignal(str, dict)      # block_id, properties  (all of type)
    delete_at_requested = pyqtSignal(int, int, int) # x, y, z  (single block)
    # Emitted when paint mode places / replaces a single block
    set_block_at = pyqtSignal(int, int, int, str)   # x, y, z, block_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._schematic: LitematicSchematic | None = None
        self._current_y = 0
        self._y_min = 0
        self._y_max = 0
        # Cache: y → QPixmap
        self._pixmap_cache: dict[int, QPixmap] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── Y-level controls ──
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Layer Y:"))

        self._y_spin = QSpinBox()
        self._y_spin.setFixedWidth(70)
        self._y_spin.valueChanged.connect(self._on_y_changed)
        ctrl.addWidget(self._y_spin)

        self._y_slider = QSlider(Qt.Orientation.Horizontal)
        self._y_slider.valueChanged.connect(self._y_spin.setValue)
        self._y_spin.valueChanged.connect(self._y_slider.setValue)
        ctrl.addWidget(self._y_slider, stretch=1)

        self._region_label = QLabel("(no schematic)")
        ctrl.addWidget(self._region_label)
        layout.addLayout(ctrl)

        # ── Paint mode controls ──
        paint_row = QHBoxLayout()
        self._paint_cb = QCheckBox("Paint mode")
        self._paint_cb.setToolTip(
            "Left-click a cell to place the active block.\n"
            "Works on both filled and empty (air) cells."
        )
        paint_row.addWidget(self._paint_cb)
        paint_row.addWidget(QLabel("Block:"))
        self._paint_block_edit = QLineEdit("minecraft:stone")
        self._paint_block_edit.setFixedWidth(220)
        self._paint_block_edit.setPlaceholderText("e.g. minecraft:stone  (namespace optional)")
        paint_row.addWidget(self._paint_block_edit)
        paint_row.addStretch()
        layout.addLayout(paint_row)

        # ── Graphics view ──
        self._scene = QGraphicsScene(self)
        self._view = _SchematicGraphicsView(self._scene, self)
        self._view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._view.block_hovered.connect(self._on_hover)
        self._view.block_clicked.connect(self._on_click)
        self._view.block_right_clicked.connect(self._on_right_click)
        layout.addWidget(self._view, stretch=1)

        # ── Status / hover label ──
        self._hover_label = QLabel("Hover over the grid to inspect blocks")
        self._hover_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self._hover_label)

        self._pixmap_item: QGraphicsPixmapItem | None = None

        # ── Texture refresh (debounced so many parallel downloads fire one repaint) ──
        self._tex_timer = QTimer(self)
        self._tex_timer.setSingleShot(True)
        self._tex_timer.setInterval(120)   # ms — wait for burst to settle
        self._tex_timer.timeout.connect(self._do_texture_refresh)
        _tex._manager.batch_ready.connect(self._on_batch_ready)

        self._placeholder()

    # ── Public API ─────────────────────────────────────────────────────────────

    def load(self, schematic: LitematicSchematic) -> None:
        self._schematic = schematic
        self._pixmap_cache.clear()
        self._compute_y_range()
        self._render_current()
        # Kick off background texture downloads for every unique block type
        self._prefetch_textures()

    def refresh(self) -> None:
        """Call after block edits to invalidate cache and redraw."""
        self._pixmap_cache.clear()
        self._render_current()

    def clear(self) -> None:
        self._schematic = None
        self._pixmap_cache.clear()
        self._scene.clear()
        self._pixmap_item = None
        self._placeholder()

    # ── Internal ───────────────────────────────────────────────────────────────

    # ── Texture helpers ─────────────────────────────────────────────────────────

    def _prefetch_textures(self) -> None:
        """Collect unique block IDs in this schematic and pre-download textures."""
        if not self._schematic:
            return
        seen: set[str] = set()
        for ri in self._schematic.regions:
            for x in ri.region.xrange():
                for y in ri.region.yrange():
                    for z in ri.region.zrange():
                        seen.add(ri.region[x, y, z].id)
        _tex.prefetch(list(seen))

    def _on_batch_ready(self) -> None:
        """Restart the debounce timer each time a texture download batch fires."""
        self._tex_timer.start()

    def _do_texture_refresh(self) -> None:
        """Repaint after the download burst has settled."""
        self._pixmap_cache.clear()
        self._render_current()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _placeholder(self) -> None:
        self._scene.clear()
        self._scene.addText("Open a schematic to view layers")
        self._hover_label.setText("Hover over the grid to inspect blocks")
        self._region_label.setText("(no schematic)")

    def _compute_y_range(self) -> None:
        if not self._schematic or not self._schematic.regions:
            return
        # Use first region for Y range (most schematics have one region)
        ri = self._schematic.regions[0]
        ys = list(ri.region.yrange())
        self._y_min = min(ys)
        self._y_max = max(ys)

        # Block signals while updating ranges
        self._y_spin.blockSignals(True)
        self._y_slider.blockSignals(True)
        self._y_spin.setRange(self._y_min, self._y_max)
        self._y_slider.setRange(self._y_min, self._y_max)
        mid = (self._y_min + self._y_max) // 2
        self._y_spin.setValue(mid)
        self._y_slider.setValue(mid)
        self._current_y = mid
        self._y_spin.blockSignals(False)
        self._y_slider.blockSignals(False)

        w, h, d = ri.dimensions
        self._region_label.setText(f"{ri.name}  {w}×{h}×{d}")

    def _on_y_changed(self, y: int) -> None:
        self._current_y = y
        self._render_current()

    def _render_current(self) -> None:
        if self._schematic is None:
            return
        self._render_layer(self._current_y)

    def _render_layer(self, y: int) -> None:
        if y in self._pixmap_cache:
            self._set_pixmap(self._pixmap_cache[y])
            return

        if not self._schematic or not self._schematic.regions:
            return

        ri: RegionInfo = self._schematic.regions[0]
        xs = list(ri.region.xrange())
        zs = list(ri.region.zrange())

        if not xs or not zs:
            return

        x_min, x_max = min(xs), max(xs)
        z_min, z_max = min(zs), max(zs)
        width = x_max - x_min + 1
        height = z_max - z_min + 1

        img_w = width * CELL_SIZE
        img_h = height * CELL_SIZE

        img = QImage(img_w, img_h, QImage.Format.Format_ARGB32)
        img.fill(QColor(40, 40, 40))  # dark background for air cells

        painter = QPainter(img)
        painter.setPen(Qt.PenStyle.NoPen)

        for xi, x in enumerate(xs):
            for zi, z in enumerate(zs):
                block = ri.region[x, y, z]
                if block.id in _AIR_IDS:
                    continue  # leave air as dark background
                px = xi * CELL_SIZE
                pz = zi * CELL_SIZE
                tex = _tex.get_pixmap(block.id, CELL_SIZE)
                if tex is not None:
                    # Real Minecraft texture — draw pixel-art tile
                    painter.drawPixmap(px, pz, tex)
                else:
                    # Texture not yet downloaded — fall back to solid colour
                    color = _block_color(block.id)
                    if color.alpha() == 0:
                        continue
                    painter.setBrush(color)
                    painter.drawRect(px, pz, CELL_SIZE - 1, CELL_SIZE - 1)

        painter.end()

        pixmap = QPixmap.fromImage(img)
        self._pixmap_cache[y] = pixmap
        self._set_pixmap(pixmap)

    def _set_pixmap(self, pixmap: QPixmap) -> None:
        self._scene.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())

    def _resolve_block(self, px: int, pz: int):
        """Convert pixel-grid coords to (block, x, y, z) or None if out of range."""
        if self._schematic is None:
            return None
        ri = self._schematic.regions[0]
        xs = list(ri.region.xrange())
        zs = list(ri.region.zrange())
        if not (0 <= px < len(xs) and 0 <= pz < len(zs)):
            return None
        x, z, y = xs[px], zs[pz], self._current_y
        try:
            return ri.region[x, y, z], x, y, z
        except Exception:
            return None

    def _on_hover(self, px: int, pz: int) -> None:
        result = self._resolve_block(px, pz)
        if result:
            block, x, y, z = result
            self._hover_label.setText(f"{block.id}  at  ({x}, {y}, {z})")
        else:
            self._hover_label.setText("")

    def _on_click(self, px: int, pz: int) -> None:
        result = self._resolve_block(px, pz)
        if not result:
            return
        block, x, y, z = result
        if self._paint_cb.isChecked():
            block_id = self._paint_block_edit.text().strip()
            if not block_id:
                return
            if ':' not in block_id:
                block_id = 'minecraft:' + block_id
            self.set_block_at.emit(x, y, z, block_id)
            return
        self.block_clicked.emit(block.id, x, y, z)

    def _on_right_click(self, px: int, pz: int) -> None:
        result = self._resolve_block(px, pz)
        if not result:
            return
        block, x, y, z = result
        is_air = block.id in _AIR_IDS

        # Capture coords for lambdas (avoid late-binding issues)
        bx, by, bz = x, y, z

        menu = QMenu(self)

        if is_air:
            place_act = QAction(f"Place block here…  ({bx}, {by}, {bz})", self)
            place_act.triggered.connect(lambda: self._prompt_set_block(bx, by, bz))
            menu.addAction(place_act)
        else:
            props = dict(block.properties())
            display = block.id.replace("minecraft:", "")

            replace_one_act = QAction(f"Replace this block…  ({bx}, {by}, {bz})", self)
            replace_one_act.triggered.connect(lambda: self._prompt_set_block(bx, by, bz))
            menu.addAction(replace_one_act)

            use_as_act = QAction(f"Use as active block  ('{display}')", self)
            _bid = block.id  # capture
            use_as_act.triggered.connect(lambda: self._paint_block_edit.setText(_bid))
            menu.addAction(use_as_act)

            menu.addSeparator()

            delete_one_act = QAction(f"Delete this block  ({bx}, {by}, {bz})", self)
            delete_one_act.triggered.connect(lambda: self.delete_at_requested.emit(bx, by, bz))
            menu.addAction(delete_one_act)

            menu.addSeparator()

            replace_act = QAction(f"Replace all '{display}'…", self)
            replace_act.triggered.connect(lambda: self.replace_requested.emit(block.id, props))
            menu.addAction(replace_act)

            delete_act = QAction(f"Delete all '{display}'…", self)
            delete_act.triggered.connect(lambda: self.delete_requested.emit(block.id, props))
            menu.addAction(delete_act)

        menu.exec(QCursor.pos())

    def _prompt_set_block(self, x: int, y: int, z: int) -> None:
        """Show an input dialog and emit set_block_at with the chosen block ID."""
        default = self._paint_block_edit.text().strip() or "minecraft:stone"
        block_id, ok = QInputDialog.getText(
            self, "Place / Replace Block",
            f"Block ID to place at ({x}, {y}, {z}):",
            text=default,
        )
        if not ok or not block_id.strip():
            return
        block_id = block_id.strip()
        if ':' not in block_id:
            block_id = 'minecraft:' + block_id
        self.set_block_at.emit(x, y, z, block_id)
