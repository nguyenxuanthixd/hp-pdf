# -*- coding: utf-8 -*-
"""Test: mui ten, danh dau elip, toolbar sap xep lai, Ctrl+A chon tat ca trang.
Chay: python tests/test_batch6.py
"""
import os
import sys
import faulthandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
faulthandler.dump_traceback_later(60, exit=True)

from fixtures import make_all  # noqa: E402

WORK = make_all()
sample1 = os.path.join(WORK, "hồ sơ thầu 布局.pdf")

from PyQt6.QtCore import QPointF, QTimer, Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from hpcons_pdf.core.annotations import Annot  # noqa: E402
from hpcons_pdf.core.document import DocumentModel  # noqa: E402
from hpcons_pdf.ui.main_window import MainWindow  # noqa: E402

app = QApplication(sys.argv)
win = MainWindow()
win.show()
errors = []


class FakeEvent:
    def __init__(self, button=Qt.MouseButton.LeftButton,
                 mods=Qt.KeyboardModifier.NoModifier):
        self._b = button
        self._m = mods
    def button(self):
        return self._b
    def modifiers(self):
        return self._m


def dark_in(img, box):
    """Dem pixel KHONG trang (muc/net ve mau bat ky)."""
    crop = img.crop(box)
    return sum(1 for (r, g, b) in list(crop.getdata()) if r + g + b < 640)


def run():
    try:
        win.open_path(sample1)
        tab = win.current_tab()
        view = tab.view
        model = tab.model
        pw0 = view._pages[0]
        app.processEvents()

        # ----- Ve mui ten bang chuot -----
        view.set_tool("arrow")
        assert view.handle_press(pw0, QPointF(100, 300), FakeEvent())
        view.handle_move(pw0, QPointF(250, 400))
        view.handle_release(pw0, QPointF(250, 400))
        a = model.pages[0].annots[-1]
        assert a.kind == "arrow" and len(a.points) == 2

        # ----- Danh dau elip -----
        view.set_tool("hl-ellipse")
        view.handle_press(pw0, QPointF(100, 500), FakeEvent())
        view.handle_move(pw0, QPointF(300, 560))
        view.handle_release(pw0, QPointF(300, 560))
        e = model.pages[0].annots[-1]
        assert e.kind == "hl-ellipse" and e.w > 150

        # ----- Nuong vao file: dau mui ten + elip hien tren ban in -----
        out = model.save_as(os.path.join(WORK, "batch6.pdf"))
        m2 = DocumentModel(out)
        img = m2.render_page(0, 1.0)
        # dau mui ten quanh (250,400): phai co pixel dam
        assert dark_in(img, (235, 385, 265, 415)) > 10, "thieu dau mui ten"
        m2.close()

        # ----- Toolbar: Ghep/Tach nam SAU nhom chinh sua; Xoay ra toolbar ---
        from PyQt6.QtWidgets import QToolBar
        tbs = win.findChildren(QToolBar)
        acts = tbs[0].actions()
        texts = [x.text() for x in acts]
        i_rot = texts.index("Xoay trái 90°")
        i_merge = texts.index("Ghép file")
        i_color_area = max(k for k, t in enumerate(texts) if t == "Xóa vùng")
        assert i_rot < i_merge, texts
        assert i_color_area < i_merge, "Ghép file phải nằm sau nhóm chỉnh sửa"

        # ----- Menu Danh dau co 2 kieu -----
        hl_items = [x.text() for x in win.btn_hl.menu().actions()]
        assert "Đánh dấu elip" in hl_items, hl_items
        win._on_hl_picked(win.btn_hl.menu().actions()[1])
        assert view.tool == "hl-ellipse"
        # menu Ve hinh co Mui ten
        shape_items = [x.text() for x in win.btn_shape.menu().actions()]
        assert "Mũi tên" in shape_items

        # ----- Ctrl+A chon tat ca trang -----
        view.setFocus()
        win._select_all_pages()
        assert tab.thumbs.selected_pages() == list(range(6))
        # dang focus o tim kiem -> chon chu, khong doi selection trang
        # (offscreen co the khong cap focus that — chi kiem tra khi co focus)
        tab.thumbs.clearSelection()
        win.ed_search.setFocus()
        app.processEvents()
        if QApplication.focusWidget() is win.ed_search:
            win.ed_search.setText("abc")
            win._select_all_pages()
            assert win.ed_search.selectedText() == "abc"
            assert tab.thumbs.selected_pages() == []

        print("BATCH6 SMOKE: OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        errors.append(e)
        print(f"BATCH6 SMOKE: FAIL {e!r}")
    finally:
        for i in range(win.tabs.count()):
            w = win.tabs.widget(i)
            if hasattr(w, "model"):
                w.model.modified = False
        win.render_thread.stop()
        app.quit()


QTimer.singleShot(200, run)
app.exec()
sys.exit(1 if errors else 0)
