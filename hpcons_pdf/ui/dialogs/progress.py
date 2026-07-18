"""Hop thoai tien trinh dung chung + helper chay worker dong bo voi UI."""
from __future__ import annotations

import os
import subprocess

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QMessageBox,
                             QProgressBar, QPushButton, QVBoxLayout)

from ...core.worker import Worker


class ProgressDialog(QDialog):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        lay = QVBoxLayout(self)
        self.label = QLabel("Đang chuẩn bị...")
        self.label.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_cancel = QPushButton("Hủy")
        btn_row.addWidget(self.btn_cancel)
        lay.addWidget(self.label)
        lay.addWidget(self.bar)
        lay.addLayout(btn_row)

    def update_progress(self, cur: int, total: int, msg: str):
        if total > 0:
            self.bar.setRange(0, total)
            self.bar.setValue(cur)
        self.label.setText(msg)


def run_task(parent, title: str, fn):
    """Chay `fn(progress=..., cancel=...)` tren QThread voi hop thoai tien trinh.

    Tra ve (status, payload): status in {"ok", "error", "canceled"}.
    """
    dlg = ProgressDialog(title, parent)
    worker = Worker(fn)
    outcome = {"status": "canceled", "payload": None}

    def on_ok(result):
        outcome["status"] = "ok"
        outcome["payload"] = result
        dlg.accept()

    def on_fail(msg):
        outcome["status"] = "error"
        outcome["payload"] = msg
        dlg.accept()

    def on_canceled():
        outcome["status"] = "canceled"
        dlg.accept()

    def on_cancel_clicked():
        dlg.btn_cancel.setEnabled(False)
        dlg.label.setText("Đang hủy, vui lòng chờ...")
        worker.cancel()

    worker.progressed.connect(dlg.update_progress)
    worker.finished_ok.connect(on_ok)
    worker.failed.connect(on_fail)
    worker.canceled.connect(on_canceled)
    dlg.btn_cancel.clicked.connect(on_cancel_clicked)

    worker.start()
    dlg.exec()
    worker.wait()
    return outcome["status"], outcome["payload"]


def show_error(parent, message: str, title: str = "Lỗi"):
    QMessageBox.critical(parent, title, message)


def show_done(parent, message: str, open_path: str | None = None,
              title: str = "Hoàn tất"):
    """Thong bao thanh cong, kem nut mo thu muc chua file ket qua."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle(title)
    box.setText(message)
    box.addButton("Đóng", QMessageBox.ButtonRole.RejectRole)
    btn_open = None
    if open_path:
        btn_open = box.addButton("Mở thư mục chứa file",
                                 QMessageBox.ButtonRole.ActionRole)
    box.exec()
    if btn_open is not None and box.clickedButton() == btn_open:
        target = open_path if os.path.isdir(open_path) else os.path.dirname(open_path)
        try:
            if os.path.isfile(open_path):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(open_path)])
            else:
                os.startfile(os.path.normpath(target))  # noqa: S606
        except OSError:
            pass
