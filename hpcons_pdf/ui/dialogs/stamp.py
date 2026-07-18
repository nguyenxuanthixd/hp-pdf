"""Hop thoai Danh so trang va Watermark / Dong dau."""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                             QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QSlider, QSpinBox,
                             QTabWidget, QVBoxLayout, QWidget)

from ...config import config
from ...core.overlay import (NUMBER_POSITIONS, STAMP_POSITIONS,
                             add_image_stamp, add_page_numbers,
                             add_text_watermark, available_fonts)
from ...utils.fileutils import parse_page_ranges, suffixed_output
from .common import default_out_dir
from .progress import run_task, show_done, show_error


def _range_or_all(text: str, page_count: int):
    text = text.strip()
    if not text:
        return None
    return parse_page_ranges(text, page_count)


class PageNumberDialog(QDialog):
    """Danh so trang: 6 vi tri, font, co chu, dinh dang, so bat dau, pham vi."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("Đánh số trang")
        self.resize(520, 420)
        ncfg = config.get("number")

        lay = QVBoxLayout(self)
        form = QFormLayout()

        self.cb_pos = QComboBox()
        for key, label in NUMBER_POSITIONS:
            self.cb_pos.addItem(label, key)
        idx = next((i for i, (k, _) in enumerate(NUMBER_POSITIONS)
                    if k == ncfg.get("position")), 4)
        self.cb_pos.setCurrentIndex(idx)

        self.cb_font = QComboBox()
        fonts = available_fonts() or ["Arial"]
        self.cb_font.addItems(fonts)
        if ncfg.get("font") in fonts:
            self.cb_font.setCurrentText(ncfg.get("font"))

        self.sp_size = QSpinBox()
        self.sp_size.setRange(6, 72)
        self.sp_size.setValue(int(ncfg.get("size", 11)))

        self.ed_fmt = QLineEdit(ncfg.get("format", "Trang {n}/{total}"))
        self.ed_fmt.setToolTip("{n} = số trang, {total} = tổng số trang")

        self.sp_start = QSpinBox()
        self.sp_start.setRange(1, 99999)
        self.sp_start.setValue(int(ncfg.get("start", 1)))

        self.ed_range = QLineEdit()
        self.ed_range.setPlaceholderText(
            f"Để trống = tất cả ({self.model.page_count} trang). Ví dụ: 2-{self.model.page_count}")

        self.sp_margin = QDoubleSpinBox()
        self.sp_margin.setRange(3, 50)
        self.sp_margin.setValue(float(ncfg.get("margin_mm", 10)))
        self.sp_margin.setSuffix(" mm")

        form.addRow("Vị trí:", self.cb_pos)
        form.addRow("Font chữ:", self.cb_font)
        form.addRow("Cỡ chữ:", self.sp_size)
        form.addRow("Định dạng:", self.ed_fmt)
        form.addRow("Số bắt đầu:", self.sp_start)
        form.addRow("Phạm vi trang:", self.ed_range)
        form.addRow("Cách mép giấy:", self.sp_margin)
        lay.addLayout(form)

        hint = QLabel("Mẹo: dùng {n} cho số trang, {total} cho tổng số. "
                      "Ví dụ: \"Trang {n}/{total}\", \"- {n} -\", \"{n}\"")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #80858A;")
        lay.addWidget(hint)
        lay.addStretch(1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_close = QPushButton("Đóng")
        btn_go = QPushButton("Đánh số và lưu file mới")
        btn_go.setObjectName("primary")
        bottom.addWidget(btn_close)
        bottom.addWidget(btn_go)
        lay.addLayout(bottom)
        btn_close.clicked.connect(self.reject)
        btn_go.clicked.connect(self._apply)

    def _apply(self):
        try:
            indices = _range_or_all(self.ed_range.text(), self.model.page_count)
        except ValueError as e:
            show_error(self, str(e))
            return
        fmt = self.ed_fmt.text().strip() or "Trang {n}/{total}"
        params = dict(
            position=self.cb_pos.currentData(),
            font=self.cb_font.currentText(),
            size=self.sp_size.value(),
            fmt=fmt,
            start=self.sp_start.value(),
            margin_mm=self.sp_margin.value(),
        )
        # Luu cau hinh de dung lai (va cho danh so lien tuc khi ghep)
        config.set("number", {
            "position": params["position"], "font": params["font"],
            "size": params["size"], "format": fmt,
            "start": params["start"], "margin_mm": params["margin_mm"],
        })
        src = self.model.path
        pw = self.model.main_source.password
        dest = suffixed_output(src, "_numbered", out_dir=default_out_dir(src))
        modified = self.model.modified

        def job(progress, cancel):
            return add_page_numbers(src, dest, page_indices=indices,
                                    password=pw, progress=progress,
                                    cancel=cancel, **params)

        status, payload = run_task(self, "Đang đánh số trang...", job)
        if status == "ok":
            note = ("\n\nLưu ý: số trang được đánh trên file GỐC trên đĩa. "
                    "Các chỉnh sửa chưa lưu (xoay/xóa/sắp xếp) không nằm trong "
                    "file này — hãy \"Lưu thành...\" trước nếu muốn giữ chỉnh sửa.") \
                if modified else ""
            show_done(self, f"Đã tạo file:\n{payload}{note}", open_path=payload)
            self.accept()
        elif status == "error":
            show_error(self, payload)


class WatermarkDialog(QDialog):
    """Watermark chu xoay cheo / dong dau anh PNG."""

    def __init__(self, model, current_page: int = 0, parent=None):
        super().__init__(parent)
        self.model = model
        self.current_page = current_page
        self.setWindowTitle("Watermark / Đóng dấu")
        self.resize(560, 500)

        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)

        # ----- Tab chu -----
        tab_text = QWidget()
        ft = QFormLayout(tab_text)
        self.ed_text = QLineEdit(config.get("watermark_text",
                                            "TÀI LIỆU ĐẤU THẦU – HP CONS"))
        self.cb_font = QComboBox()
        fonts = available_fonts() or ["Arial"]
        self.cb_font.addItems(fonts)
        self.sp_tsize = QSpinBox()
        self.sp_tsize.setRange(0, 200)
        self.sp_tsize.setValue(0)
        self.sp_tsize.setSpecialValueText("Tự động")
        self.sl_opacity = QSlider(Qt.Orientation.Horizontal)
        self.sl_opacity.setRange(3, 80)
        self.sl_opacity.setValue(15)
        self.lb_opacity = QLabel("15%")
        self.sl_opacity.valueChanged.connect(
            lambda v: self.lb_opacity.setText(f"{v}%"))
        self.sp_angle = QSpinBox()
        self.sp_angle.setRange(-90, 90)
        self.sp_angle.setValue(45)
        self.sp_angle.setSuffix("°")
        self.ed_trange = QLineEdit()
        self.ed_trange.setPlaceholderText("Để trống = tất cả các trang")
        op_row = QHBoxLayout()
        op_row.addWidget(self.sl_opacity, 1)
        op_row.addWidget(self.lb_opacity)
        ft.addRow("Nội dung:", self.ed_text)
        ft.addRow("Font chữ:", self.cb_font)
        ft.addRow("Cỡ chữ:", self.sp_tsize)
        ft.addRow("Độ đậm:", op_row)
        ft.addRow("Góc xoay:", self.sp_angle)
        ft.addRow("Phạm vi trang:", self.ed_trange)
        self.tabs.addTab(tab_text, "Watermark chữ")

        # ----- Tab anh -----
        tab_img = QWidget()
        fi = QFormLayout(tab_img)
        pick_row = QHBoxLayout()
        self.ed_img = QLineEdit()
        self.ed_img.setPlaceholderText("Chọn file ảnh PNG (nên có nền trong suốt)...")
        btn_pick = QPushButton("Chọn ảnh...")
        btn_pick.clicked.connect(self._pick_image)
        pick_row.addWidget(self.ed_img, 1)
        pick_row.addWidget(btn_pick)
        self.lb_preview = QLabel()
        self.lb_preview.setFixedHeight(90)
        self.lb_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cb_ipos = QComboBox()
        for key, label in STAMP_POSITIONS:
            self.cb_ipos.addItem(label, key)
        self.cb_ipos.setCurrentIndex(8)  # goc duoi phai
        self.sp_iscale = QSpinBox()
        self.sp_iscale.setRange(3, 100)
        self.sp_iscale.setValue(25)
        self.sp_iscale.setSuffix(" % chiều rộng trang")
        self.sl_iopacity = QSlider(Qt.Orientation.Horizontal)
        self.sl_iopacity.setRange(10, 100)
        self.sl_iopacity.setValue(100)
        self.lb_iopacity = QLabel("100%")
        self.sl_iopacity.valueChanged.connect(
            lambda v: self.lb_iopacity.setText(f"{v}%"))
        iop_row = QHBoxLayout()
        iop_row.addWidget(self.sl_iopacity, 1)
        iop_row.addWidget(self.lb_iopacity)
        self.cb_ipages = QComboBox()
        self.cb_ipages.addItems(["Mọi trang", f"Chỉ trang hiện tại (trang {current_page + 1})",
                                 "Khoảng trang..."])
        self.ed_irange = QLineEdit()
        self.ed_irange.setPlaceholderText("Ví dụ: 1, 3-5")
        self.ed_irange.setEnabled(False)
        self.cb_ipages.currentIndexChanged.connect(
            lambda i: self.ed_irange.setEnabled(i == 2))
        fi.addRow("Ảnh con dấu:", pick_row)
        fi.addRow("", self.lb_preview)
        fi.addRow("Vị trí:", self.cb_ipos)
        fi.addRow("Kích thước:", self.sp_iscale)
        fi.addRow("Độ đậm:", iop_row)
        fi.addRow("Áp dụng cho:", self.cb_ipages)
        fi.addRow("", self.ed_irange)
        self.tabs.addTab(tab_img, "Đóng dấu ảnh")

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_close = QPushButton("Đóng")
        btn_go = QPushButton("Áp dụng và lưu file mới")
        btn_go.setObjectName("primary")
        bottom.addWidget(btn_close)
        bottom.addWidget(btn_go)
        lay.addLayout(bottom)
        btn_close.clicked.connect(self.reject)
        btn_go.clicked.connect(self._apply)

    def _pick_image(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn ảnh con dấu", config.get("last_open_dir", ""),
            "Ảnh (*.png *.jpg *.jpeg *.bmp *.webp)")
        if f:
            self.ed_img.setText(f)
            pm = QPixmap(f)
            if not pm.isNull():
                self.lb_preview.setPixmap(pm.scaledToHeight(
                    84, Qt.TransformationMode.SmoothTransformation))

    def _apply(self):
        src = self.model.path
        pw = self.model.main_source.password
        n = self.model.page_count
        if self.tabs.currentIndex() == 0:
            text = self.ed_text.text().strip()
            if not text:
                show_error(self, "Vui lòng nhập nội dung watermark.")
                return
            try:
                indices = _range_or_all(self.ed_trange.text(), n)
            except ValueError as e:
                show_error(self, str(e))
                return
            config.set("watermark_text", text)
            dest = suffixed_output(src, "_watermark", out_dir=default_out_dir(src))
            params = dict(text=text, font=self.cb_font.currentText(),
                          size=self.sp_tsize.value(),
                          opacity=self.sl_opacity.value() / 100.0,
                          angle=float(self.sp_angle.value()))

            def job(progress, cancel):
                return add_text_watermark(src, dest, page_indices=indices,
                                          password=pw, progress=progress,
                                          cancel=cancel, **params)

            title = "Đang chèn watermark..."
        else:
            img = self.ed_img.text().strip()
            if not img or not os.path.exists(img):
                show_error(self, "Vui lòng chọn file ảnh con dấu.")
                return
            mode = self.cb_ipages.currentIndex()
            if mode == 0:
                indices = None
            elif mode == 1:
                indices = [self.current_page]
            else:
                try:
                    indices = _range_or_all(self.ed_irange.text(), n)
                except ValueError as e:
                    show_error(self, str(e))
                    return
                if indices is None:
                    show_error(self, "Vui lòng nhập khoảng trang, ví dụ: 1, 3-5")
                    return
            dest = suffixed_output(src, "_stamped", out_dir=default_out_dir(src))
            params = dict(image_path=img, position=self.cb_ipos.currentData(),
                          scale_percent=float(self.sp_iscale.value()),
                          opacity=self.sl_iopacity.value() / 100.0)

            def job(progress, cancel):
                return add_image_stamp(src, dest, page_indices=indices,
                                       password=pw, progress=progress,
                                       cancel=cancel, **params)

            title = "Đang đóng dấu..."

        status, payload = run_task(self, title, job)
        if status == "ok":
            show_done(self, f"Đã tạo file:\n{payload}", open_path=payload)
            self.accept()
        elif status == "error":
            show_error(self, payload)
