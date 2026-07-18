# -*- coding: utf-8 -*-
"""Test: doi thu tu MOT trang (ngoai nhom chon) vs keo ca NHOM dang chon.
Chay: python tests/test_batch7.py
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

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from hpcons_pdf.ui.main_window import MainWindow  # noqa: E402

app = QApplication(sys.argv)
win = MainWindow()
win.show()
errors = []


def run():
    try:
        win.open_path(sample1)
        tab = win.current_tab()
        model = tab.model
        thumbs = tab.thumbs
        app.processEvents()

        def labels():
            return [model.extract_text(i).split("gốc")[1].strip()[:1]
                    for i in range(6)]

        def drag_reorder(origin_row, target_row):
            """Mo phong dropEvent: chon 'rows' theo origin roi move."""
            sel = thumbs.selected_pages()
            rows = sel if origin_row in sel else [origin_row]
            thumbs.move_rows_to(rows, target_row)
            app.processEvents()

        assert labels() == ["1", "2", "3", "4", "5", "6"], labels()

        # ---- (A) Dang chon 2,4,6; KEO trang 5 (ngoai nhom) len vi tri 2 ----
        # -> chi trang 5 di chuyen, nhom 2,4,6 khong bi keo theo
        thumbs.clearSelection()
        for r in (1, 3, 5):
            thumbs.item(r).setSelected(True)
        drag_reorder(origin_row=4, target_row=1)   # trang 5 (idx4) -> truoc idx1
        assert labels() == ["1", "5", "2", "3", "4", "6"], labels()
        win.undo()
        app.processEvents()
        assert labels() == ["1", "2", "3", "4", "5", "6"], labels()

        # ---- (A2) Vi du cua Sep: keo trang 7 len vi tri 2 (8 trang) ----
        # dung file 6 trang -> keo trang 6 (idx5) len vi tri 2 (idx1)
        thumbs.clearSelection()
        drag_reorder(origin_row=5, target_row=1)
        assert labels() == ["1", "6", "2", "3", "4", "5"], labels()
        win.undo()
        app.processEvents()

        # ---- (B) KEO trang NAM TRONG nhom chon (2,4,6) -> ca nhom di chuyen -
        thumbs.clearSelection()
        for r in (1, 3, 5):
            thumbs.item(r).setSelected(True)
        drag_reorder(origin_row=3, target_row=0)   # trang 4 thuoc nhom
        assert labels() == ["2", "4", "6", "1", "3", "5"], labels()
        win.undo()
        app.processEvents()

        # ---- (C) Chon giu nhieu trang cho thao tac hang loat ----
        thumbs.clearSelection()
        for r in (1, 3, 5):
            thumbs.item(r).setSelected(True)
        assert thumbs.selected_pages() == [1, 3, 5]
        assert win._selected_or_current(tab) == [1, 3, 5]

        print("BATCH7 SMOKE: OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        errors.append(e)
        print(f"BATCH7 SMOKE: FAIL {e!r}")
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


QTimer.singleShot(200, run)
app.exec()
sys.exit(1 if errors else 0)
