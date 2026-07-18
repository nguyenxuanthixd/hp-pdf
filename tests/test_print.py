# -*- coding: utf-8 -*-
"""Test luong in: hop thoai chon may in + pham vi; winprint devmode/copies.
Chay: python tests/test_print.py
"""
import os
import sys
import ctypes
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

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtPrintSupport import QPrinterInfo  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from hpcons_pdf.core import winprint  # noqa: E402
from hpcons_pdf.ui.main_window import MainWindow  # noqa: E402

app = QApplication(sys.argv)
win = MainWindow()
win.show()
errors = []


def run():
    try:
        # ---- 1. winprint.read_copies parse DEVMODE ----
        dm = winprint.DEVMODEW()
        dm.dmCopies = 5
        raw = bytes(dm)
        assert winprint.read_copies(raw) == 5, winprint.read_copies(raw)
        assert winprint.read_copies(None) == 1

        # ---- 2. get_default_devmode cho may in (neu co) khong loi ----
        names = [i.printerName() for i in QPrinterInfo.availablePrinters()]
        if names:
            b = winprint.get_default_devmode(names[0])
            assert b is None or (isinstance(b, bytes)
                                 and len(b) >= ctypes.sizeof(winprint.DEVMODEW))

        # ---- 3. Hop thoai chon may in + pham vi ----
        from hpcons_pdf.ui.dialogs.print_dialog import PrintDialog
        pn = names or ["Máy in ảo A", "Máy in ảo B"]
        d = PrintDialog(59, 4, pn, pn[0], pn[-1], win)
        assert d.selected_printer() == pn[-1]         # nho may in lan cuoi
        assert d.page_indices() == list(range(59))    # tat ca
        d.rb_cur.setChecked(True)
        assert d.page_indices() == [4]                # trang hien tai
        d.rb_range.setChecked(True)
        d.ed_range.setText("1-3, 10")
        assert d.page_indices() == [0, 1, 2, 9]       # khoang
        d.ed_range.setText("999")
        try:
            d.page_indices(); assert False
        except ValueError:
            pass

        # ---- 4. Ghi nho thiet lap per-tab, reset khi dong file ----
        win.open_path(DDK)
        tab = win.current_tab()
        app.processEvents()
        assert tab.print_devmode is None and tab.print_printer == ""
        tab.print_printer = "Canon"
        tab.print_devmode = b"xxxx"
        # dong tab -> tao tab moi (mo lai) -> thiet lap ve mac dinh
        idx = win.tabs.indexOf(tab)
        win._close_tab(idx)
        win.open_path(DDK)
        tab2 = win.current_tab()
        assert tab2.print_devmode is None and tab2.print_printer == ""

        print("PRINT SMOKE: OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        errors.append(e)
        print(f"PRINT SMOKE: FAIL {e!r}")
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
