"""Hop thoai Them/Sua chu: noi dung + phong chu + co (chieu cao) + mau chu
+ mau nen."""
from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog,
                             QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                             QSpinBox, QVBoxLayout)

from ...core.overlay import available_fonts


class _ColorButton(QPushButton):
    """Nut hien mau, bam de chon mau."""

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = color or "#000000"
        self.setFixedSize(52, 24)
        self.clicked.connect(self._pick)
        self._refresh()

    def _refresh(self):
        self.setStyleSheet(
            f"background:{self._color}; border:1px solid #888; border-radius:3px;")

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._color), self, "Chọn màu")
        if c.isValid():
            self._color = c.name()
            self._refresh()

    def color(self) -> str:
        return self._color


class TextAnnotDialog(QDialog):
    def __init__(self, parent=None, *, title="Thêm chữ", text="",
                 font="Arial", size=14, color="#E53935", bg=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel("Nội dung (Enter để xuống dòng):"))
        self.ed = QPlainTextEdit(text)
        self.ed.setMinimumHeight(90)
        lay.addWidget(self.ed)

        # Phong chu + co chu
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Phông chữ:"))
        self.cb_font = QComboBox()
        fonts = available_fonts() or ["Arial"]
        self.cb_font.addItems(fonts)
        if font in fonts:
            self.cb_font.setCurrentText(font)
        r1.addWidget(self.cb_font, 1)
        r1.addWidget(QLabel("Cỡ chữ:"))
        self.sp = QSpinBox()
        self.sp.setRange(6, 400)
        self.sp.setValue(int(size))
        self.sp.setSuffix(" pt")
        r1.addWidget(self.sp)
        lay.addLayout(r1)

        # Mau chu + mau nen
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Màu chữ:"))
        self.btn_color = _ColorButton(color)
        r2.addWidget(self.btn_color)
        r2.addSpacing(18)
        self.chk_bg = QCheckBox("Màu nền:")
        self.chk_bg.setChecked(bool(bg))
        r2.addWidget(self.chk_bg)
        self.btn_bg = _ColorButton(bg or "#FFF59D")
        self.btn_bg.setEnabled(bool(bg))
        self.chk_bg.toggled.connect(self.btn_bg.setEnabled)
        r2.addWidget(self.btn_bg)
        r2.addStretch(1)
        lay.addLayout(r2)

        # Nut
        rb = QHBoxLayout()
        rb.addStretch(1)
        btn_cancel = QPushButton("Hủy")
        btn_ok = QPushButton("OK")
        btn_ok.setObjectName("primary")
        btn_ok.setDefault(True)
        rb.addWidget(btn_cancel)
        rb.addWidget(btn_ok)
        lay.addSpacing(4)
        lay.addLayout(rb)
        btn_cancel.clicked.connect(self.reject)
        btn_ok.clicked.connect(self.accept)

    def values(self) -> dict:
        return {
            "text": self.ed.toPlainText().strip(),
            "font": self.cb_font.currentText(),
            "size": float(self.sp.value()),
            "color": self.btn_color.color(),
            "bg": self.btn_bg.color() if self.chk_bg.isChecked() else "",
        }
