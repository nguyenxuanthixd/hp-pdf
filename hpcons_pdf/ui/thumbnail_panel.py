"""Panel thumbnail: luoi tu xep theo chieu rong (keo panel rong ra se
hien nhieu cot), so trang nam DUOI anh, keo-tha de sap xep lai trang."""
from __future__ import annotations

from PyQt6.QtCore import QItemSelectionModel, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (QAbstractItemView, QListView, QListWidget,
                             QListWidgetItem, QMenu)

THUMB_W = 110
THUMB_H = int(THUMB_W * 1.42)
CELL_W = THUMB_W + 26
CELL_H = THUMB_H + 30  # cho nhan so trang ben duoi

_ROLE_POS = Qt.ItemDataRole.UserRole


class ThumbnailPanel(QListWidget):
    orderChanged = pyqtSignal(list)          # thu tu moi (chi so cu)
    pageActivated = pyqtSignal(int)
    rotateRequested = pyqtSignal(list, int)  # (danh sach trang, goc)
    deleteRequested = pyqtSignal(list)
    extractRequested = pyqtSignal(list)
    pdfFilesDropped = pyqtSignal(list, int)  # (file paths, vi tri tha 0-based; -1=cuoi)
    copyRequested = pyqtSignal(list)         # copy cac trang da chon
    pasteRequested = pyqtSignal(int)         # dan vao vi tri (0-based)

    # Ham do MainWindow gan vao: tra ve so trang dang co trong clipboard
    clipboard_count = staticmethod(lambda: 0)

    def __init__(self, render_thread, parent=None):
        super().__init__(parent)
        self._rt = render_thread
        self._rt.rendered.connect(self._on_rendered)
        self.model_doc = None
        self.generation = 0
        # Lazy render: chi render thumbnail cua TAB DANG XEM. Tab an khong
        # render (tranh tranh khoa pdfium lam trang dang xem giat). Nho cac
        # trang da render de khi quay lai tab khong render lai tu dau.
        # Mac dinh CHUA active -> MainWindow._on_tab_changed kich hoat tab
        # dang xem; tab tao ra nhung chua duoc xem se khong render.
        self._active = False
        self._rendered_idx: set[int] = set()
        self._press_row = -1
        self._press_pos = None
        self._manual_drag = False
        self._drag_pos = None
        # Tu cuon khi keo trang toi sat mep tren/duoi panel
        self._autoscroll = QTimer(self)
        self._autoscroll.setInterval(30)
        self._autoscroll.timeout.connect(self._autoscroll_tick)
        self._autoscroll_dy = 0
        # Luoi: xep tu trai sang phai, tu xuong dong theo chieu rong panel
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setIconSize(QSize(THUMB_W, THUMB_H))
        # Chieu cao o theo ty le tung trang (trang ngang khong bi thua
        # khoang trang ben duoi) -> khong dung luoi co dinh
        # TAT hoan toan DnD cua Qt: keo SAP XEP trang do chinh app xu ly bang
        # chuot (mousePress/Move/Release), con tha FILE tu ngoai de CUA SO
        # CHINH nhan (MainWindow.dropEvent) roi quyet dinh gop hay mo tab.
        # (De acceptDrops o day thi Qt route drop toi viewport, override bi
        # bo qua -> file khong gop duoc.)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setAcceptDrops(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setMinimumWidth(CELL_W + 24)
        self.setSpacing(2)
        self.itemClicked.connect(self._on_item_clicked)
        self.model().rowsMoved.connect(lambda *_: self._sync_after_move())
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

    # ---------- Nap du lieu ----------
    def set_model(self, model_doc):
        self.model_doc = model_doc
        self.reload()

    def set_active(self, active: bool):
        """Danh dau tab dang xem hay bi an. Active -> render nhung thumbnail
        con thieu; an -> huy yeu cau dang cho de nhuong khoa pdfium cho tab
        dang xem (thumbnail da render van giu nguyen)."""
        self._active = active
        if self.model_doc is None:
            return
        if active:
            self._request_missing()
        else:
            self._rt.clear_pending("thumb", self.model_doc)

    def reload(self):
        self.generation += 1
        self._rt.clear_pending("thumb", self.model_doc)
        self._rendered_idx.clear()
        self.blockSignals(True)
        self.clear()
        self.blockSignals(False)
        if self.model_doc is None:
            return
        for i in range(self.model_doc.page_count):
            it = QListWidgetItem(self._placeholder_icon(i), str(i + 1))
            it.setData(_ROLE_POS, i)
            it.setTextAlignment(Qt.AlignmentFlag.AlignHCenter
                                | Qt.AlignmentFlag.AlignBottom)
            it.setSizeHint(self._cell_size(i))
            self.addItem(it)
        if self._active:
            self._request_all()

    def _request_missing(self):
        """Render nhung trang chua co thumbnail (khi kich hoat lai tab)."""
        if self.model_doc is None:
            return
        for i in range(self.model_doc.page_count):
            if i in self._rendered_idx:
                continue
            w_pt, h_pt = self.model_doc.page_size(i)
            scale = min(THUMB_W / max(w_pt, 1), THUMB_H / max(h_pt, 1))
            self._rt.request(self.model_doc, i, scale, "thumb", self.generation)

    def _cell_size(self, i: int) -> QSize:
        """Kich thuoc o = anh thu nho theo ty le trang + cho nhan so."""
        w_pt, h_pt = self.model_doc.page_size(i)
        scale = min(THUMB_W / max(w_pt, 1), THUMB_H / max(h_pt, 1))
        return QSize(CELL_W, int(h_pt * scale) + 26)

    def refresh_page(self, i: int):
        """Render lai thumbnail 1 trang (sau khi noi dung thay doi)."""
        if self.model_doc is None or i >= self.model_doc.page_count:
            return
        self._rendered_idx.discard(i)  # buoc render lai
        if not self._active:
            return  # tab an -> de dan khi kich hoat lai
        w_pt, h_pt = self.model_doc.page_size(i)
        scale = min(THUMB_W / max(w_pt, 1), THUMB_H / max(h_pt, 1))
        self._rt.request(self.model_doc, i, scale, "thumb", self.generation)

    def _request_all(self):
        for i in range(self.model_doc.page_count):
            w_pt, h_pt = self.model_doc.page_size(i)
            scale = min(THUMB_W / max(w_pt, 1), THUMB_H / max(h_pt, 1))
            self._rt.request(self.model_doc, i, scale, "thumb", self.generation)

    def _placeholder_icon(self, i: int) -> QIcon:
        w_pt, h_pt = self.model_doc.page_size(i)
        ratio = min(THUMB_W / max(w_pt, 1), THUMB_H / max(h_pt, 1))
        w, h = max(int(w_pt * ratio), 20), max(int(h_pt * ratio), 20)
        pm = QPixmap(w, h)
        pm.fill(QColor("#FFFFFF"))
        p = QPainter(pm)
        p.setPen(QColor("#C8CCD0"))
        p.drawRect(0, 0, pm.width() - 1, pm.height() - 1)
        p.end()
        return QIcon(pm)

    def _on_rendered(self, purpose: str, index: int, gen: int, img: QImage,
                     model=None):
        if purpose != "thumb" or gen != self.generation \
                or model is not self.model_doc:
            return
        pm = QPixmap.fromImage(img)
        # item co the da doi vi tri -> tim theo _ROLE_POS
        for row in range(self.count()):
            it = self.item(row)
            if it.data(_ROLE_POS) == index:
                it.setIcon(QIcon(pm))
                self._rendered_idx.add(index)
                break

    # ---------- Keo tha ----------
    @staticmethod
    def _pdf_urls(event) -> list[str]:
        if not event.mimeData().hasUrls():
            return []
        return [u.toLocalFile() for u in event.mimeData().urls()
                if u.toLocalFile().lower().endswith(".pdf")]

    def _on_item_clicked(self, it):
        # Ctrl/Shift+bam la de CHON nhieu trang -> khong nhay trang (tranh
        # cuon lam mat phuong huong). Bam thuong moi nhay toi trang do.
        from PyQt6.QtWidgets import QApplication
        mods = QApplication.keyboardModifiers()
        if mods & (Qt.KeyboardModifier.ControlModifier
                   | Qt.KeyboardModifier.ShiftModifier):
            return
        self.pageActivated.emit(self.row(it))

    # ---------- Keo sap xep trang (tu xu ly chuot, khong dung DnD cua Qt) ----
    def mousePressEvent(self, event):
        # Ghi lai trang bam de biet keo 1 trang hay ca nhom dang chon
        pos = event.position().toPoint()
        it = self.itemAt(pos)
        row = self.row(it) if it is not None else -1
        self._press_row = row
        self._press_pos = pos
        self._manual_drag = False
        mods = event.modifiers()
        # Shift+bam: chon DAI TRANG LIEN TUC theo thu tu (che do luoi cua Qt
        # chon theo hinh chu nhat 2D -> khong hop voi thumbnail). Tu xu ly.
        if (row >= 0 and (mods & Qt.KeyboardModifier.ShiftModifier)
                and not (mods & Qt.KeyboardModifier.ControlModifier)):
            anchor = self.currentRow()
            if anchor < 0:
                anchor = row
            lo, hi = sorted((anchor, row))
            self.blockSignals(True)
            self.clearSelection()
            for r in range(lo, hi + 1):
                self.item(r).setSelected(True)
            self.setCurrentRow(row, QItemSelectionModel.SelectionFlag.NoUpdate)
            self.blockSignals(False)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (event.buttons() & Qt.MouseButton.LeftButton
                and self._press_row >= 0 and self._press_pos is not None):
            from PyQt6.QtWidgets import QApplication
            pos = event.position().toPoint()
            if not self._manual_drag and \
                    (pos - self._press_pos).manhattanLength() > \
                    QApplication.startDragDistance():
                self._manual_drag = True
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            if self._manual_drag:
                self._drag_pos = pos
                # Cham diem tha du kien bang khung focus
                it = self.itemAt(pos)
                if it is not None:
                    self.selectionModel().setCurrentIndex(
                        self.indexFromItem(it),
                        QItemSelectionModel.SelectionFlag.NoUpdate)
                self._update_autoscroll(pos)
                event.accept()
                return
        super().mouseMoveEvent(event)

    def _update_autoscroll(self, pos):
        """Keo toi sat mep tren/duoi -> tu cuon thanh trang theo con tro."""
        margin = 44
        h = self.viewport().height()
        y = pos.y()
        if y < margin:
            # cang gan mep cang cuon nhanh
            self._autoscroll_dy = -max(6, (margin - y) // 2)
        elif y > h - margin:
            self._autoscroll_dy = max(6, (y - (h - margin)) // 2)
        else:
            self._autoscroll_dy = 0
        if self._autoscroll_dy and not self._autoscroll.isActive():
            self._autoscroll.start()
        elif not self._autoscroll_dy and self._autoscroll.isActive():
            self._autoscroll.stop()

    def _autoscroll_tick(self):
        if not self._manual_drag or not self._autoscroll_dy:
            self._autoscroll.stop()
            return
        sb = self.verticalScrollBar()
        sb.setValue(sb.value() + self._autoscroll_dy)
        # cap nhat lai o dich theo vi tri con tro hien tai
        if self._drag_pos is not None:
            it = self.itemAt(self._drag_pos)
            if it is not None:
                self.selectionModel().setCurrentIndex(
                    self.indexFromItem(it),
                    QItemSelectionModel.SelectionFlag.NoUpdate)

    def _drop_target_row(self, pos) -> int:
        """Vi tri chen tu diem tha: nua sau cua o -> chen SAU o do."""
        it = self.itemAt(pos)
        if it is None:
            return self.count()
        row = self.row(it)
        rect = self.visualItemRect(it)
        if pos.x() > rect.center().x():
            row += 1
        return row

    def mouseReleaseEvent(self, event):
        if self._manual_drag and event.button() == Qt.MouseButton.LeftButton:
            self._manual_drag = False
            self._autoscroll.stop()
            self._autoscroll_dy = 0
            self.unsetCursor()
            target = self._drop_target_row(event.position().toPoint())
            sel = self.selected_pages()
            origin = self._press_row
            self._press_row = -1
            rows = sel if origin in sel else [origin]
            self.setState(QAbstractItemView.State.NoState)
            self.move_rows_to(rows, target)
            event.accept()
            return
        self._press_row = -1
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if self._pdf_urls(event):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._pdf_urls(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):
        paths = self._pdf_urls(event)
        if paths:
            # Tha file PDF tu ben ngoai -> gop vao tai lieu tai vi tri tha
            it = self.itemAt(event.position().toPoint())
            row = self.row(it) if it is not None else -1
            event.acceptProposedAction()
            self.pdfFilesDropped.emit(paths, row)
            return
        if event.source() is self:
            # Keo sap xep trang. Phan biet:
            # - Keo trang NAM TRONG nhom dang chon -> di chuyen ca nhom.
            # - Keo trang NGOAI nhom -> chi di chuyen dung trang do
            #   (nhom dang chon 2,4,6 khong bi keo theo khi doi cho trang 7).
            it = self.itemAt(event.position().toPoint())
            target = self.row(it) if it is not None else self.count()
            sel = self.selected_pages()
            origin = getattr(self, "_press_row", -1)
            if origin >= 0 and origin in sel:
                rows = sel
            elif origin >= 0:
                rows = [origin]
            else:
                rows = sel
            if self.move_rows_to(rows, target):
                event.acceptProposedAction()
                return
            event.ignore()
            return
        super().dropEvent(event)
        # Mot so kieu view khong phat rowsMoved -> dong bo lai sau khi tha
        QTimer.singleShot(0, self._sync_after_move)

    def move_rows_to(self, rows: list[int], target: int) -> bool:
        """Di chuyen cac trang `rows` (co the RAI RAC) den vi tri `target`.

        Cac trang duoc gom lai theo dung thu tu hien tai roi chen truoc trang
        dang o vi tri `target`. Tra ve True neu co thay doi.
        """
        rows = sorted(set(r for r in rows if 0 <= r < self.count()))
        if not rows:
            return False
        # Vi tri chen sau khi go = target tru so trang bi go nam TRUOC target
        insert_at = target - sum(1 for r in rows if r < target)
        items = [self.takeItem(r) for r in reversed(rows)]
        items.reverse()  # ve lai thu tu tang dan nhu ban dau
        insert_at = max(0, min(insert_at, self.count()))
        self.blockSignals(True)
        for k, itm in enumerate(items):
            self.insertItem(insert_at + k, itm)
        self.blockSignals(False)
        self.clearSelection()
        for k in range(len(items)):
            self.item(insert_at + k).setSelected(True)
        self._sync_after_move()
        return True

    def _sync_after_move(self):
        order = [self.item(r).data(_ROLE_POS) for r in range(self.count())]
        if order == list(range(self.count())):
            return  # khong doi thu tu (hoac da dong bo roi)
        for r in range(self.count()):
            self.item(r).setData(_ROLE_POS, r)
            self.item(r).setText(str(r + 1))
        self.orderChanged.emit(order)
        for r in range(self.count()):
            self.item(r).setSizeHint(self._cell_size(r))
        # Huy render dang cho (mang chi so cu) va render lai theo thu tu moi
        self.generation += 1
        self._rt.clear_pending("thumb", self.model_doc)
        self._rendered_idx.clear()
        if self.model_doc is not None and self._active:
            self._request_all()

    def selected_pages(self) -> list[int]:
        return sorted(self.row(it) for it in self.selectedItems())

    # ---------- Ban phim ----------
    _NAV_KEYS = (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left,
                 Qt.Key.Key_Right, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown,
                 Qt.Key.Key_Home, Qt.Key.Key_End)

    def keyPressEvent(self, event):
        mods = event.modifiers()
        ctrl = mods & Qt.KeyboardModifier.ControlModifier
        shift = mods & Qt.KeyboardModifier.ShiftModifier
        if event.key() == Qt.Key.Key_Delete and self.selected_pages():
            self.deleteRequested.emit(self.selected_pages())
            return
        if ctrl and event.key() == Qt.Key.Key_C and self.selected_pages():
            self.copyRequested.emit(self.selected_pages())
            return
        if ctrl and event.key() == Qt.Key.Key_V and self.clipboard_count():
            sel = self.selected_pages()
            at = (sel[-1] + 1) if sel else self.count()
            self.pasteRequested.emit(at)
            return
        # Bam phim mui ten / PageUp-Down... trong thanh trang -> nhay trang o
        # khung xem chinh theo. Bo qua khi giu Ctrl/Shift (dang chon nhieu trang).
        if event.key() in self._NAV_KEYS and not ctrl and not shift:
            super().keyPressEvent(event)
            row = self.currentRow()
            if 0 <= row < self.count():
                self.pageActivated.emit(row)
            return
        super().keyPressEvent(event)

    # ---------- Menu chuot phai ----------
    def _show_menu(self, pos):
        if self.model_doc is None or self.count() == 0:
            return
        pages = self.selected_pages()
        if not pages:
            it = self.itemAt(pos)
            if it is None:
                return
            pages = [self.row(it)]
        menu = QMenu(self)
        n = len(pages)
        lbl = f"{n} trang đã chọn" if n > 1 else f"Trang {pages[0] + 1}"
        menu.addSection(lbl)
        act_copy = menu.addAction("Copy trang\tCtrl+C")
        n_clip = self.clipboard_count()
        act_paste = menu.addAction(
            f"Dán {n_clip} trang vào sau\tCtrl+V" if n_clip else "Dán trang\tCtrl+V")
        act_paste.setEnabled(n_clip > 0)
        menu.addSeparator()
        act_l = menu.addAction("Xoay trái 90°")
        act_r = menu.addAction("Xoay phải 90°")
        act_180 = menu.addAction("Xoay 180°")
        menu.addSeparator()
        act_extract = menu.addAction("Trích xuất trang đã chọn...")
        menu.addSeparator()
        act_del = menu.addAction("Xóa trang")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen == act_copy:
            self.copyRequested.emit(pages)
        elif chosen == act_paste:
            self.pasteRequested.emit(pages[-1] + 1)
        elif chosen == act_l:
            self.rotateRequested.emit(pages, 270)
        elif chosen == act_r:
            self.rotateRequested.emit(pages, 90)
        elif chosen == act_180:
            self.rotateRequested.emit(pages, 180)
        elif chosen == act_del:
            self.deleteRequested.emit(pages)
        elif chosen == act_extract:
            self.extractRequested.emit(pages)
