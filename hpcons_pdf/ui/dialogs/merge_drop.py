"""Hop thoai chon vi tri gop khi keo-tha file PDF vao thanh thumbnail."""
from __future__ import annotations

import os

from PyQt6.QtWidgets import (QButtonGroup, QDialog, QHBoxLayout, QLabel,
                             QPushButton, QRadioButton, QSpinBox, QVBoxLayout)


class MergeDropDialog(QDialog):
    """Hoi vi tri chen cac file PDF vua tha vao tai lieu dang mo."""

    def __init__(self, files: list[str], page_count: int, drop_row: int,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gộp file vào tài liệu")
        self.setMinimumWidth(420)
        self.page_count = page_count
        lay = QVBoxLayout(self)

        names = "\n".join("• " + os.path.basename(f) for f in files[:6])
        if len(files) > 6:
            names += f"\n... và {len(files) - 6} file khác"
        lay.addWidget(QLabel(
            f"Gộp {len(files)} file PDF vào tài liệu đang mở:\n{names}\n\n"
            "Chọn vị trí chèn:"))

        self.group = QButtonGroup(self)
        self.rb_drop = None
        if 0 <= drop_row < page_count:
            self.rb_drop = QRadioButton(
                f"Tại vị trí thả — trước trang {drop_row + 1}")
            self.group.addButton(self.rb_drop)
            lay.addWidget(self.rb_drop)
        self.rb_start = QRadioButton("Đầu tài liệu")
        self.rb_end = QRadioButton("Cuối tài liệu")
        self.rb_at = QRadioButton("Trước trang số:")
        self.sp_at = QSpinBox()
        self.sp_at.setRange(1, max(1, page_count))
        self.sp_at.setValue(min(max(drop_row + 1, 1), page_count))
        for rb in (self.rb_start, self.rb_end, self.rb_at):
            self.group.addButton(rb)
        lay.addWidget(self.rb_start)
        lay.addWidget(self.rb_end)
        row = QHBoxLayout()
        row.addWidget(self.rb_at)
        row.addWidget(self.sp_at)
        row.addStretch(1)
        lay.addLayout(row)
        (self.rb_drop or self.rb_end).setChecked(True)
        self.sp_at.valueChanged.connect(lambda _: self.rb_at.setChecked(True))

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_cancel = QPushButton("Hủy")
        btn_ok = QPushButton("Gộp vào")
        btn_ok.setObjectName("primary")
        bottom.addWidget(btn_cancel)
        bottom.addWidget(btn_ok)
        lay.addLayout(bottom)
        btn_cancel.clicked.connect(self.reject)
        btn_ok.clicked.connect(self.accept)
        self._drop_row = drop_row

    def insert_at(self) -> int:
        """Vi tri chen 0-based."""
        if self.rb_drop is not None and self.rb_drop.isChecked():
            return self._drop_row
        if self.rb_start.isChecked():
            return 0
        if self.rb_at.isChecked():
            return self.sp_at.value() - 1
        return self.page_count
