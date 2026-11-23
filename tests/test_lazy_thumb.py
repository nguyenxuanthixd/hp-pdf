# -*- coding: utf-8 -*-
"""Thumbnail render LUOI theo vung nhin: mo file nhieu trang chi render so it
thumbnail dang thay (khong render het) -> nhe RAM/CPU. Cuon toi dau render toi do.
Chay: python tests/test_lazy_thumb.py
"""
import os
import sys
import faulthandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
faulthandler.dump_traceback_later(60, exit=True)

from PyQt6.QtCore import QTimer, QEventLoop  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from hpcons_pdf.ui.main_window import MainWindow  # noqa: E402

DDK = os.path.join(ROOT, "DDK - BAO GIA PHAT SINH - 05122025 (1).pdf")
if not os.path.exists(DDK):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from fixtures import make_all
    DDK = os.path.join(make_all(), "hồ sơ thầu 布局.pdf")

app = QApplication.instance() or QApplication(sys.argv)
win = MainWindow(); win.resize(1200, 800); win.show()
errors = []


def wait(ms):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()


def run():
    try:
        win.open_path(DDK)
        tab = win.current_tab()
        thumbs = tab.thumbs
        app.processEvents()
        wait(700); app.processEvents(); wait(300); app.processEvents()

        total = tab.model.page_count
        rendered = len(thumbs._rendered_idx)
        first, last = thumbs._visible_rows()
        assert rendered > 0, "phai render it nhat vung dang nhin"
        if total > 20:   # file du lon moi kiem duoc tinh LUOI
            assert rendered < total, f"lazy sai: render het {rendered}/{total}"

        # cuon xuong cuoi -> vung nhin doi, render them trang moi
        sb = thumbs.verticalScrollBar()
        sb.setValue(sb.maximum())
        app.processEvents(); wait(300); app.processEvents(); wait(300)
        app.processEvents()
        _, last2 = thumbs._visible_rows()
        assert last2 >= last, "cuon xuong phai thay trang khac/xa hon"

        print(f"LAZY THUMB SMOKE: OK (render {rendered}/{total}, "
              f"vung ({first},{last})->(_,{last2}))")
    except Exception as e:
        import traceback
        traceback.print_exc()
        errors.append(e)
        print(f"LAZY THUMB SMOKE: FAIL {e!r}")
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
