# -*- coding: utf-8 -*-
"""Test: mui ten trai/phai chuyen trang, zoom khong nhay trang,
xoa doi tuong khong pha noi dung xung quanh (phau thuat content stream).
Chay: python tests/test_view_nav.py
"""
import os
import sys
import tempfile
import faulthandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
faulthandler.dump_traceback_later(60, exit=True)

from fixtures import make_all  # noqa: E402

WORK = make_all()
sample1 = os.path.join(WORK, "hồ sơ thầu 布局.pdf")

from PyQt6.QtCore import QEvent, QTimer, Qt  # noqa: E402
from PyQt6.QtGui import QKeyEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from hpcons_pdf.ui.main_window import MainWindow  # noqa: E402

app = QApplication(sys.argv)
win = MainWindow()
win.resize(1000, 700)
win.show()
errors = []


def key(view, k):
    ev = QKeyEvent(QEvent.Type.KeyPress, k, Qt.KeyboardModifier.NoModifier)
    view.keyPressEvent(ev)


def settle(view):
    app.processEvents()
    view._update_visible()
    app.processEvents()


def run():
    try:
        win.open_path(sample1)
        tab = win.current_tab()
        view = tab.view
        app.processEvents()

        # ----- Mui ten phai/trai chuyen trang (khong chon gi) -----
        assert not view.has_selection
        view.goto_page(0)
        settle(view)
        assert view.current_page == 0
        key(view, Qt.Key.Key_Right)
        settle(view)
        assert view.current_page == 1, view.current_page
        key(view, Qt.Key.Key_Right)
        settle(view)
        assert view.current_page == 2, view.current_page
        key(view, Qt.Key.Key_Left)
        settle(view)
        assert view.current_page == 1, view.current_page

        # ----- Zoom khong nhay trang -----
        view.goto_page(3)
        settle(view)
        assert view.current_page == 3
        view.set_zoom(2.5)
        settle(view)
        assert view.current_page == 3, \
            f"zoom lam nhay sang trang {view.current_page + 1}"
        view.set_zoom(0.8)
        settle(view)
        assert view.current_page == 3, \
            f"thu nho lam nhay sang trang {view.current_page + 1}"
        view.set_fit_mode("fit-width")
        settle(view)
        assert view.current_page == 3

        # ----- Xoa doi tuong: cac chu khac giu nguyen (phau thuat) -----
        model = tab.model
        before = model.extract_text(0)
        texts = [o for o in model.native_objects(0) if o.text.strip()]
        model.delete_natives(0, [texts[0]])
        after = model.extract_text(0)
        assert texts[0].text.strip() not in after
        # dong chu thu 2 phai con nguyen ven tung ky tu
        assert texts[1].text.strip() in after
        model.undo()
        assert model.extract_text(0) == before

        print("VIEW NAV SMOKE: OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        errors.append(e)
        print(f"VIEW NAV SMOKE: FAIL {e!r}")
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
