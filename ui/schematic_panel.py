from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QLabel
)
from PyQt6.QtCore import Qt
from core.schematic import LitematicSchematic


class SchematicPanel(QWidget):
    """Left panel: schematic metadata and region tree."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._schematic: LitematicSchematic | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._label = QLabel("No schematic loaded")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Property", "Value"])
        self._tree.setColumnWidth(0, 160)
        layout.addWidget(self._tree)

    def load(self, schematic: LitematicSchematic) -> None:
        self._schematic = schematic
        self._label.setText(f"Schematic: {schematic.name}")
        self._rebuild_tree()

    def clear(self) -> None:
        self._schematic = None
        self._label.setText("No schematic loaded")
        self._tree.clear()

    def _rebuild_tree(self) -> None:
        self._tree.clear()
        s = self._schematic
        if s is None:
            return

        # --- Metadata section ---
        meta_root = QTreeWidgetItem(["Metadata", ""])
        meta_root.setExpanded(True)
        self._tree.addTopLevelItem(meta_root)

        self._add_row(meta_root, "Name", s.name)
        self._add_row(meta_root, "Author", s.author or "(unknown)")
        self._add_row(meta_root, "Description", s.description or "(none)")
        self._add_row(meta_root, "MC Data Version", str(s.mc_version))
        self._add_row(meta_root, "Regions", str(len(s.regions)))

        # --- Regions section ---
        regions_root = QTreeWidgetItem(["Regions", ""])
        regions_root.setExpanded(True)
        self._tree.addTopLevelItem(regions_root)

        for region_info in s.regions:
            w, h, d = region_info.dimensions
            region_item = QTreeWidgetItem([region_info.name, f"{w} × {h} × {d}"])
            region_item.setExpanded(True)
            regions_root.addChild(region_item)

            self._add_row(region_item, "Width (X)", str(w))
            self._add_row(region_item, "Height (Y)", str(h))
            self._add_row(region_item, "Depth (Z)", str(d))
            self._add_row(region_item, "Volume", f"{w * h * d:,}")
            self._add_row(region_item, "Non-air blocks", f"{region_info.total_blocks:,}")
            self._add_row(region_item, "Unique block types", str(len(region_info.palette_entries)))

    @staticmethod
    def _add_row(parent: QTreeWidgetItem, key: str, value: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([key, value])
        parent.addChild(item)
        return item
