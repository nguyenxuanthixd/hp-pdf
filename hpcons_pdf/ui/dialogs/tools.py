"""Hop thoai OCR, Chuyen doi, Nen, Bao mat, Chen trang."""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox,
                             QComboBox, QDialog, QFileDialog, QFormLayout,
                             QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QPushButton, QRadioButton,
                             QSpinBox, QTabWidget, QVBoxLayout, QWidget)

from ...config import config
from ...core import convert, security
from ...core.compress import COMPRESS_LEVELS, compress_pdf
from ...core.ocr import OCR_LANG_LABELS, find_tesseract, ocr_pdf
from ...utils.fileutils import human_size, parse_page_ranges, suffixed_output
from .common import FolderPicker, default_out_dir
from .progress import run_task, show_done, show_error


def _range_or_all(text: str, page_count: int):
    text = text.strip()
    if not text:
        return None
    return parse_page_ranges(text, page_count)


class OcrDialog(QDialog):
    """OCR PDF scan -> PDF searchable."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("OCR — Nhận diện chữ (PDF scan → PDF tìm kiếm được)")
        self.resize(560, 430)

        lay = QVBoxLayout(self)
        info = QLabel(
            "Chức năng này dành cho PDF scan (ảnh chụp). Mỗi trang sẽ được "
            "nhận diện chữ và tạo lại thành trang có lớp chữ ẩn bên dưới ảnh — "
            "cho phép tìm kiếm và copy nội dung.")
        info.setWordWrap(True)
        lay.addWidget(info)

        form = QFormLayout()
        lang_row = QVBoxLayout()
        self.lang_checks: dict[str, QCheckBox] = {}
        saved = config.get("ocr_langs", ["vie", "eng"])
        for code, label in OCR_LANG_LABELS:
            cb = QCheckBox(f"{label} ({code})")
            cb.setChecked(code in saved)
            self.lang_checks[code] = cb
            lang_row.addWidget(cb)
        form.addRow("Ngôn ngữ:", lang_row)

        self.cb_dpi = QComboBox()
        for d in (200, 300, 400):
            self.cb_dpi.addItem(f"{d} DPI" + ("  (khuyên dùng)" if d == 300 else ""), d)
        idx = {200: 0, 300: 1, 400: 2}.get(int(config.get("ocr_dpi", 300)), 1)
        self.cb_dpi.setCurrentIndex(idx)
        form.addRow("Độ phân giải:", self.cb_dpi)

        self.ed_range = QLineEdit()
        self.ed_range.setPlaceholderText(
            f"Để trống = tất cả ({model.page_count} trang)")
        form.addRow("Phạm vi trang:", self.ed_range)
        lay.addLayout(form)

        # Trang thai Tesseract
        tess_row = QHBoxLayout()
        path = find_tesseract()
        self.lb_tess = QLabel()
        self.lb_tess.setWordWrap(True)
        self._set_tess_label(path)
        btn_tess = QPushButton("Chọn tesseract.exe...")
        btn_tess.clicked.connect(self._pick_tesseract)
        tess_row.addWidget(self.lb_tess, 1)
        tess_row.addWidget(btn_tess)
        lay.addLayout(tess_row)
        lay.addStretch(1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_close = QPushButton("Đóng")
        btn_go = QPushButton("Bắt đầu OCR")
        btn_go.setObjectName("primary")
        bottom.addWidget(btn_close)
        bottom.addWidget(btn_go)
        lay.addLayout(bottom)
        btn_close.clicked.connect(self.reject)
        btn_go.clicked.connect(self._run)

    def _set_tess_label(self, path):
        if path:
            self.lb_tess.setText(f"✓ Đã tìm thấy Tesseract: {path}")
            self.lb_tess.setStyleSheet("color: #5FBF2D;")
        else:
            self.lb_tess.setText(
                "✗ Chưa tìm thấy Tesseract OCR — xem hướng dẫn cài đặt trong README.md")
            self.lb_tess.setStyleSheet("color: #C0392B;")

    def _pick_tesseract(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn file tesseract.exe", r"C:\Program Files",
            "tesseract.exe (tesseract.exe);;File chạy (*.exe)")
        if f:
            config.set("tesseract_path", f)
            self._set_tess_label(f)

    def _run(self):
        langs = [c for c, cb in self.lang_checks.items() if cb.isChecked()]
        if not langs:
            show_error(self, "Vui lòng chọn ít nhất một ngôn ngữ OCR.")
            return
        try:
            indices = _range_or_all(self.ed_range.text(), self.model.page_count)
        except ValueError as e:
            show_error(self, str(e))
            return
        dpi = self.cb_dpi.currentData()
        config.set("ocr_langs", langs)
        config.set("ocr_dpi", dpi)
        model = self.model
        dest = suffixed_output(model.path, "_ocr", out_dir=default_out_dir(model.path))

        def job(progress, cancel):
            return ocr_pdf(model, dest, langs=langs, dpi=dpi,
                           page_indices=indices, progress=progress, cancel=cancel)

        status, payload = run_task(self, "Đang OCR — việc này có thể mất vài phút...", job)
        if status == "ok":
            show_done(self, f"Đã tạo PDF tìm kiếm được:\n{payload}", open_path=payload)
            self.accept()
        elif status == "error":
            show_error(self, payload)


class ConvertDialog(QDialog):
    """Chuyen doi: PDF -> anh / anh -> PDF / PDF -> text."""

    def __init__(self, model=None, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("Chuyển đổi")
        self.resize(600, 480)
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)

        # ----- PDF -> anh -----
        tab1 = QWidget()
        f1 = QFormLayout(tab1)
        self.cb_fmt = QComboBox()
        self.cb_fmt.addItems(["PNG", "JPG"])
        self.cb_dpi = QComboBox()
        for d in (100, 150, 200, 300, 600):
            self.cb_dpi.addItem(f"{d} DPI", d)
        self.cb_dpi.setCurrentIndex(2)
        self.ed_prange = QLineEdit()
        self.ed_prange.setPlaceholderText("Để trống = tất cả các trang")
        self.folder_img = FolderPicker(
            default_out_dir(model.path) if model else config.get("out_dir", ""))
        f1.addRow("Định dạng ảnh:", self.cb_fmt)
        f1.addRow("Độ phân giải:", self.cb_dpi)
        f1.addRow("Phạm vi trang:", self.ed_prange)
        f1.addRow("Lưu vào thư mục:", self.folder_img)
        if model is None:
            f1.addRow(QLabel("(Mở một file PDF trước để dùng chức năng này)"))
        self.tabs.addTab(tab1, "PDF → Ảnh")

        # ----- anh -> PDF -----
        tab2 = QWidget()
        v2 = QVBoxLayout(tab2)
        v2.addWidget(QLabel("Danh sách ảnh (kéo-thả để sắp thứ tự):"))
        self.img_list = QListWidget()
        self.img_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.img_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        v2.addWidget(self.img_list, 1)
        row2 = QHBoxLayout()
        btn_addimg = QPushButton("Thêm ảnh...")
        btn_delimg = QPushButton("Bỏ khỏi danh sách")
        row2.addWidget(btn_addimg)
        row2.addWidget(btn_delimg)
        row2.addStretch(1)
        v2.addLayout(row2)
        self.cb_pagemode = QComboBox()
        self.cb_pagemode.addItem("Kích thước trang theo ảnh", "image")
        self.cb_pagemode.addItem("Trang A4 dọc (ảnh căn giữa)", "a4-portrait")
        self.cb_pagemode.addItem("Trang A4 ngang (ảnh căn giữa)", "a4-landscape")
        v2.addWidget(self.cb_pagemode)
        btn_addimg.clicked.connect(self._add_images)
        btn_delimg.clicked.connect(self._remove_images)
        self.tabs.addTab(tab2, "Ảnh → PDF")

        # ----- PDF -> text -----
        tab3 = QWidget()
        f3 = QFormLayout(tab3)
        self.ed_trange = QLineEdit()
        self.ed_trange.setPlaceholderText("Để trống = tất cả các trang")
        f3.addRow("Phạm vi trang:", self.ed_trange)
        note = QLabel("Chỉ trích được chữ từ PDF có lớp text. Với PDF scan, "
                      "hãy chạy OCR trước.")
        note.setWordWrap(True)
        f3.addRow(note)
        self.tabs.addTab(tab3, "PDF → Text")

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_close = QPushButton("Đóng")
        self.btn_go = QPushButton("Chuyển đổi")
        self.btn_go.setObjectName("primary")
        bottom.addWidget(btn_close)
        bottom.addWidget(self.btn_go)
        lay.addLayout(bottom)
        btn_close.clicked.connect(self.reject)
        self.btn_go.clicked.connect(self._run)

    def _add_images(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn ảnh", config.get("last_open_dir", ""),
            "Ảnh (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)")
        for f in files:
            it = QListWidgetItem(os.path.basename(f))
            it.setData(Qt.ItemDataRole.UserRole, f)
            it.setToolTip(f)
            self.img_list.addItem(it)
        if files:
            config.set("last_open_dir", os.path.dirname(files[0]))

    def _remove_images(self):
        for it in self.img_list.selectedItems():
            self.img_list.takeItem(self.img_list.row(it))

    def _run(self):
        tab = self.tabs.currentIndex()
        if tab == 0:
            if self.model is None:
                show_error(self, "Hãy mở một file PDF trước.")
                return
            try:
                indices = _range_or_all(self.ed_prange.text(), self.model.page_count)
            except ValueError as e:
                show_error(self, str(e))
                return
            fmt = self.cb_fmt.currentText()
            dpi = self.cb_dpi.currentData()
            out_dir = self.folder_img.path() or default_out_dir(self.model.path)
            model = self.model

            def job(progress, cancel):
                return convert.pdf_to_images(model, out_dir, fmt=fmt, dpi=dpi,
                                             page_indices=indices,
                                             progress=progress, cancel=cancel)

            status, payload = run_task(self, "Đang xuất trang thành ảnh...", job)
            if status == "ok":
                show_done(self, f"Đã xuất {len(payload)} ảnh vào:\n{out_dir}",
                          open_path=payload[0] if payload else out_dir)
                self.accept()
            elif status == "error":
                show_error(self, payload)

        elif tab == 1:
            paths = [self.img_list.item(i).data(Qt.ItemDataRole.UserRole)
                     for i in range(self.img_list.count())]
            if not paths:
                show_error(self, "Vui lòng thêm ít nhất 1 ảnh.")
                return
            dest, _ = QFileDialog.getSaveFileName(
                self, "Lưu file PDF",
                os.path.join(os.path.dirname(paths[0]),
                             os.path.splitext(os.path.basename(paths[0]))[0] + ".pdf"),
                "File PDF (*.pdf)")
            if not dest:
                return
            mode = self.cb_pagemode.currentData()

            def job(progress, cancel):
                return convert.images_to_pdf(paths, dest, page_mode=mode,
                                             progress=progress, cancel=cancel)

            status, payload = run_task(self, "Đang tạo PDF từ ảnh...", job)
            if status == "ok":
                show_done(self, f"Đã tạo file:\n{payload}", open_path=payload)
                self.accept()
            elif status == "error":
                show_error(self, payload)

        else:
            if self.model is None:
                show_error(self, "Hãy mở một file PDF trước.")
                return
            try:
                indices = _range_or_all(self.ed_trange.text(), self.model.page_count)
            except ValueError as e:
                show_error(self, str(e))
                return
            model = self.model
            dest = suffixed_output(model.path, "", ext=".txt",
                                   out_dir=default_out_dir(model.path))

            def job(progress, cancel):
                return convert.pdf_to_text(model, dest, page_indices=indices,
                                           progress=progress, cancel=cancel)

            status, payload = run_task(self, "Đang trích xuất text...", job)
            if status == "ok":
                path, n_chars = payload
                msg = f"Đã tạo file:\n{path}"
                if n_chars < 20:
                    msg += ("\n\nLưu ý: file gần như không có lớp text — "
                            "đây có thể là PDF scan. Hãy dùng chức năng OCR "
                            "để nhận diện chữ trước.")
                show_done(self, msg, open_path=path)
                self.accept()
            elif status == "error":
                show_error(self, payload)


class CompressDialog(QDialog):
    """Nen PDF: 3 muc, hien dung luong truoc/sau."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("Nén PDF — Giảm dung lượng")
        self.resize(540, 320)
        lay = QVBoxLayout(self)
        size = os.path.getsize(model.path)
        lay.addWidget(QLabel(
            f"File: {os.path.basename(model.path)}\n"
            f"Dung lượng hiện tại: {human_size(size)}"))
        lay.addWidget(QLabel("Chọn mức nén (nén bằng cách giảm chất lượng ảnh trong file):"))
        self.group = QButtonGroup(self)
        self.radios = {}
        for key in ("light", "medium", "strong"):
            rb = QRadioButton(COMPRESS_LEVELS[key][0])
            self.group.addButton(rb)
            self.radios[key] = rb
            lay.addWidget(rb)
        self.radios["medium"].setChecked(True)
        lay.addStretch(1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_close = QPushButton("Đóng")
        btn_go = QPushButton("Nén và lưu file mới")
        btn_go.setObjectName("primary")
        bottom.addWidget(btn_close)
        bottom.addWidget(btn_go)
        lay.addLayout(bottom)
        btn_close.clicked.connect(self.reject)
        btn_go.clicked.connect(self._run)

    def _run(self):
        level = next(k for k, rb in self.radios.items() if rb.isChecked())
        src = self.model.path
        pw = self.model.main_source.password
        dest = suffixed_output(src, "_compressed", out_dir=default_out_dir(src))

        def job(progress, cancel):
            return compress_pdf(src, dest, level=level, password=pw,
                                progress=progress, cancel=cancel)

        status, payload = run_task(self, "Đang nén PDF...", job)
        if status == "ok":
            final, before, after = payload
            pct = (1 - after / before) * 100 if before else 0
            if after >= before:
                msg = (f"Đã tạo file:\n{final}\n\n"
                       f"Dung lượng: {human_size(before)} → {human_size(after)}.\n"
                       "File này gần như không giảm thêm được (ảnh bên trong "
                       "đã được nén tối ưu).")
            else:
                msg = (f"Đã tạo file:\n{final}\n\n"
                       f"Dung lượng: {human_size(before)} → {human_size(after)} "
                       f"(giảm {pct:.0f}%)")
            show_done(self, msg, open_path=final)
            self.accept()
        elif status == "error":
            show_error(self, payload)


class SecurityDialog(QDialog):
    """Dat / go mat khau va quyen."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("Bảo mật PDF")
        self.resize(520, 400)
        lay = QVBoxLayout(self)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)

        # ----- Dat mat khau -----
        tab1 = QWidget()
        f1 = QFormLayout(tab1)
        self.ed_user = QLineEdit()
        self.ed_user.setEchoMode(QLineEdit.EchoMode.Password)
        self.ed_user2 = QLineEdit()
        self.ed_user2.setEchoMode(QLineEdit.EchoMode.Password)
        self.chk_print = QCheckBox("Cấm in tài liệu")
        self.chk_copy = QCheckBox("Cấm sao chép nội dung (copy)")
        self.chk_modify = QCheckBox("Cấm chỉnh sửa")
        self.chk_modify.setChecked(True)
        f1.addRow("Mật khẩu mở file:", self.ed_user)
        f1.addRow("Nhập lại mật khẩu:", self.ed_user2)
        f1.addRow(self.chk_print)
        f1.addRow(self.chk_copy)
        f1.addRow(self.chk_modify)
        note1 = QLabel("File mới sẽ được mã hóa AES-256. "
                       "Giữ mật khẩu cẩn thận — không có cách khôi phục nếu quên.")
        note1.setWordWrap(True)
        f1.addRow(note1)
        self.tabs.addTab(tab1, "Đặt mật khẩu / quyền")

        # ----- Go mat khau -----
        tab2 = QWidget()
        f2 = QFormLayout(tab2)
        self.ed_current = QLineEdit()
        self.ed_current.setEchoMode(QLineEdit.EchoMode.Password)
        f2.addRow("Mật khẩu hiện tại:", self.ed_current)
        note2 = QLabel("Tạo bản sao KHÔNG mã hóa của file (file gốc giữ nguyên).")
        note2.setWordWrap(True)
        f2.addRow(note2)
        self.tabs.addTab(tab2, "Gỡ mật khẩu")

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_close = QPushButton("Đóng")
        btn_go = QPushButton("Thực hiện và lưu file mới")
        btn_go.setObjectName("primary")
        bottom.addWidget(btn_close)
        bottom.addWidget(btn_go)
        lay.addLayout(bottom)
        btn_close.clicked.connect(self.reject)
        btn_go.clicked.connect(self._run)

    def _run(self):
        src = self.model.path
        cur_pw = self.model.main_source.password
        if self.tabs.currentIndex() == 0:
            pw1, pw2 = self.ed_user.text(), self.ed_user2.text()
            if not pw1:
                show_error(self, "Vui lòng nhập mật khẩu mở file.")
                return
            if pw1 != pw2:
                show_error(self, "Hai lần nhập mật khẩu không khớp. Vui lòng nhập lại.")
                return
            dest = suffixed_output(src, "_protected", out_dir=default_out_dir(src))
            allow_print = not self.chk_print.isChecked()
            allow_copy = not self.chk_copy.isChecked()
            allow_modify = not self.chk_modify.isChecked()

            def job(progress, cancel):
                progress(0, 1, "Đang mã hóa file...")
                r = security.encrypt_pdf(src, dest, user_password=pw1,
                                         allow_print=allow_print,
                                         allow_copy=allow_copy,
                                         allow_modify=allow_modify,
                                         current_password=cur_pw)
                progress(1, 1, "Xong")
                return r

            title = "Đang đặt mật khẩu..."
        else:
            pw = self.ed_current.text() or cur_pw
            if not pw:
                show_error(self, "Vui lòng nhập mật khẩu hiện tại của file.")
                return
            dest = suffixed_output(src, "_unlocked", out_dir=default_out_dir(src))

            def job(progress, cancel):
                progress(0, 1, "Đang gỡ mật khẩu...")
                r = security.decrypt_pdf(src, dest, password=pw)
                progress(1, 1, "Xong")
                return r

            title = "Đang gỡ mật khẩu..."

        status, payload = run_task(self, title, job)
        if status == "ok":
            show_done(self, f"Đã tạo file:\n{payload}", open_path=payload)
            self.accept()
        elif status == "error":
            show_error(self, payload)


class InsertDialog(QDialog):
    """Chen trang tu PDF khac vao tai lieu dang mo."""

    def __init__(self, model, current_page: int, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("Chèn trang từ PDF khác")
        self.resize(520, 280)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        pick_row = QHBoxLayout()
        self.ed_file = QLineEdit()
        self.ed_file.setPlaceholderText("Chọn file PDF nguồn...")
        self.ed_file.setReadOnly(True)
        btn_pick = QPushButton("Chọn file...")
        btn_pick.clicked.connect(self._pick)
        pick_row.addWidget(self.ed_file, 1)
        pick_row.addWidget(btn_pick)
        form.addRow("File nguồn:", pick_row)
        self.ed_range = QLineEdit()
        self.ed_range.setPlaceholderText("Để trống = tất cả các trang của file nguồn")
        form.addRow("Trang cần chèn:", self.ed_range)
        self.cb_pos = QComboBox()
        self.cb_pos.addItem(f"Trước trang hiện tại (trang {current_page + 1})",
                            current_page)
        self.cb_pos.addItem(f"Sau trang hiện tại (trang {current_page + 1})",
                            current_page + 1)
        self.cb_pos.addItem("Đầu tài liệu", 0)
        self.cb_pos.addItem("Cuối tài liệu", model.page_count)
        form.addRow("Vị trí chèn:", self.cb_pos)
        lay.addLayout(form)
        note = QLabel("Trang chèn chỉ nằm trong phiên làm việc — "
                      "dùng \"Lưu thành...\" để xuất file mới.")
        note.setWordWrap(True)
        lay.addWidget(note)
        lay.addStretch(1)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_close = QPushButton("Đóng")
        btn_go = QPushButton("Chèn trang")
        btn_go.setObjectName("primary")
        bottom.addWidget(btn_close)
        bottom.addWidget(btn_go)
        lay.addLayout(bottom)
        btn_close.clicked.connect(self.reject)
        btn_go.clicked.connect(self._insert)
        self._password = ""

    def _pick(self):
        from .merge_split import check_pdf_password
        f, _ = QFileDialog.getOpenFileName(
            self, "Chọn file PDF nguồn", config.get("last_open_dir", ""),
            "File PDF (*.pdf)")
        if not f:
            return
        pw = check_pdf_password(self, f)
        if pw is None:
            return
        self._password = pw
        self.ed_file.setText(f)

    def _insert(self):
        path = self.ed_file.text()
        if not path:
            show_error(self, "Vui lòng chọn file PDF nguồn.")
            return
        try:
            import pikepdf
            with pikepdf.open(path, password=self._password) as p:
                n_src = len(p.pages)
            indices = None
            if self.ed_range.text().strip():
                indices = parse_page_ranges(self.ed_range.text(), n_src)
        except ValueError as e:
            show_error(self, str(e))
            return
        except Exception:
            show_error(self, "Không đọc được file PDF nguồn.")
            return
        at = self.cb_pos.currentData()
        try:
            n = self.model.insert_from_pdf(path, at, indices, password=self._password)
        except Exception as e:
            from ...utils.errors import friendly_message
            show_error(self, friendly_message(e))
            return
        self.inserted = n
        self.accept()
