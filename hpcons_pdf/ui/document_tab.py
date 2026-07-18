"""Mot tab tai lieu: panel thumbnail (trai) + khung xem (giua) + logic tim kiem."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QSplitter, QToolButton

from ..core.document import DocumentModel
from .pdf_view import PdfView
from .thumbnail_panel import ThumbnailPanel


class DocumentTab(QSplitter):
    stateChanged = pyqtSignal()  # trang hien tai / so trang / modified thay doi
    sidebarToggleRequested = pyqtSignal()  # bam nut mui ten thu/mo thanh trang

    def __init__(self, model: DocumentModel, render_thread, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.model = model
        self.thumbs = ThumbnailPanel(render_thread)
        self.view = PdfView(render_thread)
        self.addWidget(self.thumbs)
        self.addWidget(self.view)
        self.setStretchFactor(0, 0)
        self.setStretchFactor(1, 1)
        # Cho phep keo rong/hep thanh thumbnail (keo rong -> nhieu cot)
        self.setCollapsible(0, True)
        self.setCollapsible(1, False)
        self.setSizes([170, 1000])

        # Nut mui ten thu/mo thanh trang, noi o GOC TREN-TRAI (luon thay).
        # Gan vao thanh trang khi hien (dung goc), vao khung xem khi an
        # (de con cho bam mo lai). Khong gan truc tiep vao QSplitter vi
        # splitter se coi no la 1 pane va day sang ben.
        self.btn_toggle = QToolButton(self.thumbs)
        self.btn_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle.setFixedSize(16, 46)
        self.btn_toggle.setToolTip("Thu gọn / mở thanh trang (F4)")
        self.btn_toggle.setStyleSheet(
            "QToolButton{border:1px solid #DDE0E3;border-radius:4px;"
            "background:#F5F6F7;color:#4A4F54;font-size:12pt;font-weight:bold;}"
            "QToolButton:hover{background:#E3EFF8;border-color:#1B75BB;}")
        self.btn_toggle.clicked.connect(
            lambda: self.sidebarToggleRequested.emit())
        self.update_toggle_button(True)

        self.view.set_model(model)
        self.thumbs.set_model(model)

        self.thumbs.pageActivated.connect(self.view.goto_page)
        self.thumbs.orderChanged.connect(self._reorder)
        self.thumbs.rotateRequested.connect(self.rotate_pages)
        self.thumbs.deleteRequested.connect(self.delete_pages)
        self.view.pageChanged.connect(self._sync_thumb_selection)
        self.view.pageChanged.connect(lambda _i: self.stateChanged.emit())
        self.view.annotationsChanged.connect(self.stateChanged.emit)
        self.view.pageContentChanged.connect(self._on_page_content_changed)

        # Trang thai tim kiem
        self._search_term = ""
        self._search_page = -1
        self._search_hits: list[int] = []  # cac trang co ket qua (cache theo term)

        # Ghi nho thiet lap in trong PHIEN nay (mat khi dong file -> ve mac dinh)
        self.print_printer = ""
        self.print_devmode = None

    # ---------- Thao tac trang ----------
    def _reorder(self, order: list[int]):
        self.model.reorder(order)
        self.view.reload()
        self.stateChanged.emit()

    def rotate_pages(self, pages: list[int], angle: int):
        self.model.rotate_pages(pages, angle)
        self.refresh()

    def delete_pages(self, pages: list[int]):
        self.model.delete_pages(pages)
        self.refresh()

    def refresh(self):
        """Ve lai toan bo sau khi model thay doi."""
        self.view.reload()
        self.thumbs.reload()
        self.stateChanged.emit()

    def _on_page_content_changed(self, page: int):
        """Noi dung goc thay doi (sua/xoa/di chuyen doi tuong) -> lam moi."""
        self.thumbs.refresh_page(page)
        self.invalidate_search_cache()

    def _sync_thumb_selection(self, page: int):
        """Cuon khung xem qua trang -> keo thumbnail theo cho de theo doi.

        KHONG duoc dong bo (clear + chon 1 trang) khi nguoi dung dang chon
        NHIEU trang (Ctrl/Shift+bam) — neu khong se xoa mat lua chon cua ho.
        """
        if self.thumbs.state() == self.thumbs.State.DraggingState:
            return
        if 0 <= page < self.thumbs.count():
            self.thumbs.scrollToItem(self.thumbs.item(page))
        # Dang chon nhieu trang -> giu nguyen, chi cuon theo doi
        if len(self.thumbs.selected_pages()) > 1:
            return
        if 0 <= page < self.thumbs.count():
            self.thumbs.blockSignals(True)
            # setCurrentRow: chon 1 trang + dat DIEM NEO cho Shift+bam sau nay
            self.thumbs.setCurrentRow(page)
            self.thumbs.blockSignals(False)

    # ---------- Tim kiem ----------
    def search(self, term: str, backwards: bool = False) -> tuple[int, int] | None:
        """Tim va nhay den trang co ket qua ke tiep.

        Tra ve (vi_tri_trong_ds, tong_so_trang_co_kq) hoac None neu khong thay.
        """
        term = term.strip()
        if not term:
            self.clear_search()
            return None
        if term != self._search_term:
            self._search_term = term
            self._search_hits = []
            for i in range(self.model.page_count):
                if self.model.search_page(i, term):
                    self._search_hits.append(i)
            self._search_page = -1
        if not self._search_hits:
            self.clear_search()
            return None
        cur = self.view.current_page
        if self._search_page < 0:
            candidates = [p for p in self._search_hits if p >= cur]
            nxt = candidates[0] if candidates else self._search_hits[0]
        else:
            pos = self._search_hits.index(self._search_page) \
                if self._search_page in self._search_hits else 0
            pos = (pos - 1) % len(self._search_hits) if backwards \
                else (pos + 1) % len(self._search_hits)
            nxt = self._search_hits[pos]
        self._search_page = nxt
        rects = self.model.search_page(nxt, term)
        self.view.set_highlights(nxt, rects)
        self.view.goto_page(nxt)
        return (self._search_hits.index(nxt) + 1, len(self._search_hits))

    def clear_search(self):
        self._search_term = ""
        self._search_page = -1
        self._search_hits = []
        self.view.clear_highlights()

    def invalidate_search_cache(self):
        self._search_term = ""
        self._search_hits = []
        self._search_page = -1

    def update_toggle_button(self, sidebar_visible: bool):
        """Doi chieu mui ten + gan dung noi:
        ‹ = dang hien (gan tren thanh trang, bam de thu),
        › = dang an (gan tren khung xem, bam de mo)."""
        host = self.thumbs if sidebar_visible else self.view
        if self.btn_toggle.parent() is not host:
            self.btn_toggle.setParent(host)
        self.btn_toggle.setText("‹" if sidebar_visible else "›")
        self.btn_toggle.move(2, 2)
        self.btn_toggle.show()
        self.btn_toggle.raise_()

    def rebind_render_thread(self, rt):
        """Chuyen tab sang luong render cua cua so khac (tach/gop cua so)."""
        for comp in (self.view, self.thumbs):
            try:
                comp._rt.rendered.disconnect(comp._on_rendered)
            except TypeError:
                pass
            comp._rt = rt
            rt.rendered.connect(comp._on_rendered)
        self.view.reload()
        self.thumbs.reload()

    def close_document(self):
        self.model.close()
