"""
Settings dialog — key remapping, mouse sensitivity, move speed.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QTabWidget, QWidget,
    QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QPushButton,
    QLabel, QSlider, QDoubleSpinBox,
    QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeyEvent, QKeySequence

from core import settings as _cfg

# ── Action labels for display ─────────────────────────────────────────────────
_ACTION_LABELS: dict[str, str] = {
    "forward":  "Fly Forward",
    "backward": "Fly Backward",
    "left":     "Strafe Left",
    "right":    "Strafe Right",
    "up":       "Move Up",
    "down":     "Move Down",
    "reset":    "Reset Camera",
}

_ACTION_ORDER = ["forward", "backward", "left", "right", "up", "down", "reset"]


# ── Key-capture button ─────────────────────────────────────────────────────────

class _KeyCaptureButton(QPushButton):
    """A button that enters 'listening' mode on click and captures the next key."""

    def __init__(self, action: str, parent=None):
        super().__init__(parent)
        self._action = action
        self._listening = False
        self._original_text = ""
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.clicked.connect(self._start_listen)

    def set_key_name(self, name: str) -> None:
        self._original_text = name
        self.setText(name)
        self._listening = False

    def _start_listen(self) -> None:
        self._listening = True
        self.setText("Press a key…")
        self.setStyleSheet("background: #ffcc44; color: black;")
        self.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self._listening:
            super().keyPressEvent(event)
            return
        # Ignore modifier-only keys
        key = event.key()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt,
                   Qt.Key.Key_Meta, Qt.Key.Key_unknown):
            return
        if key == Qt.Key.Key_Escape:
            self.setText(self._original_text)
            self._listening = False
            self.setStyleSheet("")
            return
        # Convert Qt key to a short string like "W", "Space", "Up"
        key_name = QKeySequence(key).toString()
        self._original_text = key_name
        self.setText(key_name)
        self._listening = False
        self.setStyleSheet("")
        # Notify parent table
        parent = self.parent()
        if hasattr(parent, "_on_key_changed"):
            parent._on_key_changed(self._action, key_name)

    def focusOutEvent(self, event) -> None:
        if self._listening:
            self.setText(self._original_text)
            self._listening = False
            self.setStyleSheet("")
        super().focusOutEvent(event)


# ── Controls tab ──────────────────────────────────────────────────────────────

class _ControlsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # ── Key bindings table ──
        layout.addWidget(QLabel("<b>3D Fly Controls</b>"))
        layout.addWidget(QLabel(
            "Click a button then press the desired key.  Press Esc to cancel."
        ))

        self._key_buttons: dict[str, _KeyCaptureButton] = {}
        self._pending: dict[str, str] = {}   # uncommitted changes

        keys = _cfg.get_fly_keys()
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        for action in _ACTION_ORDER:
            label = _ACTION_LABELS.get(action, action.title())
            btn = _KeyCaptureButton(action, self)
            btn.set_key_name(keys.get(action, ""))
            self._key_buttons[action] = btn
            form.addRow(label + ":", btn)
        layout.addLayout(form)

        # Reset to defaults button
        reset_btn = QPushButton("Reset Controls to Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        layout.addWidget(reset_btn)

        layout.addStretch()

        # ── Mouse sensitivity ──
        layout.addWidget(QLabel("<b>Mouse Look Sensitivity</b>"))
        sens_row = QHBoxLayout()
        self._sens_slider = QSlider(Qt.Orientation.Horizontal)
        self._sens_slider.setRange(1, 100)           # 0.01 – 1.00 deg/px
        self._sens_spin  = QDoubleSpinBox()
        self._sens_spin.setRange(0.01, 1.00)
        self._sens_spin.setSingleStep(0.01)
        self._sens_spin.setDecimals(2)
        self._sens_spin.setSuffix(" °/px")
        self._sens_spin.setFixedWidth(90)
        val = _cfg.mouse_sensitivity()
        self._sens_slider.setValue(int(val * 100))
        self._sens_spin.setValue(val)
        self._sens_slider.valueChanged.connect(
            lambda v: self._sens_spin.setValue(v / 100.0))
        self._sens_spin.valueChanged.connect(
            lambda v: self._sens_slider.setValue(int(v * 100)))
        sens_row.addWidget(self._sens_slider, stretch=1)
        sens_row.addWidget(self._sens_spin)
        layout.addLayout(sens_row)

        # ── Default move speed ──
        layout.addWidget(QLabel("<b>Default Fly Speed</b>"))
        speed_row = QHBoxLayout()
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(1, 200)           # 1 – 200 blocks/s
        self._speed_spin  = QDoubleSpinBox()
        self._speed_spin.setRange(1.0, 200.0)
        self._speed_spin.setSingleStep(1.0)
        self._speed_spin.setDecimals(1)
        self._speed_spin.setSuffix(" blk/s")
        self._speed_spin.setFixedWidth(90)
        spd = _cfg.move_speed()
        self._speed_slider.setValue(int(spd))
        self._speed_spin.setValue(spd)
        self._speed_slider.valueChanged.connect(
            lambda v: self._speed_spin.setValue(float(v)))
        self._speed_spin.valueChanged.connect(
            lambda v: self._speed_slider.setValue(int(v)))
        speed_row.addWidget(self._speed_slider, stretch=1)
        speed_row.addWidget(self._speed_spin)
        layout.addLayout(speed_row)

        layout.addStretch()

    # Called by _KeyCaptureButton when a key is recorded
    def _on_key_changed(self, action: str, key_name: str) -> None:
        self._pending[action] = key_name

    def _reset_defaults(self) -> None:
        from core.settings import _DEFAULTS
        defaults = _DEFAULTS["fly_keys"]
        for action, btn in self._key_buttons.items():
            default_key = defaults.get(action, "")
            btn.set_key_name(default_key)
            self._pending[action] = default_key

    def apply(self) -> None:
        """Persist all changes."""
        # Key bindings
        if self._pending:
            keys = _cfg.get_fly_keys()
            keys.update(self._pending)
            _cfg.set_fly_keys(keys)
            self._pending.clear()
        # Sensitivity
        _cfg.set_mouse_sensitivity(self._sens_spin.value())
        # Speed
        _cfg.set_move_speed(self._speed_spin.value())


# ── Main dialog ──────────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    """Application settings dialog.  Call exec(); if accepted, changes are saved."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(440)
        self.setMinimumHeight(460)

        layout = QVBoxLayout(self)

        self._tabs = QTabWidget()
        self._controls_tab = _ControlsTab()
        self._tabs.addTab(self._controls_tab, "Controls")
        layout.addWidget(self._tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Apply,
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)
        layout.addWidget(buttons)

    def _apply(self) -> None:
        self._controls_tab.apply()

    def _accept(self) -> None:
        self._apply()
        self.accept()
