from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QSlider, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QSizePolicy, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap, QImage, QPainter, QWheelEvent, QMouseEvent, QCursor, QAction
from core.schematic import LitematicSchematic, RegionInfo

# Pixels per block cell at 1× zoom
CELL_SIZE = 12

# ──────────────────────────────────────────────────────────────────────────────
# Block colour map — common Minecraft blocks
# Unknown blocks get a deterministic colour derived from hash(block_id).
# ──────────────────────────────────────────────────────────────────────────────
_COLOR_MAP: dict[str, tuple[int, int, int]] = {
    "minecraft:air":               (0,   0,   0),    # treated as transparent
    "minecraft:cave_air":          (0,   0,   0),
    "minecraft:void_air":          (0,   0,   0),
    "minecraft:stone":             (128, 128, 128),
    "minecraft:granite":           (167, 107,  82),
    "minecraft:polished_granite":  (180, 120,  90),
    "minecraft:diorite":           (195, 195, 195),
    "minecraft:andesite":          (140, 140, 140),
    "minecraft:grass_block":       (89,  145,  63),
    "minecraft:dirt":              (134,  96,  67),
    "minecraft:coarse_dirt":       (120,  82,  55),
    "minecraft:cobblestone":       (110, 110, 110),
    "minecraft:oak_planks":        (197, 163, 102),
    "minecraft:spruce_planks":     (120,  86,  48),
    "minecraft:birch_planks":      (216, 206, 160),
    "minecraft:jungle_planks":     (160, 115,  72),
    "minecraft:acacia_planks":     (168,  90,  50),
    "minecraft:dark_oak_planks":   ( 66,  43,  20),
    "minecraft:oak_log":           (101,  77,  41),
    "minecraft:spruce_log":        ( 72,  55,  30),
    "minecraft:birch_log":         (216, 206, 160),
    "minecraft:jungle_log":        (148, 108,  57),
    "minecraft:acacia_log":        (168,  90,  50),
    "minecraft:dark_oak_log":      ( 60,  40,  14),
    "minecraft:oak_leaves":        ( 61, 102,  35),
    "minecraft:spruce_leaves":     ( 44,  75,  35),
    "minecraft:birch_leaves":      ( 90, 132,  44),
    "minecraft:jungle_leaves":     ( 40,  93,  24),
    "minecraft:acacia_leaves":     ( 76, 115,  24),
    "minecraft:dark_oak_leaves":   ( 43,  78,  14),
    "minecraft:sand":              (218, 210, 158),
    "minecraft:red_sand":          (189,  93,  38),
    "minecraft:gravel":            (161, 154, 148),
    "minecraft:gold_ore":          (144, 138,  78),
    "minecraft:iron_ore":          (136, 118, 107),
    "minecraft:coal_ore":          ( 85,  85,  85),
    "minecraft:gold_block":        (249, 236,  77),
    "minecraft:iron_block":        (220, 220, 220),
    "minecraft:diamond_block":     ( 99, 219, 213),
    "minecraft:emerald_block":     ( 42, 178,  81),
    "minecraft:glass":             (196, 225, 238),
    "minecraft:water":             ( 63, 118, 228),
    "minecraft:lava":              (228, 102,  18),
    "minecraft:obsidian":          ( 20,  13,  35),
    "minecraft:snow":              (240, 245, 255),
    "minecraft:ice":               (162, 200, 237),
    "minecraft:packed_ice":        (142, 188, 228),
    "minecraft:blue_ice":          ( 96, 167, 230),
    "minecraft:netherrack":        (135,  54,  54),
    "minecraft:nether_bricks":     ( 95,  28,  28),
    "minecraft:soul_sand":         ( 84,  66,  52),
    "minecraft:glowstone":         (225, 186, 104),
    "minecraft:end_stone":         (219, 220, 169),
    "minecraft:purpur_block":      (167, 118, 167),
    "minecraft:white_concrete":    (207, 213, 214),
    "minecraft:orange_concrete":   (224, 101,  20),
    "minecraft:magenta_concrete":  (170,  48, 159),
    "minecraft:light_blue_concrete":(36, 137, 199),
    "minecraft:yellow_concrete":   (240, 175,  21),
    "minecraft:lime_concrete":     ( 94, 168,  24),
    "minecraft:pink_concrete":     (213, 101, 142),
    "minecraft:gray_concrete":     ( 55,  58,  62),
    "minecraft:light_gray_concrete":(125,125,115),
    "minecraft:cyan_concrete":     ( 21, 119, 136),
    "minecraft:purple_concrete":   (100,  32, 156),
    "minecraft:blue_concrete":     ( 45,  47, 143),
    "minecraft:brown_concrete":    ( 96,  60,  32),
    "minecraft:green_concrete":    ( 73,  91,  36),
    "minecraft:red_concrete":      (142,  32,  32),
    "minecraft:black_concrete":    ( 8,   10,  15),
    "minecraft:bricks":            (151,  96,  83),
    "minecraft:stone_bricks":      (118, 118, 118),
    "minecraft:mossy_stone_bricks":(104, 118,  87),
    "minecraft:cracked_stone_bricks":(100,100,100),
    "minecraft:chiseled_stone_bricks":(130,130,130),
}

_AIR_IDS = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}


def _block_color(block_id: str) -> QColor:
    """Return a QColor for a given block ID."""
    if block_id in _AIR_IDS:
        return QColor(0, 0, 0, 0)  # transparent
    if block_id in _COLOR_MAP:
        r, g, b = _COLOR_MAP[block_id]
        return QColor(r, g, b)
    # Deterministic colour for unknown blocks
    h = abs(hash(block_id))
    r = (h & 0xFF0000) >> 16
    g = (h & 0x00FF00) >> 8
    b = (h & 0x0000FF)
    # Avoid very dark colours — boost brightness
    r = max(r, 80)
    g = max(g, 80)
    b = max(b, 80)
    return QColor(r, g, b)


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
    replace_requested = pyqtSignal(str, dict)   # block_id, properties
    delete_requested  = pyqtSignal(str, dict)   # block_id, properties

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
        self._placeholder()

    # ── Public API ─────────────────────────────────────────────────────────────

    def load(self, schematic: LitematicSchematic) -> None:
        self._schematic = schematic
        self._pixmap_cache.clear()
        self._compute_y_range()
        self._render_current()

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
                color = _block_color(block.id)
                if color.alpha() == 0:
                    continue  # leave air as background
                painter.setBrush(color)
                px = xi * CELL_SIZE
                pz = zi * CELL_SIZE
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
        if result:
            block, x, y, z = result
            self.block_clicked.emit(block.id, x, y, z)

    def _on_right_click(self, px: int, pz: int) -> None:
        result = self._resolve_block(px, pz)
        if not result:
            return
        block, x, y, z = result
        if block.id in _AIR_IDS:
            return  # no menu for air

        props = dict(block.properties())
        display = block.id.replace("minecraft:", "")

        menu = QMenu(self)
        replace_act = QAction(f"Replace '{display}'…", self)
        replace_act.triggered.connect(lambda: self.replace_requested.emit(block.id, props))
        menu.addAction(replace_act)

        delete_act = QAction(f"Delete all '{display}'…", self)
        delete_act.triggered.connect(lambda: self.delete_requested.emit(block.id, props))
        menu.addAction(delete_act)

        menu.exec(QCursor.pos())
