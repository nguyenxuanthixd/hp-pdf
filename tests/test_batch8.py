# -*- coding: utf-8 -*-
"""Test: auto-scroll khi keo trang toi mep; an/hien thanh trang.
Chay: python tests/test_batch8.py
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

from PyQt6.QtCore import QPoint, QPointF, QTimer, Qt  # noqa: E402
from PyQt6.QtGui import QMouseEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from hpcons_pdf.ui.main_window import MainWindow  # noqa: E402

app = QApplication(sys.argv)
win = MainWindow()
win.resize(1200, 760)
win.show()
errors = []


def run():
    try:
        win.open_path(DDK)
        tab = win.current_tab()
        thumbs = tab.thumbs
        app.processEvents()
        n = thumbs.count()
        assert n >= 20, n

        # ================= 1. Auto-scroll khi keo toi mep duoi =================
        thumbs.verticalScrollBar().setValue(0)
        app.processEvents()
        top0 = thumbs.verticalScrollBar().value()
        # Bat dau keo trang 1
        start = thumbs.visualItemRect(thumbs.item(0)).center()
        gp = thumbs.mapToGlobal(start)
        press = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(start),
                            QPointF(gp), Qt.MouseButton.LeftButton,
                            Qt.MouseButton.LeftButton,
                            Qt.KeyboardModifier.NoModifier)
        thumbs.mousePressEvent(press)
        # Re xuong sat MEP DUOI viewport -> kich hoat auto-scroll
        low = QPoint(start.x(), thumbs.viewport().height() - 6)
        for _ in range(3):
            mv = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(low),
                             QPointF(thumbs.mapToGlobal(low)),
                             Qt.MouseButton.LeftButton,
                             Qt.MouseButton.LeftButton,
                             Qt.KeyboardModifier.NoModifier)
            thumbs.mouseMoveEvent(mv)
        assert thumbs._manual_drag, "phai vao che do keo"
        assert thumbs._autoscroll.isActive(), "auto-scroll phai chay o mep duoi"
        assert thumbs._autoscroll_dy > 0, "phai cuon XUONG"
        # cho timer cuon vai nhip
        for _ in range(8):
            thumbs._autoscroll_tick()
        app.processEvents()
        assert thumbs.verticalScrollBar().value() > top0, "thanh cuon phai chay xuong"

        # Re ve giua -> dung auto-scroll
        mid = QPoint(start.x(), thumbs.viewport().height() // 2)
        mv = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(mid),
                         QPointF(thumbs.mapToGlobal(mid)),
                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier)
        thumbs.mouseMoveEvent(mv)
        assert not thumbs._autoscroll.isActive(), "ve giua phai dung cuon"

        # Tha chuot -> ket thuc, timer tat
        rel = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(mid),
                          QPointF(thumbs.mapToGlobal(mid)),
                          Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton,
                          Qt.KeyboardModifier.NoModifier)
        thumbs.mouseReleaseEvent(rel)
        assert not thumbs._autoscroll.isActive()

        # ================= 2. An/hien thanh trang =================
        assert tab.thumbs.isVisible()
        win.act_toggle_sidebar.setChecked(False)   # bat action -> an
        app.processEvents()
        assert not tab.thumbs.isVisible(), "thanh trang phai an"
        assert win.sidebar_visible is False
        # mo file thu 2 -> thanh trang cung dang AN (nho trang thai chung)
        win.open_path(DDK)  # cung file -> chuyen tab cu; mo file khac:
        # dung sample2 de chac chan tab moi
        from fixtures import make_all as _m
        s2 = os.path.join(_m(), "phụ lục.pdf")
        win.open_path(s2)
        tab2 = win.current_tab()
        app.processEvents()
        assert not tab2.thumbs.isVisible(), "tab moi phai theo trang thai an"
        # hien lai
        win.act_toggle_sidebar.setChecked(True)
        app.processEvents()
        assert tab2.thumbs.isVisible()
        # quay lai tab 1 cung hien
        win.tabs.setCurrentIndex(0)
        app.processEvents()
        assert win.current_tab().thumbs.isVisible()

        print("BATCH8 SMOKE: OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        errors.append(e)
        print(f"BATCH8 SMOKE: FAIL {e!r}")
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
