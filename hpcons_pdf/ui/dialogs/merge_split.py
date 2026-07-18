"""Hop thoai Ghep file va Tach file."""
from __future__ import annotations

import os

import pikepdf
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox,
                             QDialog, QDoubleSpinBox, QFileDialog, QHBoxLayout,
                             QInputDialog, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QPushButton, QRadioButton,
                             QVBoxLayout)

from ...config import config
from ...core import operations
from ...core.overlay import add_page_numbers
from ...utils.errors import FriendlyError
from ...utils.fileutils import (human_size, parse_page_ranges, suffixed_output,
                                unique_path)
from .common import FolderPicker, default_out_dir
from .progress import run_task, show_done, show_error


def _ask_password(parent, path: str) -> str | None:
    """Hoi mat khau cho file PDF bi khoa. Tra ve None neu nguoi dung bo qua."""
    pw, ok = QInputDialog.getText(
        parent, "File có mật khẩu",
        f"File \"{os.path.basename(path)}\" được bảo vệ bằng mật khẩu.\n"
        "Nhập mật khẩu để tiếp tục:",
        QLineEdit.EchoMode.Password)
    return pw if ok else None


def check_pdf_password(parent, path: str) -> str | None:
    """Kiem tra file mo duoc khong; hoi mat khau neu can.

    Tra ve mat khau ("" neu khong can), None neu nguoi dung huy/sai.
    """
    pw = ""
    for _ in range(3):
        try:
            with pikepdf.open(path, password=pw):
                return pw
        except pikepdf.PasswordError:
            got = _ask_password(parent, path)
            if got is None:
                return None
            pw = got
        except Exception as e:
            show_error(parent, f"Không đọc được file:\n{os.path.basename(path)}\n\n"
                               "File có thể bị hỏng hoặc không phải PDF.")
            return None
    show_error(parent, "Mật khẩu không đúng (đã thử 3 lần).")
    return None


class MergeDialog(QDialog):
    """Ghep nhieu PDF: keo-tha sap thu tu, tuy chon danh so lien tuc."""

    def __init__(self, parent=None, initial_files: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Ghép file PDF")
        self.resize(620, 480)
        self._passwords: dict[str, str] = {}

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Danh sách file sẽ ghép (kéo-thả để sắp thứ tự):"))
        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        lay.addWidget(self.list, 1)

        row = QHBoxLayout()
        btn_add = QPushButton("Thêm file...")
        btn_remove = QPushButton("Bỏ khỏi danh sách")
        btn_up = QPushButton("Lên")
        btn_down = QPushButton("Xuống")
        for b in (btn_add, btn_remove, btn_up, btn_down):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)

        self.chk_number = QCheckBox(
            "Đánh số trang liên tục cho file sau khi ghép (theo cấu hình Đánh số hiện tại)")
        lay.addWidget(self.chk_number)

        lay.addWidget(QLabel("Lưu file kết quả vào thư mục:"))
        self.folder = FolderPicker(config.get("out_dir", ""))
        lay.addWidget(self.folder)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_cancel = QPushButton("Đóng")
        self.btn_merge = QPushButton("Ghép file")
        self.btn_merge.setObjectName("primary")
        bottom.addWidget(btn_cancel)
        bottom.addWidget(self.btn_merge)
        lay.addLayout(bottom)

        btn_add.clicked.connect(self._add_files)
        btn_remove.clicked.connect(self._remove_selected)
        btn_up.clicked.connect(lambda: self._move(-1))
        btn_down.clicked.connect(lambda: self._move(1))
        btn_cancel.clicked.connect(self.reject)
        self.btn_merge.clicked.connect(self._do_merge)

        for f in initial_files or []:
            self._append_file(f)

    def _append_file(self, path: str):
        if not path.lower().endswith(".pdf"):
            return
        pw = check_pdf_password(self, path)
        if pw is None:
            return
        self._passwords[path] = pw
        try:
            size = human_size(os.path.getsize(path))
        except OSError:
            size = "?"
        it = QListWidgetItem(f"{os.path.basename(path)}   ({size})")
        it.setData(Qt.ItemDataRole.UserRole, path)
        it.setToolTip(path)
        self.list.addItem(it)

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn file PDF để ghép",
            config.get("last_open_dir", ""), "File PDF (*.pdf)")
        for f in files:
            self._append_file(f)
        if files:
            config.set("last_open_dir", os.path.dirname(files[0]))

    def _remove_selected(self):
        for it in self.list.selectedItems():
            self.list.takeItem(self.list.row(it))

    def _move(self, delta: int):
        rows = sorted((self.list.row(it) for it in self.list.selectedItems()),
                      reverse=(delta > 0))
        for r in rows:
            nr = r + delta
            if 0 <= nr < self.list.count():
                it = self.list.takeItem(r)
                self.list.insertItem(nr, it)
                it.setSelected(True)

    def _paths(self) -> list[str]:
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.list.count())]

    def _do_merge(self):
        paths = self._paths()
        if len(paths) < 2:
            show_error(self, "Cần chọn ít nhất 2 file PDF để ghép.")
            return
        out_dir = self.folder.path() or os.path.dirname(paths[0])
        first = os.path.splitext(os.path.basename(paths[0]))[0]
        dest = unique_path(os.path.join(out_dir, f"{first}_merged.pdf"))
        do_number = self.chk_number.isChecked()
        passwords = dict(self._passwords)

        def job(progress, cancel):
            result = operations.merge_pdfs(paths, dest, passwords=passwords,
                                           progress=progress, cancel=cancel)
            if do_number:
                ncfg = config.get("number")
                numbered = suffixed_output(result, "_numbered")
                numbered = add_page_numbers(
                    result, numbered,
                    position=ncfg.get("position", "bottom-center"),
                    font=ncfg.get("font", "Arial"),
                    size=int(ncfg.get("size", 11)),
                    fmt=ncfg.get("format", "Trang {n}/{total}"),
                    start=int(ncfg.get("start", 1)),
                    margin_mm=float(ncfg.get("margin_mm", 10)),
                    progress=progress, cancel=cancel)
                return (result, numbered)
            return (result, None)

        status, payload = run_task(self, "Đang ghép file PDF...", job)
        if status == "ok":
            merged, numbered = payload
            msg = f"Đã ghép {len(paths)} file thành:\n{merged}"
            if numbered:
                msg += f"\n\nBản đã đánh số trang liên tục:\n{numbered}"
            show_done(self, msg, open_path=numbered or merged)
            self.accept()
        elif status == "error":
            show_error(self, payload)


class SplitDialog(QDialog):
    """Tach file: theo khoang trang / moi trang 1 file / theo dung luong."""

    def __init__(self, src_path: str, page_count: int, password: str = "",
                 parent=None):
        super().__init__(parent)
        self.src_path = src_path
        self.page_count = page_count
        self.password = password
        self.setWindowTitle("Tách file PDF")
        self.resize(560, 380)

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            f"File: {os.path.basename(src_path)}  —  {page_count} trang"))

        self.rb_range = QRadioButton("Tách theo khoảng trang (tạo 1 file chứa các trang chọn):")
        self.ed_range = QLineEdit()
        self.ed_range.setPlaceholderText("Ví dụ: 1-5, 8, 10-12")
        self.rb_each = QRadioButton("Tách mỗi trang thành 1 file riêng")
        self.rb_size = QRadioButton("Tách theo dung lượng (xấp xỉ), mỗi phần tối đa:")
        self.sp_size = QDoubleSpinBox()
        self.sp_size.setRange(0.2, 500)
        self.sp_size.setValue(5.0)
        self.sp_size.setSuffix(" MB")
        self.sp_size.setDecimals(1)

        grp = QButtonGroup(self)
        for rb in (self.rb_range, self.rb_each, self.rb_size):
            grp.addButton(rb)
        self.rb_range.setChecked(True)

        lay.addWidget(self.rb_range)
        row1 = QHBoxLayout()
        row1.addSpacing(24)
        row1.addWidget(self.ed_range, 1)
        lay.addLayout(row1)
        lay.addWidget(self.rb_each)
        row2 = QHBoxLayout()
        row2.addWidget(self.rb_size)
        row2.addWidget(self.sp_size)
        row2.addStretch(1)
        lay.addLayout(row2)

        lay.addWidget(QLabel("Lưu kết quả vào thư mục:"))
        self.folder = FolderPicker(default_out_dir(src_path))
        lay.addWidget(self.folder)
        lay.addStretch(1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_close = QPushButton("Đóng")
        btn_go = QPushButton("Tách file")
        btn_go.setObjectName("primary")
        bottom.addWidget(btn_close)
        bottom.addWidget(btn_go)
        lay.addLayout(bottom)
        btn_close.clicked.connect(self.reject)
        btn_go.clicked.connect(self._do_split)

    def _do_split(self):
        out_dir = self.folder.path() or default_out_dir(self.src_path)
        src, pw = self.src_path, self.password
        try:
            if self.rb_range.isChecked():
                indices = parse_page_ranges(self.ed_range.text(), self.page_count)
        except ValueError as e:
            show_error(self, str(e))
            return

        if self.rb_range.isChecked():
            dest = suffixed_output(src, "_split", out_dir=out_dir)

            def job(progress, cancel):
                progress(0, 1, "Đang tách trang...")
                r = operations.split_by_ranges(src, indices, dest, password=pw)
                progress(1, 1, "Xong")
                return [r]
        elif self.rb_each.isChecked():
            def job(progress, cancel):
                return operations.split_each_page(src, out_dir, password=pw,
                                                  progress=progress, cancel=cancel)
        else:
            max_bytes = int(self.sp_size.value() * 1024 * 1024)

            def job(progress, cancel):
                return operations.split_by_size(src, max_bytes, out_dir,
                                                password=pw, progress=progress,
                                                cancel=cancel)

        status, payload = run_task(self, "Đang tách file PDF...", job)
        if status == "ok":
            files = payload
            if len(files) == 1:
                msg = f"Đã tạo file:\n{files[0]}"
            else:
                msg = (f"Đã tạo {len(files)} file trong thư mục:\n{out_dir}\n\n"
                       + "\n".join(os.path.basename(f) for f in files[:8]))
                if len(files) > 8:
                    msg += f"\n... và {len(files) - 8} file khác"
            show_done(self, msg, open_path=files[0])
            self.accept()
        elif status == "error":
            show_error(self, payload)
