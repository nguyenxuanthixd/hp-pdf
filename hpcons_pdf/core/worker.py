"""Worker QThread dung chung cho cac thao tac nang (OCR, nen, ghep...).

Ham cong viec nhan (progress, cancel):
- progress(cur, total, message) -> phat tin hieu cap nhat UI.
- cancel: threading.Event — kiem tra dinh ky de ho tro nut Huy.
"""
from __future__ import annotations

import threading
import traceback

from PyQt6.QtCore import QThread, pyqtSignal

from ..utils.errors import FriendlyError, friendly_message


class Worker(QThread):
    progressed = pyqtSignal(int, int, str)   # cur, total, message
    finished_ok = pyqtSignal(object)         # ket qua tra ve
    failed = pyqtSignal(str)                 # thong bao loi tieng Viet
    canceled = pyqtSignal()

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn
        self.cancel_event = threading.Event()

    def cancel(self):
        self.cancel_event.set()

    def run(self):
        try:
            result = self._fn(
                progress=lambda c, t, m: self.progressed.emit(int(c), int(t), m),
                cancel=self.cancel_event,
            )
        except FriendlyError as e:
            if self.cancel_event.is_set():
                self.canceled.emit()
            else:
                self.failed.emit(str(e))
            return
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.failed.emit(friendly_message(e))
            return
        if self.cancel_event.is_set():
            self.canceled.emit()
        else:
            self.finished_ok.emit(result)
