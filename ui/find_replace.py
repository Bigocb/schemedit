from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QLineEdit, QPushButton, QDialogButtonBox,
    QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt
from core.schematic import LitematicSchematic, RegionInfo
from core import block_ops


class FindReplaceDialog(QDialog):
    """Modal dialog for finding and replacing blocks in a schematic."""

    def __init__(
        self,
        schematic: LitematicSchematic,
        prefill_id: str = "",
        prefill_props: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Find & Replace Blocks")
        self.setMinimumWidth(420)
        self._schematic = schematic
        self._prefill_id = prefill_id
        self._prefill_props = prefill_props or {}

        layout = QVBoxLayout(self)

        # --- Find section ---
        find_group = QGroupBox("Find block")
        find_layout = QVBoxLayout(find_group)

        self._find_combo = QComboBox()
        self._find_combo.setEditable(True)
        self._find_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._populate_find_combo()
        find_layout.addWidget(self._find_combo)
        layout.addWidget(find_group)

        # --- Replace section ---
        replace_group = QGroupBox("Replace with")
        replace_layout = QVBoxLayout(replace_group)

        self._replace_edit = QLineEdit()
        self._replace_edit.setPlaceholderText("e.g. minecraft:stone or stone")
        replace_layout.addWidget(self._replace_edit)

        hint = QLabel("Tip: Use full ID like 'minecraft:oak_planks' or just 'oak_planks'")
        hint.setStyleSheet("color: gray; font-size: 10px;")
        replace_layout.addWidget(hint)
        layout.addWidget(replace_group)

        # --- Scope section ---
        scope_group = QGroupBox("Scope")
        scope_layout = QHBoxLayout(scope_group)
        scope_layout.addWidget(QLabel("Apply to:"))
        self._scope_combo = QComboBox()
        self._scope_combo.addItem("All regions", userData=None)
        for ri in schematic.regions:
            self._scope_combo.addItem(ri.name, userData=ri)
        scope_layout.addWidget(self._scope_combo)
        layout.addWidget(scope_group)

        # --- Preview label ---
        self._preview_label = QLabel("")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._preview_label)
        self._find_combo.currentTextChanged.connect(self._update_preview)
        self._scope_combo.currentIndexChanged.connect(self._update_preview)

        # --- Buttons ---
        buttons = QDialogButtonBox()
        self._replace_btn = QPushButton("Replace")
        self._replace_btn.setDefault(True)
        buttons.addButton(self._replace_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        self._replace_btn.clicked.connect(self._do_replace)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

        self._update_preview()

    def _populate_find_combo(self) -> None:
        seen = set()
        for ri in self._schematic.regions:
            for entry in ri.palette_entries:
                if entry.block_id not in seen:
                    seen.add(entry.block_id)
                    label = entry.display_name
                    self._find_combo.addItem(label, userData=(entry.block_id, entry.properties))

        # Pre-select if we were given a block
        if self._prefill_id:
            for i in range(self._find_combo.count()):
                data = self._find_combo.itemData(i)
                if data and data[0] == self._prefill_id:
                    self._find_combo.setCurrentIndex(i)
                    break

    def _get_find_id(self) -> str:
        data = self._find_combo.currentData()
        if data:
            return data[0]
        # User typed a custom value
        text = self._find_combo.currentText().strip()
        if ":" not in text:
            return f"minecraft:{text}"
        return text

    def _get_replace_id(self) -> str:
        text = self._replace_edit.text().strip()
        if not text:
            return ""
        if ":" not in text:
            return f"minecraft:{text}"
        return text

    def _get_target_regions(self) -> list[RegionInfo]:
        scope_data = self._scope_combo.currentData()
        if scope_data is None:
            return self._schematic.regions
        return [scope_data]

    def _count_affected(self) -> int:
        find_id = self._get_find_id()
        total = 0
        for ri in self._get_target_regions():
            total += block_ops.count_block(ri.region, find_id)
        return total

    def _update_preview(self) -> None:
        try:
            count = self._count_affected()
            self._preview_label.setText(f"{count:,} block(s) will be affected")
        except Exception:
            self._preview_label.setText("")

    def _do_replace(self) -> None:
        find_id = self._get_find_id()
        replace_id = self._get_replace_id()

        if not find_id:
            QMessageBox.warning(self, "Error", "Please specify a block to find.")
            return
        if not replace_id:
            QMessageBox.warning(self, "Error", "Please specify a replacement block.")
            return

        total_changed = 0
        for ri in self._get_target_regions():
            total_changed += block_ops.find_replace(ri.region, find_id, replace_id)

        self._schematic.refresh_regions()
        self.accept()
        QMessageBox.information(
            self.parent(),
            "Replace Complete",
            f"Replaced {total_changed:,} block(s) of '{find_id}' with '{replace_id}'.",
        )
