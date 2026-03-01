from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QMenu, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from core.schematic import LitematicSchematic, PaletteEntry


class PalettePanel(QWidget):
    """Right panel: block palette with counts, sorted by frequency."""

    # Emitted when the user requests a find & replace for a specific block
    replace_requested = pyqtSignal(str, dict)  # block_id, properties
    # Emitted when the user requests deletion of all instances of a block
    delete_requested = pyqtSignal(str, dict)   # block_id, properties

    def __init__(self, parent=None):
        super().__init__(parent)
        self._schematic: LitematicSchematic | None = None
        self._all_entries: list[PaletteEntry] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._label = QLabel("Block Palette")
        layout.addWidget(self._label)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter blocks…")
        self._search.textChanged.connect(self._apply_filter)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

        self._count_label = QLabel("")
        layout.addWidget(self._count_label)

    def load(self, schematic: LitematicSchematic) -> None:
        self._schematic = schematic
        self._rebuild_list()

    def clear(self) -> None:
        self._schematic = None
        self._all_entries = []
        self._list.clear()
        self._label.setText("Block Palette")
        self._count_label.setText("")

    def refresh(self) -> None:
        if self._schematic:
            self._schematic.refresh_regions()
            self._rebuild_list()

    def _rebuild_list(self) -> None:
        if self._schematic is None:
            return

        # Merge palette entries across all regions
        merged: dict[tuple, PaletteEntry] = {}
        for region_info in self._schematic.regions:
            for entry in region_info.palette_entries:
                key = (entry.block_id, tuple(sorted(entry.properties.items())))
                if key in merged:
                    merged[key].count += entry.count
                else:
                    merged[key] = PaletteEntry(
                        block_id=entry.block_id,
                        properties=dict(entry.properties),
                        count=entry.count,
                    )

        self._all_entries = sorted(merged.values(), key=lambda e: e.count, reverse=True)
        self._apply_filter(self._search.text())

        total_unique = len(self._all_entries)
        self._label.setText(f"Block Palette ({total_unique} unique types)")

    def _apply_filter(self, text: str) -> None:
        self._list.clear()
        q = text.lower().strip()
        shown = 0
        for entry in self._all_entries:
            if q and q not in entry.display_name.lower():
                continue
            item = QListWidgetItem(f"{entry.display_name}  —  {entry.count:,}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._list.addItem(item)
            shown += 1
        self._count_label.setText(f"Showing {shown} of {len(self._all_entries)}")

    def _show_context_menu(self, pos) -> None:
        item = self._list.itemAt(pos)
        if item is None:
            return
        entry: PaletteEntry = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        replace_action = QAction(f"Replace '{entry.display_name}'…", self)
        replace_action.triggered.connect(lambda: self.replace_requested.emit(
            entry.block_id, entry.properties
        ))
        menu.addAction(replace_action)

        delete_action = QAction(f"Delete all '{entry.display_name}'…", self)
        delete_action.triggered.connect(lambda: self.delete_requested.emit(
            entry.block_id, entry.properties
        ))
        menu.addAction(delete_action)

        menu.exec(self._list.mapToGlobal(pos))

    def _on_double_click(self, item: QListWidgetItem) -> None:
        entry: PaletteEntry = item.data(Qt.ItemDataRole.UserRole)
        self.replace_requested.emit(entry.block_id, entry.properties)
