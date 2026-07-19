"""Hop thoai in kieu Foxit: chon may in + Thuoc tinh (driver goc), so ban,
in den trang, pham vi trang, ti le (vua le / co that / tuy chinh), huong giay,
kem khung XEM TRUOC co lat trang. In qua GDI giu nguyen thiet lap driver."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog,
                             QDoubleSpinBox, QFrame, QGroupBox, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QRadioButton,
                             QSpinBox, QVBoxLayout, QWidget)

from ...utils.fileutils import parse_page_ranges


class PrintDialog(QDialog):
    def __init__(self, page_count: int, current_page: int,
                 printer_names: list[str], default_name: str,
                 last_name: str, hwnd: int, get_preview, parent=None):
        """get_preview(page_index, max_px) -> QPixmap (de xem truoc)."""
        super().__init__(parent)
        self.setWindowTitle("In tài liệu")
        self.setMinimumSize(820, 560)
        self.page_count = page_count
        self._current_page = current_page
        self._hwnd = hwnd
        self._get_preview = get_preview
        self._devmode = None      # DEVMODE bytes cua may in dang chon
        self._preview_page = current_page

        root = QHBoxLayout(self)

        # ---------------- Cot trai: thiet lap ----------------
        left = QVBoxLayout()
        left.setSpacing(8)

        # -- May in + Thuoc tinh --
        gp_pr = QGroupBox("Máy in")
        v = QVBoxLayout(gp_pr)
        row = QHBoxLayout()
        self.cb_printer = QComboBox()
        self.cb_printer.addItems(printer_names)
        pick = last_name if last_name in printer_names else default_name
        if pick in printer_names:
            self.cb_printer.setCurrentText(pick)
        self.btn_props = QPushButton("Thuộc tính...")
        row.addWidget(self.cb_printer, 1)
        row.addWidget(self.btn_props)
        v.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Số bản:"))
        self.sp_copies = QSpinBox()
        self.sp_copies.setRange(1, 999)
        self.sp_copies.setValue(1)
        row2.addWidget(self.sp_copies)
        row2.addStretch(1)
        self.chk_gray = QCheckBox("In đen trắng (xám)")
        row2.addWidget(self.chk_gray)
        v.addLayout(row2)
        left.addWidget(gp_pr)

        # -- Pham vi in --
        gp_rg = QGroupBox("Phạm vi in")
        vr = QVBoxLayout(gp_rg)
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
        vr.addWidget(self.rb_all)
        vr.addWidget(self.rb_cur)
        rr = QHBoxLayout()
        rr.addWidget(self.rb_range)
        rr.addWidget(self.ed_range, 1)
        vr.addLayout(rr)
        left.addWidget(gp_rg)

        # -- Xu ly khi in: ti le --
        gp_sc = QGroupBox("Tỉ lệ in")
        vs = QVBoxLayout(gp_sc)
        self.rb_fit = QRadioButton("Vừa lề giấy (khuyến nghị)")
        self.rb_actual = QRadioButton("Cỡ thật (100%)")
        self.rb_custom = QRadioButton("Tùy chỉnh:")
        gsc = QButtonGroup(self)
        for rb in (self.rb_fit, self.rb_actual, self.rb_custom):
            gsc.addButton(rb)
        self.rb_fit.setChecked(True)
        self.sp_pct = QDoubleSpinBox()
        self.sp_pct.setRange(10.0, 400.0)
        self.sp_pct.setValue(100.0)
        self.sp_pct.setSuffix(" %")
        self.sp_pct.setEnabled(False)
        self.rb_custom.toggled.connect(self.sp_pct.setEnabled)
        vs.addWidget(self.rb_fit)
        vs.addWidget(self.rb_actual)
        rc = QHBoxLayout()
        rc.addWidget(self.rb_custom)
        rc.addWidget(self.sp_pct)
        rc.addStretch(1)
        vs.addLayout(rc)
        left.addWidget(gp_sc)

        # -- Huong giay --
        gp_or = QGroupBox("Hướng giấy")
        vo = QHBoxLayout(gp_or)
        self.rb_auto = QRadioButton("Tự động")
        self.rb_port = QRadioButton("Dọc")
        self.rb_land = QRadioButton("Ngang")
        gor = QButtonGroup(self)
        for rb in (self.rb_auto, self.rb_port, self.rb_land):
            gor.addButton(rb)
            vo.addWidget(rb)
        self.rb_auto.setChecked(True)
        left.addWidget(gp_or)

        left.addStretch(1)

        # -- Nut duoi --
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_cancel = QPushButton("Hủy")
        self.btn_print = QPushButton("In")
        self.btn_print.setObjectName("primary")
        self.btn_print.setDefault(True)
        bottom.addWidget(btn_cancel)
        bottom.addWidget(self.btn_print)
        left.addLayout(bottom)

        left_w = QWidget()
        left_w.setLayout(left)
        left_w.setMaximumWidth(380)
        root.addWidget(left_w)

        # ---------------- Cot phai: xem truoc ----------------
        right = QVBoxLayout()
        self.lb_preview = QLabel("Đang tải xem trước...")
        self.lb_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lb_preview.setFrameShape(QFrame.Shape.StyledPanel)
        self.lb_preview.setStyleSheet(
            "background:#3A3D41; border:1px solid #55585C;")
        self.lb_preview.setMinimumSize(360, 440)
        right.addWidget(self.lb_preview, 1)

        nav = QHBoxLayout()
        self.btn_prev = QPushButton("‹ Trước")
        self.btn_next = QPushButton("Sau ›")
        self.lb_pageno = QLabel()
        self.lb_pageno.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self.btn_prev)
        nav.addWidget(self.lb_pageno, 1)
        nav.addWidget(self.btn_next)
        right.addLayout(nav)
        root.addLayout(right, 1)

        # ---------------- Ket noi ----------------
        btn_cancel.clicked.connect(self.reject)
        self.btn_print.clicked.connect(self._accept)
        self.btn_props.clicked.connect(self._open_properties)
        self.cb_printer.currentTextChanged.connect(self._printer_changed)
        self.btn_prev.clicked.connect(lambda: self._step(-1))
        self.btn_next.clicked.connect(lambda: self._step(1))
        for rb in (self.rb_all, self.rb_cur, self.rb_range):
            rb.toggled.connect(self._sync_preview_to_range)

        self._load_devmode(self.cb_printer.currentText())
        self._refresh_preview()

    # ---------------- Xem truoc ----------------
    def _step(self, d: int):
        self._preview_page = max(0, min(self.page_count - 1,
                                        self._preview_page + d))
        self._refresh_preview()

    def _sync_preview_to_range(self):
        if self.rb_cur.isChecked():
            self._preview_page = self._current_page
            self._refresh_preview()

    def _refresh_preview(self):
        self.btn_prev.setEnabled(self._preview_page > 0)
        self.btn_next.setEnabled(self._preview_page < self.page_count - 1)
        self.lb_pageno.setText(
            f"Trang {self._preview_page + 1} / {self.page_count}")
        try:
            box = self.lb_preview.size()
            mx = max(240, min(box.width(), box.height()) + 120)
            pm = self._get_preview(self._preview_page, mx)
        except Exception:
            pm = None
        if pm and not pm.isNull():
            scaled = pm.scaled(self.lb_preview.size(),
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
            self.lb_preview.setPixmap(scaled)
        else:
            self.lb_preview.setText("(Không xem trước được)")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._refresh_preview()

    # ---------------- May in / driver ----------------
    def _load_devmode(self, name: str):
        from ...core import winprint
        try:
            self._devmode = winprint.get_default_devmode(name)
        except Exception:
            self._devmode = None

    def _printer_changed(self, name: str):
        self._load_devmode(name)

    def _open_properties(self):
        from ...core import winprint
        name = self.cb_printer.currentText()
        try:
            dm = winprint.prompt_devmode(name, self._hwnd, self._devmode)
        except Exception:
            dm = winprint.UNAVAILABLE
        if dm is winprint.CANCELLED or dm is winprint.UNAVAILABLE:
            return
        self._devmode = dm

    # ---------------- Ket qua ----------------
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

    def devmode_bytes(self):
        return self._devmode

    def copies(self) -> int:
        return self.sp_copies.value()

    def grayscale(self) -> bool:
        return self.chk_gray.isChecked()

    def orientation(self) -> str:
        if self.rb_port.isChecked():
            return "portrait"
        if self.rb_land.isChecked():
            return "landscape"
        return "auto"

    def scale_mode(self) -> str:
        if self.rb_actual.isChecked():
            return "actual"
        if self.rb_custom.isChecked():
            return "custom"
        return "fit"

    def custom_percent(self) -> float:
        return self.sp_pct.value()

    def page_indices(self) -> list[int]:
        if self.rb_cur.isChecked():
            return [self._current_page]
        if self.rb_range.isChecked():
            return parse_page_ranges(self.ed_range.text(), self.page_count)
        return list(range(self.page_count))
