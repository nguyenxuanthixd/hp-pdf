# -*- coding: utf-8 -*-
"""Test Ctrl+bam chon nhieu trang RAI RAC tich luy dung (bug: sync xoa mat).
Chay: python tests/test_multiselect.py
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


def click(thumbs, row, mods=Qt.KeyboardModifier.NoModifier):
    """Mo phong click chuot that (press + release) len o `row`."""
    pos = thumbs.visualItemRect(thumbs.item(row)).center()
    gp = thumbs.mapToGlobal(pos)
    press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(pos),
                        QPointF(gp), Qt.MouseButton.LeftButton,
                        Qt.MouseButton.LeftButton, mods)
    release = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(pos),
                          QPointF(gp), Qt.MouseButton.LeftButton,
                          Qt.MouseButton.NoButton, mods)
    thumbs.mousePressEvent(press)
    thumbs.mouseReleaseEvent(release)
    app.processEvents()


def run():
    try:
        win.open_path(DDK)
        tab = win.current_tab()
        thumbs = tab.thumbs
        app.processEvents()
        assert thumbs.count() >= 6

        CTRL = Qt.KeyboardModifier.ControlModifier

        # ---- Bam thuong trang 2 -> chon dung 1 trang ----
        click(thumbs, 1)
        assert thumbs.selected_pages() == [1], thumbs.selected_pages()

        # ---- Ctrl+bam trang 4 -> tich luy thanh {2,4} ----
        click(thumbs, 3, CTRL)
        assert thumbs.selected_pages() == [1, 3], thumbs.selected_pages()

        # ---- Ctrl+bam trang 6 -> {2,4,6} ----
        click(thumbs, 5, CTRL)
        assert thumbs.selected_pages() == [1, 3, 5], thumbs.selected_pages()

        # ---- Ctrl+bam lai trang 4 -> bo, con {2,6} ----
        click(thumbs, 3, CTRL)
        assert thumbs.selected_pages() == [1, 5], thumbs.selected_pages()

        # ---- Bam thuong trang khac -> reset ve 1 trang ----
        click(thumbs, 0)
        assert thumbs.selected_pages() == [0], thumbs.selected_pages()

        # ---- Shift+bam trang 4 -> chon dai 1..4 (index 0..3) ----
        click(thumbs, 3, Qt.KeyboardModifier.ShiftModifier)
        assert thumbs.selected_pages() == [0, 1, 2, 3], thumbs.selected_pages()

        # ---- Ctrl+A chon het ----
        thumbs.setFocus()
        win._select_all_pages()
        assert thumbs.selected_pages() == list(range(thumbs.count()))

        print("MULTISELECT SMOKE: OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        errors.append(e)
        print(f"MULTISELECT SMOKE: FAIL {e!r}")
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
