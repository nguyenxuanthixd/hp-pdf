"""Khung xem PDF: cuon lien tuc, zoom, fit, tim kiem, quet chon/copy chu,
keo trang (pan), chinh sua doi tuong goc va ghi chu (chu/highlight/hinh ve)."""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QColor, QCursor, QFont, QGuiApplication, QImage,
                         QPainter, QPainterPath, QPen, QPixmap)
from PyQt6.QtWidgets import (QInputDialog, QMenu, QMessageBox, QScrollArea,
                             QToolTip, QVBoxLayout, QWidget)

import pypdfium2.raw as pdfium_c

from ..core.annotations import Annot, measure_text
from ..core.document import NativeObj
from ..utils.errors import FriendlyError

BASE_SCALE = 96.0 / 72.0  # 100% = kich thuoc thuc tren man hinh 96dpi
PAGE_GAP = 14
MIN_ZOOM, MAX_ZOOM = 0.15, 6.0

# Cong cu: 'pan' | 'select' | 'text' | 'highlight' | 'hl-ellipse' | 'rect'
#          | 'ellipse' | 'line' | 'arrow' | 'pen' | 'cover' | 'erase'
DRAW_TOOLS = {"highlight", "hl-ellipse", "rect", "ellipse", "line", "arrow",
              "pen", "cover"}


class _PageWidget(QWidget):
    """Mot trang trong khung cuon."""

    def __init__(self, index: int, view: "PdfView", parent=None):
        super().__init__(parent)
        self.index = index
        self.view = view
        self.pixmap: QPixmap | None = None
        self.highlights: list[tuple[float, float, float, float]] = []
        self.text_sel_rects: list[tuple[float, float, float, float]] = []
        self.zoom = 1.0
        self.setMouseTracking(True)

    def set_page_px(self, w: int, h: int):
        self.setFixedSize(w, h)

    # ---------- Ve ----------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#FFFFFF"))
        if self.pixmap is not None:
            p.drawPixmap(self.rect(), self.pixmap)
        else:
            p.setPen(QColor("#C8CCD0"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Đang tải...")
        p.setPen(QColor("#C8CCD0"))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        z = self.zoom * BASE_SCALE
        # Highlight tim kiem (xanh la)
        if self.highlights:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(95, 191, 45, 90))
            for (x, y, w, h) in self.highlights:
                if x < 0:
                    continue
                p.drawRect(QRectF(x * z, y * z, w * z, h * z).toRect())
        # Vung chon chu (xanh duong, nhu trinh doc PDF)
        if self.text_sel_rects:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(27, 117, 187, 80))
            for (x, y, w, h) in self.text_sel_rects:
                p.drawRect(QRectF(x * z, y * z, w * z, h * z))
        # Ghi chu / hinh ve
        for a in self.view.annots_for_page(self.index):
            selected = self.view.is_selected(self.index, a)
            _draw_annot(p, a, z, selected)
        # Doi tuong goc dang chon (khung cam)
        nsel = self.view.native_sel_info(self.index)
        if nsel is not None and nsel[0]:
            objs, dx, dy = nsel
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor("#E67E22"), 2, Qt.PenStyle.DashLine))
            if len(objs) == 1:
                obj = objs[0]
                p.drawRect(QRectF((obj.x + dx) * z - 2, (obj.y + dy) * z - 2,
                                  obj.w * z + 4, obj.h * z + 4))
            else:
                # Nhieu doi tuong -> ve 1 KHUNG BAO chung cho do roi mat
                x0 = min(o.x for o in objs)
                y0 = min(o.y for o in objs)
                x1 = max(o.x + o.w for o in objs)
                y1 = max(o.y + o.h for o in objs)
                p.drawRect(QRectF((x0 + dx) * z - 3, (y0 + dy) * z - 3,
                                  (x1 - x0) * z + 6, (y1 - y0) * z + 6))
        # Khung quet (chon = xanh, xoa vung = do)
        band = self.view.band_rect_for(self.index)
        if band is not None:
            if self.view.band_mode == "erase":
                p.setPen(QPen(QColor("#C0392B"), 1, Qt.PenStyle.DashLine))
                p.setBrush(QColor(192, 57, 43, 30))
            else:
                p.setPen(QPen(QColor("#1B75BB"), 1, Qt.PenStyle.DashLine))
                p.setBrush(QColor(27, 117, 187, 30))
            p.drawRect(QRectF(band.x() * z, band.y() * z,
                              band.width() * z, band.height() * z))
        p.end()

    # ---------- Chuot -> chuyen cho view xu ly ----------
    def _pt(self, event) -> QPointF:
        z = self.zoom * BASE_SCALE
        pos = event.position()
        return QPointF(pos.x() / z, pos.y() / z)

    def mousePressEvent(self, event):
        if not self.view.handle_press(self, self._pt(event), event):
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.NoButton:
            self.view.handle_hover(self, self._pt(event))
            return
        if not self.view.handle_move(self, self._pt(event)):
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if not self.view.handle_release(self, self._pt(event)):
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if not self.view.handle_double_click(self, self._pt(event)):
            super().mouseDoubleClickEvent(event)


# Ten phong (theo overlay._FONT_FILES) -> (ho QFont, in dam) de ve xem truoc
_QFONT_MAP = {
    "Arial": ("Arial", False),
    "Arial đậm": ("Arial", True),
    "Times New Roman": ("Times New Roman", False),
    "Segoe UI": ("Segoe UI", False),
    "Microsoft YaHei (Trung)": ("Microsoft YaHei", False),
}


def _qfont_family(name: str) -> tuple[str, bool]:
    return _QFONT_MAP.get(name, ("Arial", False))


def _draw_annot(p: QPainter, a: Annot, z: float, selected: bool):
    col = QColor(a.color)
    if a.kind == "highlight":
        c = QColor(col)
        c.setAlphaF(0.40)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawRect(QRectF(a.x * z, a.y * z, a.w * z, a.h * z))
    elif a.kind == "whiteout":
        # Che: to theo MAU NEN (mac dinh trang) + vien mo (chi tren man hinh)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(a.color or "#FFFFFF"))
        p.drawRect(QRectF(a.x * z, a.y * z, a.w * z, a.h * z))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(0, 0, 0, 28), 1, Qt.PenStyle.DashLine))
        p.drawRect(QRectF(a.x * z, a.y * z, a.w * z, a.h * z))
    elif a.kind == "rect":
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(col, max(1.0, a.width * z)))
        p.drawRect(QRectF(a.x * z, a.y * z, a.w * z, a.h * z))
    elif a.kind == "ellipse":
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(col, max(1.0, a.width * z)))
        p.drawEllipse(QRectF(a.x * z, a.y * z, a.w * z, a.h * z))
    elif a.kind == "hl-ellipse":
        c = QColor(col)
        c.setAlphaF(0.40)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawEllipse(QRectF(a.x * z, a.y * z, a.w * z, a.h * z))
    elif a.kind == "line" and len(a.points) >= 2:
        p.setPen(QPen(col, max(1.0, a.width * z),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        (x1, y1), (x2, y2) = a.points[0], a.points[-1]
        p.drawLine(QPointF(x1 * z, y1 * z), QPointF(x2 * z, y2 * z))
    elif a.kind == "arrow" and len(a.points) >= 2:
        import math
        p.setPen(QPen(col, max(1.0, a.width * z),
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        (x1, y1), (x2, y2) = a.points[0], a.points[-1]
        p.drawLine(QPointF(x1 * z, y1 * z), QPointF(x2 * z, y2 * z))
        ang = math.atan2(y2 - y1, x2 - x1)
        head = max(8.0, a.width * 4 + 6)
        for da in (math.pi * 5 / 6, -math.pi * 5 / 6):
            hx = x2 + head * math.cos(ang + da)
            hy = y2 + head * math.sin(ang + da)
            p.drawLine(QPointF(x2 * z, y2 * z), QPointF(hx * z, hy * z))
    elif a.kind == "pen" and len(a.points) >= 2:
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(col, max(1.0, a.width * z), Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        path = QPainterPath(QPointF(a.points[0][0] * z, a.points[0][1] * z))
        for (px, py) in a.points[1:]:
            path.lineTo(QPointF(px * z, py * z))
        p.drawPath(path)
    elif a.kind == "text" and a.text:
        bg = getattr(a, "bg_color", "")
        if bg:
            p.fillRect(QRectF(a.x * z - 1, a.y * z - 1,
                              a.w * z + 2, a.h * z + 2), QColor(bg))
        p.setPen(QPen(col))
        fam, bold = _qfont_family(getattr(a, "font", "Arial"))
        f = QFont(fam)
        f.setBold(bold)
        f.setPixelSize(max(2, int(a.font_size * z)))
        p.setFont(f)
        for i, line in enumerate(a.text.split("\n")):
            base_y = (a.y + a.font_size * 0.9 + i * a.font_size * 1.2) * z
            p.drawText(QPointF(a.x * z, base_y), line)
    if selected:
        x, y, w, h = a.bbox()
        pen = QPen(QColor("#1B75BB"), 1, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(x * z - 3, y * z - 3, w * z + 6, h * z + 6))
        # Diem nam 2 dau duong/mui ten -> keo dai/ngan
        if a.kind in ("line", "arrow") and len(a.points) >= 2:
            p.setPen(QPen(QColor("#1B75BB"), 1))
            p.setBrush(QColor("#FFFFFF"))
            for (px, py) in (a.points[0], a.points[-1]):
                p.drawRect(QRectF(px * z - 4, py * z - 4, 8, 8))


class PdfView(QScrollArea):
    pageChanged = pyqtSignal(int)          # trang hien tai (0-based)
    zoomChanged = pyqtSignal(float)
    annotationsChanged = pyqtSignal()      # co chinh sua (annot/goc)
    toolFinished = pyqtSignal()            # da ve xong 1 hinh
    pageContentChanged = pyqtSignal(int)   # noi dung goc cua trang thay doi
    panRequested = pyqtSignal()            # ESC -> quay ve cong cu Xem

    def __init__(self, render_thread, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._rt = render_thread
        self._rt.rendered.connect(self._on_rendered)
        self.model = None
        self.zoom = 1.0
        self.fit_mode: str | None = "fit-width"
        self.generation = 0
        self._pages: list[_PageWidget] = []
        self._sizes_pt: list[tuple[float, float]] = []
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(PAGE_GAP, PAGE_GAP, PAGE_GAP, PAGE_GAP)
        self._layout.setSpacing(PAGE_GAP)
        self.setWidget(self._container)
        self._current_page = 0
        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(60)
        self._update_timer.timeout.connect(self._update_visible)
        self.verticalScrollBar().valueChanged.connect(
            lambda _: self._update_timer.start())
        self._container.setStyleSheet("background: #ECEDEF;")

        # Trang thai cong cu
        self.tool = "pan"
        self.annot_color = "#E53935"
        self.annot_width = 2.0
        self._endpoint_drag = None      # (annot, chi_so_diem) khi keo dau duong
        self._endpoint_before = None    # points truoc khi keo (de hoan tac)
        self._selected: tuple[int, Annot] | None = None   # ghi chu dang chon
        self._draft: Annot | None = None
        self._draft_page = -1
        self._drag_start: QPointF | None = None
        self._moving = False
        # Doi tuong goc dang chon: (trang, [NativeObj...])
        self._native_sel: tuple[int, list[NativeObj]] | None = None
        self._native_moving = False
        self._native_delta = QPointF(0, 0)
        self._warned_rotated: set[int] = set()
        # Quet vung (chon doi tuong / xoa vung)
        self._band_page = -1
        self._band_origin: QPointF | None = None
        self._band_rect: QRectF | None = None
        self.band_mode = "select"  # "select" | "erase"
        self._pending_click_obj = None  # doi tuong duoi con tro khi bam (chua keo)
        # Keo trang (pan)
        self._panning = False
        self._pan_start = QPoint()
        self._pan_sb = (0, 0)
        # Quet chon chu
        self._tsel_page = -1
        self._tsel_anchor = -1
        self._tsel_focus = -1
        self._tsel_text = ""
        self._tsel_dragging = False
        # Di chuyen bang phim mui ten: gom nhieu lan bam thanh 1 buoc hoan tac
        self._nudge_timer = QTimer(self)
        self._nudge_timer.setSingleShot(True)
        self._nudge_timer.setInterval(400)
        self._nudge_timer.timeout.connect(self._commit_nudge)
        self._annot_nudge = QPointF(0, 0)

    # ---------- Tai lieu ----------
    def set_model(self, model):
        self.model = model
        self.reload(keep_position=False)

    def reload(self, keep_position: bool = True):
        """Xay lai layout trang (sau khi xoay/xoa/sap xep...)."""
        pos = self.verticalScrollBar().value() if keep_position else 0
        self.generation += 1
        self._rt.clear_pending("page", self.model)
        self._selected = None
        self._draft = None
        self._native_sel = None
        self._band_rect = None
        self._nudge_timer.stop()
        self._annot_nudge = QPointF(0, 0)
        self._native_delta = QPointF(0, 0)
        self.clear_text_selection()
        for w in self._pages:
            w.setParent(None)
            w.deleteLater()
        self._pages = []
        self._sizes_pt = []
        if self.model is None:
            return
        for i in range(self.model.page_count):
            self._sizes_pt.append(self.model.page_size(i))
            pw = _PageWidget(i, self, self._container)
            self._layout.addWidget(pw, 0, Qt.AlignmentFlag.AlignHCenter)
            pw.show()
            self._pages.append(pw)
        self._apply_fit()
        self._resize_pages()
        self._apply_cursor()
        self.verticalScrollBar().setValue(pos)
        self._update_timer.start()

    # ---------- Zoom ----------
    def _capture_anchor(self):
        """Ghi lai (trang hien tai, vi tri tuong doi trong trang) truoc khi
        doi zoom — de sau khi phong to/thu nho van dung cho cu, khong nhay trang."""
        if not self._pages:
            return None
        i = min(self._current_page, len(self._pages) - 1)
        pw = self._pages[i]
        rel = (self.verticalScrollBar().value() - pw.y()) / max(pw.height(), 1)
        return (i, rel)

    def _restore_anchor(self, anchor):
        if anchor is None or not self._pages:
            return
        i, rel = anchor
        i = min(i, len(self._pages) - 1)
        self._layout.activate()
        self._container.adjustSize()
        pw = self._pages[i]
        self.verticalScrollBar().setValue(int(pw.y() + rel * pw.height()))

    def set_zoom(self, zoom: float, fit_mode: str | None = None):
        anchor = self._capture_anchor()
        self.fit_mode = fit_mode
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, zoom))
        self.generation += 1
        self._rt.clear_pending("page", self.model)
        self._resize_pages()
        self._restore_anchor(anchor)
        self._update_timer.start()
        self.zoomChanged.emit(self.zoom)

    def set_fit_mode(self, mode: str | None):
        anchor = self._capture_anchor()
        self.fit_mode = mode
        self._apply_fit()
        self.generation += 1
        self._rt.clear_pending("page", self.model)
        self._resize_pages()
        self._restore_anchor(anchor)
        self._update_timer.start()
        self.zoomChanged.emit(self.zoom)

    def zoom_in(self):
        self.set_zoom(self.zoom * 1.2)

    def zoom_out(self):
        self.set_zoom(self.zoom / 1.2)

    def _apply_fit(self):
        if not self._sizes_pt or self.fit_mode is None:
            return
        i = min(self._current_page, len(self._sizes_pt) - 1)
        w_pt, h_pt = self._sizes_pt[i]
        avail_w = self.viewport().width() - 2 * PAGE_GAP - 20
        avail_h = self.viewport().height() - 2 * PAGE_GAP
        if avail_w <= 50 or avail_h <= 50:
            return
        if self.fit_mode == "fit-width":
            self.zoom = avail_w / (w_pt * BASE_SCALE)
        elif self.fit_mode == "fit-page":
            self.zoom = min(avail_w / (w_pt * BASE_SCALE),
                            avail_h / (h_pt * BASE_SCALE))
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, self.zoom))

    def _resize_pages(self):
        for i, pw in enumerate(self._pages):
            w_pt, h_pt = self._sizes_pt[i]
            pw.zoom = self.zoom
            pw.pixmap = None
            pw.set_page_px(int(w_pt * BASE_SCALE * self.zoom),
                           int(h_pt * BASE_SCALE * self.zoom))
        self._container.adjustSize()

    # ---------- Render hien thi ----------
    def _visible_range(self) -> tuple[int, int]:
        if not self._pages:
            return (0, -1)
        top = self.verticalScrollBar().value()
        bottom = top + self.viewport().height()
        first, last = None, None
        for i, pw in enumerate(self._pages):
            y0 = pw.y()
            y1 = y0 + pw.height()
            if y1 >= top and y0 <= bottom:
                if first is None:
                    first = i
                last = i
        if first is None:
            return (0, -1)
        return (first, last)

    def _update_visible(self):
        if self.model is None or not self._pages:
            return
        first, last = self._visible_range()
        if last < first:
            return
        center = self.verticalScrollBar().value() + self.viewport().height() // 2
        cur = first
        for i in range(first, last + 1):
            pw = self._pages[i]
            if pw.y() <= center <= pw.y() + pw.height():
                cur = i
                break
        if cur != self._current_page:
            self._current_page = cur
            self.pageChanged.emit(cur)
        lo, hi = max(0, first - 1), min(len(self._pages) - 1, last + 1)
        dpr = self.devicePixelRatioF()
        for i in range(lo, hi + 1):
            pw = self._pages[i]
            if pw.pixmap is None:
                self._rt.request(self.model, i, BASE_SCALE * self.zoom * dpr,
                                 "page", self.generation)
        for i, pw in enumerate(self._pages):
            if (i < lo - 4 or i > hi + 4) and pw.pixmap is not None:
                pw.pixmap = None

    def _on_rendered(self, purpose: str, index: int, gen: int, img: QImage,
                     model=None):
        if purpose != "page" or gen != self.generation \
                or model is not self.model:
            return
        if index >= len(self._pages):
            return
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(self.devicePixelRatioF())
        self._pages[index].pixmap = pm
        self._pages[index].update()

    # ---------- Dieu huong ----------
    @property
    def current_page(self) -> int:
        return self._current_page

    def goto_page(self, index: int):
        if not self._pages:
            return
        index = max(0, min(index, len(self._pages) - 1))
        self.verticalScrollBar().setValue(self._pages[index].y() - PAGE_GAP)
        self._update_timer.start()

    # ---------- Tim kiem ----------
    def set_highlights(self, page_index: int,
                       rects: list[tuple[float, float, float, float]]):
        for i, pw in enumerate(self._pages):
            new = rects if i == page_index else []
            if pw.highlights != new:
                pw.highlights = new
                pw.update()

    def clear_highlights(self):
        for pw in self._pages:
            if pw.highlights:
                pw.highlights = []
                pw.update()

    # ================= Cong cu =================
    def set_tool(self, tool: str):
        self.flush_pending_edits()
        self.tool = tool
        self._draft = None
        self._band_rect = None
        if tool != "pan":
            self.clear_text_selection()
        if tool != "select":
            self._set_selected(None)
            self._set_native_sel(None)
        self._apply_cursor()

    def _apply_cursor(self):
        if self.tool == "pan":
            cursor = Qt.CursorShape.OpenHandCursor
        elif self.tool == "select":
            cursor = Qt.CursorShape.ArrowCursor
        elif self.tool == "text":
            cursor = Qt.CursorShape.IBeamCursor
        else:  # ve hinh / danh dau / xoa vung
            cursor = Qt.CursorShape.CrossCursor
        for pw in self._pages:
            pw.setCursor(cursor)

    def annots_for_page(self, index: int) -> list[Annot]:
        if self.model is None or index >= self.model.page_count:
            return []
        annots = list(self.model.pages[index].annots)
        if self._draft is not None and self._draft_page == index:
            annots.append(self._draft)
        return annots

    def is_selected(self, index: int, a: Annot) -> bool:
        return (self._selected is not None and self._selected[0] == index
                and self._selected[1] is a)

    def _set_selected(self, sel: tuple[int, Annot] | None):
        old = self._selected
        self._selected = sel
        if sel is not None:
            self.setFocus(Qt.FocusReason.OtherFocusReason)
        for pair in (old, sel):
            if pair is not None and pair[0] < len(self._pages):
                self._pages[pair[0]].update()

    # ----- Doi tuong goc -----
    def native_sel_info(self, index: int):
        if self._native_sel is not None and self._native_sel[0] == index:
            return (self._native_sel[1], self._native_delta.x(),
                    self._native_delta.y())
        return None

    def _set_native_sel(self, sel: tuple[int, list[NativeObj]] | None):
        old = self._native_sel
        self._native_sel = sel
        self._native_delta = QPointF(0, 0)
        # Giu focus ban phim cho khung xem de phim mui ten NHICH vung chon
        # (khong bi cuon trang) sau khi khoanh chon bang chuot.
        if sel is not None:
            self.setFocus(Qt.FocusReason.OtherFocusReason)
        for pair in (old, sel):
            if pair is not None and pair[0] < len(self._pages):
                self._pages[pair[0]].update()

    def band_rect_for(self, index: int) -> QRectF | None:
        if self._band_rect is not None and self._band_page == index:
            return self._band_rect
        return None

    def _refresh_page_render(self, index: int):
        if index < len(self._pages):
            self._pages[index].pixmap = None
            self._pages[index].update()
            self._update_timer.start()
        self.pageContentChanged.emit(index)

    @property
    def has_selection(self) -> bool:
        return self._selected is not None or self._native_sel is not None

    def delete_selected(self) -> bool:
        if self._selected is not None:
            idx, a = self._selected
            ref = self.model.pages[idx]
            if a in ref.annots:
                pos = ref.annots.index(a)
                ref.annots.remove(a)
                self.model.push_undo(
                    "xóa ghi chú", lambda: ref.annots.insert(pos, a))
            self._selected = None
            self._pages[idx].update()
            self._mark_changed()
            return True
        if self._native_sel is not None:
            idx, objs = self._native_sel
            try:
                self.model.delete_natives(idx, objs)
            except FriendlyError as e:
                QMessageBox.warning(self, "Không xóa được", str(e))
                return True
            self._native_sel = None
            self._refresh_page_render(idx)
            self._mark_changed()
            return True
        return False

    def _mark_changed(self):
        if self.model is not None:
            self.model.modified = True
        self.annotationsChanged.emit()

    def _hit_annot(self, index: int, pt: QPointF) -> Annot | None:
        for a in reversed(self.model.pages[index].annots):
            if a.hit(pt.x(), pt.y()):
                return a
        return None

    def _endpoint_at(self, index: int, pt: QPointF):
        """Neu dang chon 1 duong/mui ten tren trang `index` va con tro gan
        1 trong 2 dau -> tra (annot, chi_so_diem); nguoc lai None."""
        sel = self._selected
        if sel is None or sel[0] != index:
            return None
        a = sel[1]
        if a.kind not in ("line", "arrow") or len(a.points) < 2:
            return None
        tol = 7.0
        for i in (0, len(a.points) - 1):
            px, py = a.points[i]
            if abs(pt.x() - px) <= tol and abs(pt.y() - py) <= tol:
                return (a, i)
        return None

    def _hit_native_safe(self, index: int, pt: QPointF) -> NativeObj | None:
        try:
            return self.model.hit_native(index, pt.x(), pt.y())
        except FriendlyError as e:
            if index not in self._warned_rotated:
                self._warned_rotated.add(index)
                QMessageBox.information(self, "Trang đang xoay", str(e))
            return None
        except Exception:
            return None

    # ----- Chon / copy chu -----
    def clear_text_selection(self):
        self._tsel_page = -1
        self._tsel_anchor = self._tsel_focus = -1
        self._tsel_text = ""
        self._tsel_dragging = False
        for pw in self._pages:
            if pw.text_sel_rects:
                pw.text_sel_rects = []
                pw.update()

    def selected_text(self) -> str:
        return self._tsel_text

    def _update_text_selection(self):
        if self._tsel_page < 0 or self._tsel_anchor < 0 or self._tsel_focus < 0:
            return
        text, rects = self.model.text_range(
            self._tsel_page, self._tsel_anchor, self._tsel_focus)
        self._tsel_text = text
        for i, pw in enumerate(self._pages):
            new = rects if i == self._tsel_page else []
            if pw.text_sel_rects != new:
                pw.text_sel_rects = new
                pw.update()

    def copy_selected_text(self) -> bool:
        if self._tsel_text.strip():
            QGuiApplication.clipboard().setText(self._tsel_text)
            return True
        return False

    # ----- Di chuyen bang phim mui ten -----
    def _nudge(self, dx: float, dy: float):
        """Dich chuyen doi tuong dang chon; commit sau khi ngung bam 0.4s."""
        if self._selected is not None:
            idx, a = self._selected
            a.move_by(dx, dy)
            self._annot_nudge += QPointF(dx, dy)
            if idx < len(self._pages):
                self._pages[idx].update()
            self._nudge_timer.start()
        elif self._native_sel is not None and not self._native_moving:
            self._native_delta += QPointF(dx, dy)
            idx = self._native_sel[0]
            if idx < len(self._pages):
                self._pages[idx].update()
            self._nudge_timer.start()

    def _commit_nudge(self):
        self._nudge_timer.stop()
        # Ghi chu: da di chuyen truc tiep, chi can day 1 buoc hoan tac
        acc = self._annot_nudge
        if self._selected is not None and (abs(acc.x()) > 0.01 or abs(acc.y()) > 0.01):
            _idx, a = self._selected
            dx, dy = acc.x(), acc.y()
            self.model.push_undo("di chuyển ghi chú",
                                 lambda: a.move_by(-dx, -dy))
            self._mark_changed()
        self._annot_nudge = QPointF(0, 0)
        # Doi tuong goc: ap dung do lech tich luy vao file
        if self._native_sel is not None and not self._native_moving:
            dx, dy = self._native_delta.x(), self._native_delta.y()
            if abs(dx) > 0.01 or abs(dy) > 0.01:
                idx, objs = self._native_sel
                self._native_delta = QPointF(0, 0)
                try:
                    self.model.move_natives(idx, objs, dx, dy)
                    for obj in objs:
                        obj.x += dx
                        obj.y += dy
                    self._refresh_page_render(idx)
                    self._mark_changed()
                except FriendlyError as e:
                    QMessageBox.warning(self, "Không di chuyển được", str(e))

    def flush_pending_edits(self):
        """Ap dung ngay cac dich chuyen phim mui ten con cho (goi truoc undo...)."""
        if self._nudge_timer.isActive():
            self._commit_nudge()

    # ----- Hover: doi con tro theo noi dung duoi chuot -----
    def handle_hover(self, pw: _PageWidget, pt: QPointF):
        if self.model is None:
            return
        # Re vao dau duong/mui ten dang chon -> con tro keo dai/ngan
        if self._endpoint_at(pw.index, pt) is not None:
            pw.setCursor(Qt.CursorShape.SizeFDiagCursor)
            return
        if self.tool != "pan":
            return
        # Re vao ghi chu minh them -> con tro di chuyen (keo duoc ngay)
        if self._hit_annot(pw.index, pt) is not None:
            pw.setCursor(Qt.CursorShape.SizeAllCursor)
            return
        # wait=False: dang render trang nang thi bo qua, KHONG cho khoa pdfium
        # (tranh dung giao dien khi re chuot luc chuyen trang)
        idx = -1
        for tol in (5, 12):
            idx = self.model.text_hit(pw.index, pt.x(), pt.y(), tol=tol,
                                      wait=False)
            if idx >= 0:
                break
        pw.setCursor(Qt.CursorShape.IBeamCursor if idx >= 0
                     else Qt.CursorShape.OpenHandCursor)

    # ----- Xu ly chuot (tra ve True neu da xu ly) -----
    def handle_press(self, pw: _PageWidget, pt: QPointF, event) -> bool:
        if self.model is None:
            return False
        self.flush_pending_edits()
        if event.button() == Qt.MouseButton.RightButton:
            if self.tool == "pan":
                # Chuot phai trung ghi chu minh them -> menu (sua/xoa/mau...)
                a = self._hit_annot(pw.index, pt)
                if a is not None:
                    self._set_selected((pw.index, a))
                    self._show_annot_menu(pw, a, event)
                    return True
                if self._tsel_text.strip():
                    menu = QMenu(self)
                    act_copy = menu.addAction("Copy chữ đã chọn\tCtrl+C")
                    if menu.exec(event.globalPosition().toPoint()) == act_copy:
                        self.copy_selected_text()
                    return True
            if self.tool == "select":
                a = self._hit_annot(pw.index, pt)
                if a is not None:
                    self._set_selected((pw.index, a))
                    self._show_annot_menu(pw, a, event)
                    return True
                obj = self._hit_native_safe(pw.index, pt)
                if obj is not None:
                    self._set_selected(None)
                    self._set_native_sel((pw.index, [obj]))
                    self._show_native_menu(pw, event)
                    return True
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        # Keo diem 2 dau duong/mui ten dang chon -> keo dai/ngan (moi cong cu)
        ep = self._endpoint_at(pw.index, pt)
        if ep is not None:
            self._endpoint_drag = ep      # (annot, chi_so_diem)
            self._drag_start = pt
            a = ep[0]
            self._endpoint_before = list(a.points)
            return True

        if self.tool == "pan":
            # Bam trung GHI CHU minh them (chu/hinh/che trang) -> chon + keo
            # di chuyen ngay, khong can chuyen sang cong cu Chon.
            a = self._hit_annot(pw.index, pt)
            if a is not None:
                self.clear_text_selection()
                self._set_native_sel(None)
                self._set_selected((pw.index, a))
                self._drag_start = pt
                self._annot_start = (a.x, a.y)
                self._moving = True
                return True
            self.clear_text_selection()
            # Do 2 muc dung sai de bat dau quet duoc ca khi bam trung
            # phan gach chan ngay duoi chan chu
            idx = -1
            for tol in (5, 12):
                idx = self.model.text_hit(pw.index, pt.x(), pt.y(), tol=tol)
                if idx >= 0:
                    break
            if idx >= 0:
                self._tsel_page = pw.index
                self._tsel_anchor = self._tsel_focus = idx
                self._tsel_dragging = True
            else:
                self._panning = True
                self._pan_start = QCursor.pos()
                self._pan_sb = (self.horizontalScrollBar().value(),
                                self.verticalScrollBar().value())
                pw.setCursor(Qt.CursorShape.ClosedHandCursor)
            return True

        if self.tool == "select":
            ctrl = bool(getattr(event, "modifiers", lambda: None)()
                        and event.modifiers() & Qt.KeyboardModifier.ControlModifier)
            if ctrl:
                # Ctrl+bam: them/bo tung doi tuong vao nhom chon
                obj = self._hit_native_safe(pw.index, pt)
                if obj is not None:
                    self._set_selected(None)
                    cur = self._native_sel
                    if cur is not None and cur[0] == pw.index:
                        lst = list(cur[1])
                        for existing in lst:
                            if existing.obj_index == obj.obj_index:
                                lst.remove(existing)
                                break
                        else:
                            lst.append(obj)
                        self._set_native_sel((pw.index, lst) if lst else None)
                    else:
                        self._set_native_sel((pw.index, [obj]))
                return True  # ctrl+bam cho trong: giu nguyen nhom dang chon
            a = self._hit_annot(pw.index, pt)
            if a is not None:
                self._set_native_sel(None)
                self._set_selected((pw.index, a))
                self._drag_start = pt
                self._annot_start = (a.x, a.y)
                self._moving = True
                return True
            self._set_selected(None)
            # Bam TRONG khung bao cua vung dang chon -> keo ca vung di chuyen
            cur = self._native_sel
            if cur is not None and cur[0] == pw.index and cur[1]:
                x0 = min(o.x for o in cur[1])
                y0 = min(o.y for o in cur[1])
                x1 = max(o.x + o.w for o in cur[1])
                y1 = max(o.y + o.h for o in cur[1])
                if x0 - 3 <= pt.x() <= x1 + 3 and y0 - 3 <= pt.y() <= y1 + 3:
                    self._drag_start = pt
                    self._native_moving = True
                    return True
            # Con lai: KEO = khoanh chon ca vung (marquee); BAM 1 phat = chon
            # 1 doi tuong. Nho doi tuong duoi con tro de xu ly khi chi bam.
            self._pending_click_obj = self._hit_native_safe(pw.index, pt)
            self._set_native_sel(None)
            self.band_mode = "select"
            self._band_page = pw.index
            self._band_origin = pt
            self._band_rect = QRectF(pt, pt)
            pw.update()
            return True

        if self.tool == "erase":
            self._set_selected(None)
            self._set_native_sel(None)
            self.band_mode = "erase"
            self._band_page = pw.index
            self._band_origin = pt
            self._band_rect = QRectF(pt, pt)
            pw.update()
            return True

        if self.tool == "text":
            self._create_text(pw.index, pt)
            return True

        if self.tool in DRAW_TOOLS:
            self._drag_start = pt
            self._draft_page = pw.index
            if self.tool in ("line", "arrow", "pen"):
                self._draft = Annot(kind=self.tool,
                                    points=[(pt.x(), pt.y())],
                                    color=self.annot_color,
                                    width=self.annot_width)
            elif self.tool == "cover":
                self._draft = Annot(kind="whiteout", x=pt.x(), y=pt.y(),
                                    w=0, h=0, color="#FFFFFF")
            else:
                self._draft = Annot(kind=self.tool, x=pt.x(), y=pt.y(),
                                    w=0, h=0, color=self.annot_color,
                                    width=self.annot_width)
            pw.update()
            return True
        return False

    def handle_move(self, pw: _PageWidget, pt: QPointF) -> bool:
        if self._endpoint_drag is not None:
            a, i = self._endpoint_drag
            a.points[i] = (pt.x(), pt.y())
            if self._selected is not None and self._selected[0] < len(self._pages):
                self._pages[self._selected[0]].update()
            return True
        if self._panning:
            delta = QCursor.pos() - self._pan_start
            self.horizontalScrollBar().setValue(self._pan_sb[0] - delta.x())
            self.verticalScrollBar().setValue(self._pan_sb[1] - delta.y())
            return True
        if self._tsel_dragging:
            if pw.index == self._tsel_page:
                # Mo rong dan vung bam chu: khong dut chon khi re qua
                # gach chan, khoang trang giua cac tu hay lech dong.
                # wait=False de keo chon khong dung khi render nen ban.
                idx = -1
                for tol in (6, 14, 28):
                    idx = self.model.text_hit(pw.index, pt.x(), pt.y(),
                                              tol=tol, wait=False)
                    if idx >= 0:
                        break
                if idx >= 0:
                    self._tsel_focus = idx
                    self._update_text_selection()
            return True
        if self._band_rect is not None and self._band_origin is not None:
            if pw.index == self._band_page:
                x0, y0 = self._band_origin.x(), self._band_origin.y()
                self._band_rect = QRectF(min(x0, pt.x()), min(y0, pt.y()),
                                         abs(pt.x() - x0), abs(pt.y() - y0))
                pw.update()
            return True
        if self._native_moving and self._native_sel is not None \
                and self._drag_start is not None:
            if self._native_sel[0] == pw.index:
                self._native_delta = QPointF(pt.x() - self._drag_start.x(),
                                             pt.y() - self._drag_start.y())
                pw.update()
            return True
        if self._moving and self._selected is not None and self._drag_start is not None:
            idx, a = self._selected
            if idx == pw.index:
                a.move_by(pt.x() - self._drag_start.x(),
                          pt.y() - self._drag_start.y())
                self._drag_start = pt
                pw.update()
            return True
        if self._draft is not None and self._drag_start is not None \
                and pw.index == self._draft_page:
            if self._draft.kind == "pen":
                self._draft.points.append((pt.x(), pt.y()))
            elif self._draft.kind in ("line", "arrow"):
                self._draft.points = [self._draft.points[0], (pt.x(), pt.y())]
            else:
                x0, y0 = self._drag_start.x(), self._drag_start.y()
                self._draft.x = min(x0, pt.x())
                self._draft.y = min(y0, pt.y())
                self._draft.w = abs(pt.x() - x0)
                self._draft.h = abs(pt.y() - y0)
            pw.update()
            return True
        return False

    def handle_release(self, pw: _PageWidget, pt: QPointF) -> bool:
        if self._endpoint_drag is not None:
            a, _i = self._endpoint_drag
            before = self._endpoint_before
            self._endpoint_drag = None
            self._endpoint_before = None
            if before is not None and before != a.points:
                def _undo():
                    a.points = list(before)
                self.model.push_undo("chỉnh đường vẽ", _undo)
                self._mark_changed()
            return True
        if self._panning:
            self._panning = False
            pw.setCursor(Qt.CursorShape.OpenHandCursor)
            return True
        if self._tsel_dragging:
            self._tsel_dragging = False
            if self._tsel_anchor == self._tsel_focus:
                self.clear_text_selection()
            return True
        if self._band_rect is not None:
            band, page = self._band_rect, self._band_page
            mode = self.band_mode
            self._band_rect = None
            self._band_origin = None
            if band.width() > 3 and band.height() > 3:
                if mode == "erase":
                    if page < len(self._pages):
                        self._pages[page].update()
                    self._do_erase(page, band)
                    return True
                objs = self.model.natives_in_region(
                    page, band.x(), band.y(), band.width(), band.height())
                self._set_native_sel((page, objs) if objs else None)
            elif mode == "select":
                # Bam (khong keo) -> chon 1 doi tuong tai diem bam
                obj = getattr(self, "_pending_click_obj", None)
                if obj is not None:
                    sel = [obj]
                    # Chu vo manh (file xuat loi) -> gom ca dong de keo khong xe
                    if obj.type == pdfium_c.FPDF_PAGEOBJ_TEXT:
                        try:
                            sel = self.model.text_cluster(page, [obj]) or [obj]
                        except Exception:
                            sel = [obj]
                    self._set_native_sel((page, sel))
            self._pending_click_obj = None
            if page < len(self._pages):
                self._pages[page].update()
            return True
        if self._native_moving:
            self._native_moving = False
            self._drag_start = None
            dx, dy = self._native_delta.x(), self._native_delta.y()
            self._native_delta = QPointF(0, 0)
            if self._native_sel is not None and (abs(dx) > 0.5 or abs(dy) > 0.5):
                idx, objs = self._native_sel
                try:
                    self.model.move_natives(idx, objs, dx, dy)
                    for obj in objs:
                        obj.x += dx
                        obj.y += dy
                    self._refresh_page_render(idx)
                    self._mark_changed()
                except FriendlyError as e:
                    QMessageBox.warning(self, "Không di chuyển được", str(e))
            elif self._native_sel is not None:
                self._pages[self._native_sel[0]].update()
            return True
        if self._moving:
            self._moving = False
            self._drag_start = None
            if self._selected is not None:
                idx, a = self._selected
                sx, sy = getattr(self, "_annot_start", (a.x, a.y))
                dx, dy = a.x - sx, a.y - sy
                if abs(dx) > 0.01 or abs(dy) > 0.01:
                    self.model.push_undo(
                        "di chuyển ghi chú", lambda: a.move_by(-dx, -dy))
            self._mark_changed()
            return True
        if self._draft is not None:
            a = self._draft
            self._draft = None
            self._drag_start = None
            x, y, w, h = a.bbox()
            big_enough = (w > 2 or h > 2) if a.kind != "pen" else len(a.points) >= 3
            if big_enough and pw.index < self.model.page_count:
                # Che trang: lay mau NEN quanh vung de che khop nen (file scan)
                if a.kind == "whiteout":
                    bg = self.model.sample_bg_color(self._draft_page, x, y, w, h)
                    if bg:
                        a.color = bg
                ref = self.model.pages[self._draft_page]
                ref.annots.append(a)
                desc = "che trắng vùng" if a.kind == "whiteout" else "vẽ/đánh dấu"
                self.model.push_undo(
                    desc, lambda: a in ref.annots and ref.annots.remove(a))
                self._mark_changed()
            pw.update()
            self.toolFinished.emit()
            return True
        return False

    # ----- Xoa vung (xoa ngay, khong hoi) -----
    def _do_erase(self, page: int, band: QRectF):
        n = self.model.erase_region(page, band.x(), band.y(),
                                    band.width(), band.height())
        if n:
            self._refresh_page_render(page)
            self._mark_changed()
            QToolTip.showText(QCursor.pos(),
                              f"Đã xóa {n} chữ/hình trong vùng (Ctrl+Z để hoàn tác)",
                              self, QRect(), 3000)
        else:
            QToolTip.showText(QCursor.pos(),
                              "Vùng quét không có chữ/hình xóa được — "
                              "với file scan hãy dùng công cụ \"Che trắng\"",
                              self, QRect(), 4000)

    def handle_double_click(self, pw: _PageWidget, pt: QPointF) -> bool:
        if self.model is None:
            return False
        if self.tool == "pan":
            # Bam dup vao chu MINH THEM -> sua noi dung luon
            a = self._hit_annot(pw.index, pt)
            if a is not None and a.kind == "text":
                self._edit_text(pw.index, a)
                return True
            idx = self.model.text_hit(pw.index, pt.x(), pt.y())
            if idx >= 0:
                a, b = self.model.word_at(pw.index, idx)
                self._tsel_page = pw.index
                self._tsel_anchor, self._tsel_focus = a, b
                self._update_text_selection()
                return True
            return False
        if self.tool != "select":
            return False
        a = self._hit_annot(pw.index, pt)
        if a is not None and a.kind == "text":
            self._edit_text(pw.index, a)
            return True
        obj = self._hit_native_safe(pw.index, pt)
        if obj is not None and obj.text:
            self._set_native_sel((pw.index, [obj]))
            self._edit_native_text(pw.index, obj)
            return True
        return False

    # ----- Chu (ghi chu) -----
    def _create_text(self, index: int, pt: QPointF):
        from ..config import config
        from .dialogs.text_annot import TextAnnotDialog
        dlg = TextAnnotDialog(
            self, title="Thêm chữ",
            font=config.get("annot_font", "Arial"),
            size=config.get("annot_font_size", 14),
            color=self.annot_color,
            bg=config.get("annot_bg", ""))
        if not dlg.exec():
            return
        v = dlg.values()
        if not v["text"]:
            return
        config.set("annot_font", v["font"])
        config.set("annot_font_size", v["size"])
        config.set("annot_bg", v["bg"])
        a = Annot(kind="text", x=pt.x(), y=pt.y(), text=v["text"],
                  color=v["color"], font_size=v["size"], font=v["font"],
                  bg_color=v["bg"])
        a.w, a.h = measure_text(a.text, a.font_size, a.font)
        ref = self.model.pages[index]
        ref.annots.append(a)
        self.model.push_undo(
            "thêm chữ", lambda: a in ref.annots and ref.annots.remove(a))
        self._pages[index].update()
        self._mark_changed()
        self.toolFinished.emit()

    def _edit_text(self, index: int, a: Annot):
        from .dialogs.text_annot import TextAnnotDialog
        dlg = TextAnnotDialog(
            self, title="Sửa chữ", text=a.text,
            font=getattr(a, "font", "Arial"), size=a.font_size,
            color=a.color, bg=getattr(a, "bg_color", ""))
        if not dlg.exec():
            return
        v = dlg.values()
        ref = self.model.pages[index]
        old = (a.text, a.w, a.h, a.color, a.font_size,
               getattr(a, "font", "Arial"), getattr(a, "bg_color", ""))
        if not v["text"]:
            pos = ref.annots.index(a) if a in ref.annots else 0
            if a in ref.annots:
                ref.annots.remove(a)
            self.model.push_undo("xóa ghi chú",
                                 lambda: ref.annots.insert(pos, a))
            self._selected = None
        else:
            a.text = v["text"]
            a.color = v["color"]
            a.font_size = v["size"]
            a.font = v["font"]
            a.bg_color = v["bg"]
            a.w, a.h = measure_text(a.text, a.font_size, a.font)

            def _undo():
                (a.text, a.w, a.h, a.color, a.font_size,
                 a.font, a.bg_color) = old
            self.model.push_undo("sửa ghi chú", _undo)
        self._pages[index].update()
        self._mark_changed()

    def _edit_native_text(self, index: int, obj: NativeObj):
        old = obj.text.replace("\r\n", "\n").replace("\r", "\n").strip()
        text, ok = QInputDialog.getMultiLineText(
            self, "Sửa chữ trong file",
            "Nội dung mới (dùng font sẵn có của file — nếu font thiếu ký tự,\n"
            "chữ có thể không hiện; khi đó hãy xóa rồi dùng \"Thêm chữ\"):",
            old)
        if not ok or text.strip() == old:
            return
        try:
            if text.strip():
                self.model.set_native_text(index, obj, text.strip())
                obj.text = text.strip()
            else:
                self.model.delete_natives(index, [obj])
                self._native_sel = None
        except FriendlyError as e:
            QMessageBox.warning(self, "Không sửa được", str(e))
            return
        self._refresh_page_render(index)
        self._mark_changed()

    def _show_annot_menu(self, pw: _PageWidget, a: Annot, event):
        menu = QMenu(self)
        act_edit = menu.addAction("Sửa nội dung...") if a.kind == "text" else None
        act_del = menu.addAction("Xóa")
        chosen = menu.exec(event.globalPosition().toPoint())
        if chosen is None:
            return
        if act_edit is not None and chosen == act_edit:
            self._edit_text(pw.index, a)
        elif chosen == act_del:
            self.delete_selected()

    def _show_native_menu(self, pw: _PageWidget, event):
        if self._native_sel is None:
            return
        objs = self._native_sel[1]
        menu = QMenu(self)
        act_edit = None
        if len(objs) == 1 and objs[0].text:
            act_edit = menu.addAction("Sửa chữ...")
        label = (f"Xóa {len(objs)} đối tượng" if len(objs) > 1
                 else f"Xóa {objs[0].type_name} này")
        act_del = menu.addAction(label)
        chosen = menu.exec(event.globalPosition().toPoint())
        if chosen is None:
            return
        if act_edit is not None and chosen == act_edit:
            self._edit_native_text(pw.index, objs[0])
        elif chosen == act_del:
            self.delete_selected()

    def apply_color_to_selection(self, color: str):
        if self._selected is not None:
            idx, a = self._selected
            old = a.color
            a.color = color

            def _undo():
                a.color = old
            self.model.push_undo("đổi màu", _undo)
            self._pages[idx].update()
            self._mark_changed()

    def apply_width_to_selection(self, width: float):
        """Doi do day net cua hinh dang chon (duong/mui ten/khung/but)."""
        if self._selected is not None:
            idx, a = self._selected
            if a.kind in ("line", "arrow", "pen", "rect", "ellipse",
                          "hl-ellipse"):
                old = a.width
                a.width = width

                def _undo():
                    a.width = old
                self.model.push_undo("đổi độ dày nét", _undo)
                self._pages[idx].update()
                self._mark_changed()

    # ---------- Su kien ----------
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_C and \
                event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if self.copy_selected_text():
                return
        # Mui ten: di chuyen doi tuong dang chon (Shift = buoc 10pt)
        arrows = {Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0),
                  Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1)}
        if event.key() in arrows and self.has_selection:
            dx, dy = arrows[event.key()]
            step = 10.0 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0
            self._nudge(dx * step, dy * step)
            return
        # Khong chon gi: mui ten trai/phai = chuyen trang truoc/sau
        if event.key() == Qt.Key.Key_Right:
            self.goto_page(self._current_page + 1)
            return
        if event.key() == Qt.Key.Key_Left:
            self.goto_page(self._current_page - 1)
            return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.flush_pending_edits()
            if self.delete_selected():
                return
        if event.key() == Qt.Key.Key_Escape:
            self.flush_pending_edits()
            self._set_selected(None)
            self._set_native_sel(None)
            self._draft = None
            self._band_rect = None
            self.clear_text_selection()
            if self.tool != "pan":
                self.panRequested.emit()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_mode is not None and self._pages:
            anchor = self._capture_anchor()
            self._apply_fit()
            self.generation += 1
            self._resize_pages()
            self._restore_anchor(anchor)
            self.zoomChanged.emit(self.zoom)
        self._update_timer.start()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.set_zoom(self.zoom * 1.1)
            else:
                self.set_zoom(self.zoom / 1.1)
            event.accept()
            return
        super().wheelEvent(event)
