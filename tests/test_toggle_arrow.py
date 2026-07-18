# -*- coding: utf-8 -*-
"""Test nut mui ten thu/mo thanh trang o goc tren-trai.
Chay: python tests/test_toggle_arrow.py
"""
import os
import sys
import faulthandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
faulthandler.dump_traceback_later(60, exit=True)

DDK = os.path.join(ROOT, "DDK - BAO GIA PHAT SINH - 05122025 (1).pdf")
if not os.path.exists(DDK):
    from fixtures import make_all
    DDK = os.path.join(make_all(), "hồ sơ thầu 布局.pdf")
from fixtures import make_all
S2 = os.path.join(make_all(), "phụ lục.pdf")

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QToolBar  # noqa: E402
from hpcons_pdf.ui.main_window import MainWindow  # noqa: E402

app = QApplication(sys.argv)
win = MainWindow()
win.resize(1100, 740)
win.show()
errors = []


def run():
    try:
        win.open_path(DDK)
        tab = win.current_tab()
        app.processEvents()

        # Nut mui ten ton tai, o goc tren-trai, dang '‹' khi thanh trang hien
        btn = tab.btn_toggle
        assert btn.isVisible()
        assert btn.text() == "‹", btn.text()
        assert btn.x() < 30 and btn.y() < 30, (btn.x(), btn.y())

        # Toolbar KHONG con nut "Thanh trang" to
        tb = win.findChildren(QToolBar)[0]
        assert "Thanh trang" not in [a.text() for a in tb.actions()]

        # Bam nut mui ten -> an thanh trang, mui ten doi thanh '›'
        btn.click()
        app.processEvents()
        assert not tab.thumbs.isVisible()
        assert win.sidebar_visible is False
        assert btn.text() == "›", btn.text()
        assert btn.isVisible(), "nut van phai thay de mo lai"

        # Bam lai -> hien, mui ten '‹'
        btn.click()
        app.processEvents()
        assert tab.thumbs.isVisible()
        assert btn.text() == "‹"

        # F4 / menu action dong bo nut
        win.act_toggle_sidebar.setChecked(False)
        app.processEvents()
        assert not tab.thumbs.isVisible() and btn.text() == "›"
        win.act_toggle_sidebar.setChecked(True)
        app.processEvents()

        # Mo file khac: nut o tab moi dung chieu theo trang thai chung
        win.act_toggle_sidebar.setChecked(False)  # an
        win.open_path(S2)
        tab2 = win.current_tab()
        app.processEvents()
        assert not tab2.thumbs.isVisible()
        assert tab2.btn_toggle.text() == "›", tab2.btn_toggle.text()
        # bam nut o tab2 -> hien ca 2 tab
        tab2.btn_toggle.click()
        app.processEvents()
        assert tab2.thumbs.isVisible() and tab2.btn_toggle.text() == "‹"
        win.tabs.setCurrentIndex(0)
        app.processEvents()
        assert win.current_tab().thumbs.isVisible()
        assert win.current_tab().btn_toggle.text() == "‹"

        print("TOGGLE ARROW SMOKE: OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        errors.append(e)
        print(f"TOGGLE ARROW SMOKE: FAIL {e!r}")
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
