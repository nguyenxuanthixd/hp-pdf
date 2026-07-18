"""Hop thoai chon MAY IN + pham vi trang. Sau khi OK, ung dung mo THANG
hop thoai thiet lap goc cua driver may in (giao dien native, day du)."""
from __future__ import annotations

from PyQt6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QRadioButton,
                             QVBoxLayout)

from ...utils.fileutils import parse_page_ranges


class PrintDialog(QDialog):
    def __init__(self, page_count: int, current_page: int,
                 printer_names: list[str], default_name: str,
                 last_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("In tài liệu")
        self.setMinimumWidth(430)
        self.page_count = page_count
        self._current_page = current_page

        lay = QVBoxLayout(self)

        lay.addWidget(QLabel("Máy in:"))
        self.cb_printer = QComboBox()
        self.cb_printer.addItems(printer_names)
        pick = last_name if last_name in printer_names else default_name
        if pick in printer_names:
            self.cb_printer.setCurrentText(pick)
        lay.addWidget(self.cb_printer)

        lay.addSpacing(6)
        lay.addWidget(QLabel("Phạm vi in:"))
        self.rb_all = QRadioButton(f"Tất cả ({page_count} trang)")
        self.rb_cur = QRadioButton(f"Trang hiện tại (trang {current_page + 1})")
        self.rb_range = QRadioButton("Khoảng trang:")
        self.ed_range = QLineEdit()
        self.ed_range.setPlaceholderText("Ví dụ: 1-5, 8, 10-12")
        self.ed_range.setEnabled(False)
        grp = QButtonGroup(self)
        for rb in (self.rb_all, self.rb_cur, self.rb_range):
            grp.addButton(rb)
        self.rb_all.setChecked(True)
        self.rb_range.toggled.connect(self.ed_range.setEnabled)
        self.ed_range.textEdited.connect(
            lambda _t: self.rb_range.setChecked(True))
        lay.addWidget(self.rb_all)
        lay.addWidget(self.rb_cur)
        row = QHBoxLayout()
        row.addWidget(self.rb_range)
        row.addWidget(self.ed_range, 1)
        lay.addLayout(row)

        note = QLabel("Bấm \"Thiết lập & In\" để mở hộp thoại của máy in "
                      "(khổ giấy, 2 mặt, đóng ghim, số bản...) rồi in. "
                      "Thiết lập được ghi nhớ trong khi file còn mở.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#80858A;")
        lay.addSpacing(4)
        lay.addWidget(note)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_cancel = QPushButton("Hủy")
        self.btn_print = QPushButton("Thiết lập & In")
        self.btn_print.setObjectName("primary")
        self.btn_print.setDefault(True)
        bottom.addWidget(btn_cancel)
        bottom.addWidget(self.btn_print)
        lay.addSpacing(6)
        lay.addLayout(bottom)
        btn_cancel.clicked.connect(self.reject)
        self.btn_print.clicked.connect(self._accept)

    def _accept(self):
        try:
            self.page_indices()
        except ValueError as e:
            from .progress import show_error
            show_error(self, str(e))
            return
        self.accept()

    def selected_printer(self) -> str:
        return self.cb_printer.currentText()

    def page_indices(self) -> list[int]:
        if self.rb_cur.isChecked():
            return [self._current_page]
        if self.rb_range.isChecked():
            return parse_page_ranges(self.ed_range.text(), self.page_count)
        return list(range(self.page_count))
