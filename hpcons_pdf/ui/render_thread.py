"""Luong render nen: render trang/thumbnail ngoai GUI thread de khong do giao dien.

Hai hang doi: uu tien cao (trang dang xem) va thap (thumbnail).
"""
from __future__ import annotations

import queue
import threading

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage


def pil_to_qimage(pil) -> QImage:
    if pil.mode != "RGB":
        pil = pil.convert("RGB")
    data = pil.tobytes("raw", "RGB")
    qimg = QImage(data, pil.width, pil.height, pil.width * 3,
                  QImage.Format.Format_RGB888)
    return qimg.copy()  # copy vi buffer PIL se bi giai phong


class RenderThread(QThread):
    """Signal: rendered(purpose, page_index, generation, QImage)."""
    rendered = pyqtSignal(str, int, int, QImage)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._high: queue.Queue = queue.Queue()
        self._low: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._wake = threading.Event()

    def request(self, model, page_index: int, scale: float, purpose: str,
                generation: int):
        q = self._high if purpose == "page" else self._low
        q.put((model, page_index, scale, purpose, generation))
        self._wake.set()

    def clear_pending(self, purpose: str | None = None):
        for q in ((self._high, self._low) if purpose is None
                  else ((self._high,) if purpose == "page" else (self._low,))):
            try:
                while True:
                    q.get_nowait()
            except queue.Empty:
                pass

    def stop(self):
        self._stop.set()
        self._wake.set()
        self.wait(3000)

    def run(self):
        while not self._stop.is_set():
            task = None
            try:
                task = self._high.get_nowait()
            except queue.Empty:
                try:
                    task = self._low.get_nowait()
                except queue.Empty:
                    self._wake.wait(0.1)
                    self._wake.clear()
                    continue
            model, idx, scale, purpose, gen = task
            try:
                if idx >= model.page_count:
                    continue
                pil = model.render_page(idx, scale)
                qimg = pil_to_qimage(pil)
            except Exception:
                continue
            if not self._stop.is_set():
                self.rendered.emit(purpose, idx, gen, qimg)
