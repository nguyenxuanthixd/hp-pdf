# -*- coding: utf-8 -*-
"""Test: tach tab thanh cua so rieng va gop lai; man hinh chao co nut Ghep file.
Chay: python tests/test_windows.py
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
sample2 = os.path.join(WORK, "phụ lục.pdf")

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from hpcons_pdf.ui.main_window import MainWindow  # noqa: E402
from hpcons_pdf.ui.document_tab import DocumentTab  # noqa: E402

app = QApplication(sys.argv)
win = MainWindow()
win.show()
errors = []


def run():
    try:
        # Man hinh chao co nut Ghep file
        assert win.btn_welcome_merge.text() == "Ghép file PDF..."

        win.open_path(sample1)
        win.open_path(sample2)
        tab_a = win.current_tab()
        assert win.tabs.count() == 2
        assert len(MainWindow._instances) == 1

        # ----- Tach tab 2 (phu luc) ra cua so rieng -----
        win.detach_tab(1)
        app.processEvents()
        assert len(MainWindow._instances) == 2, len(MainWindow._instances)
        win2 = MainWindow._instances[1]
        assert win.tabs.count() == 1
        assert win2.tabs.count() == 1
        tab_b = win2.current_tab()
        assert isinstance(tab_b, DocumentTab)
        assert tab_b.model.page_count == 3
        # render thread da chuyen sang cua so moi
        assert tab_b.view._rt is win2.render_thread
        assert tab_b.thumbs._rt is win2.render_thread
        assert tab_b.thumbs.count() == 3
        # tieu de cua so moi theo ten file
        assert "phụ lục" in win2.windowTitle()
        # thao tac tren cua so moi van chay (xoay + undo)
        tab_b.model.rotate_pages([0], 90)
        win2.undo()
        assert tab_b.model.pages[0].rotation == 0

        # ----- Gop nguoc lai ve cua so chinh -----
        win2._move_tab_to(0, win)
        app.processEvents()
        assert win.tabs.count() == 2
        # cua so phu het tab -> tu dong dong
        assert len(MainWindow._instances) == 1, len(MainWindow._instances)
        moved = win.tabs.widget(1)
        assert isinstance(moved, DocumentTab) and moved.model.page_count == 3
        assert moved.view._rt is win.render_thread

        # ----- Tach tab duy nhat cua cua so chinh: chinh hien man hinh chao --
        win.tabs.setCurrentIndex(0)
        win.detach_tab(0)
        app.processEvents()
        assert len(MainWindow._instances) == 2
        # cua so chinh van con 1 tab (phu luc)
        assert win.tabs.count() == 1
        win3 = MainWindow._instances[1]
        assert win3.current_tab().model.page_count == 6
        win3._move_tab_to(0, win)
        app.processEvents()
        assert len(MainWindow._instances) == 1

        print("WINDOWS SMOKE: OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        errors.append(e)
        print(f"WINDOWS SMOKE: FAIL {e!r}")
    finally:
        for w in list(MainWindow._instances):
            for i in range(w.tabs.count()):
                t = w.tabs.widget(i)
                if hasattr(t, "model"):
                    t.model.modified = False
            w.render_thread.stop()
        app.quit()


QTimer.singleShot(200, run)
app.exec()
sys.exit(1 if errors else 0)
