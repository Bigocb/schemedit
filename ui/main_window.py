from __future__ import annotations
import os
from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QFileDialog,
    QMessageBox, QStatusBar, QTabWidget
)
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtCore import Qt
from core.schematic import LitematicSchematic
from core import block_ops
from ui.schematic_panel import SchematicPanel
from ui.palette_panel import PalettePanel
from ui.find_replace import FindReplaceDialog
from ui.layer_view import LayerView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Schemedit — Litematica Schematic Editor")
        self.setMinimumSize(1000, 640)
        self._schematic: LitematicSchematic | None = None
        self._dirty = False

        self._build_menu()
        self._build_central()
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._set_status("Ready. Open a .litematic file to begin.")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("&File")
        open_act = QAction("&Open…", self)
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self._open_file)
        file_menu.addAction(open_act)

        file_menu.addSeparator()

        save_act = QAction("&Save", self)
        save_act.setShortcut(QKeySequence.StandardKey.Save)
        save_act.triggered.connect(self._save_file)
        file_menu.addAction(save_act)

        save_as_act = QAction("Save &As…", self)
        save_as_act.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_act.triggered.connect(self._save_file_as)
        file_menu.addAction(save_as_act)

        file_menu.addSeparator()

        quit_act = QAction("&Quit", self)
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        edit_menu = mb.addMenu("&Edit")
        find_replace_act = QAction("&Find && Replace…", self)
        find_replace_act.setShortcut(QKeySequence("Ctrl+H"))
        find_replace_act.triggered.connect(self._open_find_replace)
        edit_menu.addAction(find_replace_act)

    def _build_central(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._schematic_panel = SchematicPanel()
        self._schematic_panel.setMinimumWidth(240)
        splitter.addWidget(self._schematic_panel)

        # Right side: tab widget containing Palette and Layer View
        self._tabs = QTabWidget()

        self._palette_panel = PalettePanel()
        self._palette_panel.replace_requested.connect(self._open_find_replace_for)
        self._palette_panel.delete_requested.connect(self._delete_block)
        self._tabs.addTab(self._palette_panel, "Palette")

        self._layer_view = LayerView()
        self._layer_view.block_clicked.connect(self._on_layer_block_clicked)
        self._layer_view.replace_requested.connect(self._open_find_replace_for)
        self._layer_view.delete_requested.connect(self._delete_block)
        self._tabs.addTab(self._layer_view, "Layer View")

        self._tabs.setMinimumWidth(380)
        splitter.addWidget(self._tabs)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        self.setCentralWidget(splitter)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _open_file(self) -> None:
        if self._dirty and not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Litematica Schematic", "",
            "Litematica Schematics (*.litematic);;All Files (*)"
        )
        if path:
            self._open_file_path(path)

    def _open_file_path(self, path: str) -> None:
        try:
            self._schematic = LitematicSchematic.load(path)
            self._schematic_panel.load(self._schematic)
            self._palette_panel.load(self._schematic)
            self._layer_view.load(self._schematic)
            self._dirty = False
            self._update_title(path)
            self._set_status(f"Loaded: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error loading file", str(e))

    def _save_file(self) -> None:
        if self._schematic is None:
            return
        if self._schematic.path is None:
            self._save_file_as()
            return
        try:
            self._schematic.save()
            self._dirty = False
            self._update_title(self._schematic.path)
            self._set_status(f"Saved: {os.path.basename(self._schematic.path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error saving file", str(e))

    def _save_file_as(self) -> None:
        if self._schematic is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Schematic As", "",
            "Litematica Schematics (*.litematic);;All Files (*)"
        )
        if not path:
            return
        if not path.endswith(".litematic"):
            path += ".litematic"
        try:
            self._schematic.save(path)
            self._dirty = False
            self._update_title(path)
            self._set_status(f"Saved: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error saving file", str(e))

    # ------------------------------------------------------------------
    # Edit operations
    # ------------------------------------------------------------------

    def _open_find_replace(self) -> None:
        if self._schematic is None:
            QMessageBox.information(self, "No file open", "Open a .litematic file first.")
            return
        self._launch_find_replace()

    def _open_find_replace_for(self, block_id: str, props: dict) -> None:
        if self._schematic is None:
            return
        self._launch_find_replace(prefill_id=block_id, prefill_props=props)

    def _launch_find_replace(self, prefill_id: str = "", prefill_props: dict | None = None) -> None:
        dlg = FindReplaceDialog(
            self._schematic,
            prefill_id=prefill_id,
            prefill_props=prefill_props,
            parent=self,
        )
        if dlg.exec():
            self._refresh_all_panels()
            self._dirty = True
            self._update_title(self._schematic.path)

    def _delete_block(self, block_id: str, props: dict) -> None:
        if self._schematic is None:
            return

        # Count how many blocks will be removed across all regions
        total = sum(
            block_ops.count_block(ri.region, block_id)
            for ri in self._schematic.regions
        )
        if total == 0:
            QMessageBox.information(self, "Delete Blocks", f"No '{block_id}' blocks found.")
            return

        reply = QMessageBox.question(
            self,
            "Delete Blocks",
            f"Delete all {total:,} instance(s) of '{block_id}' (replace with air)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        removed = sum(
            block_ops.find_replace(ri.region, block_id, "minecraft:air")
            for ri in self._schematic.regions
        )
        self._schematic.refresh_regions()
        self._refresh_all_panels()
        self._dirty = True
        self._update_title(self._schematic.path)
        self._set_status(f"Deleted {removed:,} block(s) of '{block_id}'")

    def _on_layer_block_clicked(self, block_id: str, x: int, y: int, z: int) -> None:
        self._set_status(f"Selected: {block_id}  at  ({x}, {y}, {z})")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _refresh_all_panels(self) -> None:
        """Reload schematic panel, palette, and layer view after any edit."""
        self._schematic_panel.load(self._schematic)
        self._palette_panel.load(self._schematic)
        self._layer_view.refresh()

    def _update_title(self, path: str | None) -> None:
        name = os.path.basename(path) if path else "Untitled"
        dirty_mark = " *" if self._dirty else ""
        self.setWindowTitle(f"Schemedit — {name}{dirty_mark}")

    def _set_status(self, msg: str) -> None:
        self._status.showMessage(msg)

    def _confirm_discard(self) -> bool:
        reply = QMessageBox.question(
            self, "Unsaved changes",
            "You have unsaved changes. Discard them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def closeEvent(self, event) -> None:
        if self._dirty and not self._confirm_discard():
            event.ignore()
        else:
            event.accept()
