"""Widget dung chung cho cac hop thoai: chon thu muc xuat, khoang trang..."""
from __future__ import annotations

import os

from PyQt6.QtWidgets import (QFileDialog, QHBoxLayout, QLineEdit, QPushButton,
                             QWidget)

from ...config import config


class FolderPicker(QWidget):
    """O chon thu muc + nut Duyet."""

    def __init__(self, initial: str = "", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(initial)
        self.edit.setPlaceholderText("Thư mục lưu kết quả...")
        btn = QPushButton("Duyệt...")
        btn.clicked.connect(self._browse)
        lay.addWidget(self.edit, 1)
        lay.addWidget(btn)

    def _browse(self):
        start = self.edit.text() or config.get("out_dir") or config.get("last_open_dir")
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu", start or "")
        if d:
            self.edit.setText(d)

    def path(self) -> str:
        return self.edit.text().strip()


def default_out_dir(src_path: str) -> str:
    """Thu muc xuat mac dinh: cau hinh nguoi dung, khong co thi cung cho file goc."""
    cfg = config.get("out_dir", "")
    if cfg and os.path.isdir(cfg):
        return cfg
    return os.path.dirname(src_path)
