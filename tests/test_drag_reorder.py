# -*- coding: utf-8 -*-
"""Test keo sap xep trang bang CHUOI SU KIEN CHUOT THAT (press/move/release)
tren file DDK cua nguoi dung. Chay: python tests/test_drag_reorder.py
"""
import os
import sys
import faulthandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
faulthandler.dump_traceback_later(90, exit=True)

DDK = os.path.join(ROOT, "DDK - BAO GIA PHAT SINH - 05122025 (1).pdf")
if not os.path.exists(DDK):
    from fixtures import make_all
    DDK = os.path.join(make_all(), "hồ sơ thầu 布局.pdf")

from PyQt6.QtCore import QPointF, QTimer, Qt  # noqa: E402
from PyQt6.QtGui import QMouseEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from hpcons_pdf.ui.main_window import MainWindow  # noqa: E402

app = QApplication(sys.argv)
win = MainWindow()
win.resize(1200, 800)
win.show()
errors = []


def mouse(widget, etype, pos, buttons=Qt.MouseButton.LeftButton):
    ev = QMouseEvent(etype, QPointF(pos), QPointF(widget.mapToGlobal(pos)),
                     Qt.MouseButton.LeftButton, buttons,
                     Qt.KeyboardModifier.NoModifier)
    if etype == QMouseEvent.Type.MouseButtonPress:
        widget.mousePressEvent(ev)
    elif etype == QMouseEvent.Type.MouseMove:
        widget.mouseMoveEvent(ev)
    else:
        widget.mouseReleaseEvent(ev)


def drag_page(thumbs, from_row, to_row):
    """Keo trang from_row tha vao NUA TRUOC cua o to_row (chen truoc no)."""
    r1 = thumbs.visualItemRect(thumbs.item(from_row))
    r2 = thumbs.visualItemRect(thumbs.item(to_row))
    start = r1.center()
    # tha vao me trai/tren cua o dich -> chen TRUOC o dich
    end = r2.center()
    end.setX(r2.left() + 3)
    mouse(thumbs, QMouseEvent.Type.MouseButtonPress, start)
    # vai buoc di chuyen (vuot startDragDistance)
    for f in (0.3, 0.6, 1.0):
        mid = start + (end - start) * f
        mouse(thumbs, QMouseEvent.Type.MouseMove, mid)
    mouse(thumbs, QMouseEvent.Type.MouseButtonRelease, end,
          buttons=Qt.MouseButton.NoButton)
    QApplication.processEvents()


def run():
    try:
        win.open_path(DDK)
        tab = win.current_tab()
        thumbs = tab.thumbs
        model = tab.model
        app.processEvents()
        n = model.page_count
        print("file:", os.path.basename(DDK), "-", n, "trang")
        assert thumbs.count() == n

        # thu tu goc theo _ROLE_POS cua model: dung text trang de doi chieu
        t0 = model.extract_text(0)[:60]
        t1 = model.extract_text(1)[:60]
        t6 = model.extract_text(6)[:60]

        # ---- Keo trang 7 (index 6) len vi tri 2 (chen truoc index 1) ----
        drag_page(thumbs, 6, 1)
        assert model.extract_text(0)[:60] == t0
        assert model.extract_text(1)[:60] == t6, "trang 7 phai len vi tri 2"
        assert model.extract_text(2)[:60] == t1
        assert model.modified
        win.undo()
        app.processEvents()
        assert model.extract_text(1)[:60] == t1

        # ---- Dang chon 2,4,6: keo trang 8 (ngoai nhom) -> chi trang 8 ----
        thumbs.clearSelection()
        for r in (1, 3, 5):
            thumbs.item(r).setSelected(True)
        t7 = model.extract_text(7)[:60]
        drag_page(thumbs, 7, 2)
        assert model.extract_text(2)[:60] == t7, "chi trang 8 duoc di chuyen"
        # 3 trang chon cu khong doi cho: trang 1 van o dau
        assert model.extract_text(0)[:60] == t0
        win.undo()
        app.processEvents()

        # ---- Keo trang TRONG nhom chon -> ca nhom di ----
        thumbs.clearSelection()
        for r in (1, 3, 5):
            thumbs.item(r).setSelected(True)
        tt = [model.extract_text(i)[:60] for i in (1, 3, 5)]
        drag_page(thumbs, 3, 0)
        got = [model.extract_text(i)[:60] for i in (0, 1, 2)]
        assert got == tt, "ca nhom 2,4,6 phai don len dau"
        win.undo()
        app.processEvents()

        # ---- Bam thuong (khong keo) van chon trang binh thuong ----
        r2 = thumbs.visualItemRect(thumbs.item(2)).center()
        mouse(thumbs, QMouseEvent.Type.MouseButtonPress, r2)
        mouse(thumbs, QMouseEvent.Type.MouseButtonRelease, r2,
              buttons=Qt.MouseButton.NoButton)
        app.processEvents()
        assert thumbs.selected_pages() == [2]

        print("DRAG REORDER SMOKE: OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        errors.append(e)
        print(f"DRAG REORDER SMOKE: FAIL {e!r}")
    finally:
        for w in list(MainWindow._instances):
            for i in range(w.tabs.count()):
                t = w.tabs.widget(i)
                if hasattr(t, "model"):
                    t.model.modified = False
            try:
                w.render_thread.stop()
            except Exception:
                pass
        app.quit()


QTimer.singleShot(300, run)
app.exec()
sys.exit(1 if errors else 0)
