# -*- coding: utf-8 -*-
"""Test luong cap nhat trong GUI: worker chay nen, khong crash; skip-version;
menu tu-kiem-tra dong bo config. Chay: python tests/test_update_gui.py
"""
import os
import sys
import time
import faulthandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
faulthandler.dump_traceback_later(60, exit=True)

from fixtures import make_all  # noqa: E402
WORK = make_all()
s1 = os.path.join(WORK, "hồ sơ thầu 布局.pdf")

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from hpcons_pdf.core import updater  # noqa: E402
from hpcons_pdf.config import config  # noqa: E402
from hpcons_pdf.ui.main_window import MainWindow  # noqa: E402

app = QApplication(sys.argv)
win = MainWindow()
win.show()
errors = []
offered = {"info": None}


def run():
    try:
        win.open_path(s1)
        app.processEvents()

        # chan _offer_update de khong hien dialog modal
        win._offer_update = lambda info: offered.__setitem__("info", info)

        # ---- 1. Auto-check, khong co ban moi (None) -> khong offer, khong crash
        updater.check_latest = lambda progress=None, cancel=None: None
        win.check_updates(manual=False)
        for _ in range(60):
            app.processEvents()
            if win._update_worker is None:
                break
            time.sleep(0.03)
        assert win._update_worker is None, "worker phai ket thuc"
        assert offered["info"] is None

        # ---- 2. Auto-check, CO ban moi -> offer ----
        info = updater.UpdateInfo("1.2.0", "http://x/s.exe", "note", 100, "s.exe")
        updater.check_latest = lambda progress=None, cancel=None: info
        win.check_updates(manual=False)
        for _ in range(60):
            app.processEvents()
            if win._update_worker is None:
                break
            time.sleep(0.03)
        assert offered["info"] is info, "phai goi _offer_update voi ban moi"

        # ---- 3. Auto-check nhung nguoi dung da BO QUA ban 1.2.0 -> khong offer
        offered["info"] = None
        config.set("skip_update_version", "1.2.0")
        win.check_updates(manual=False)
        for _ in range(60):
            app.processEvents()
            if win._update_worker is None:
                break
            time.sleep(0.03)
        assert offered["info"] is None, "ban bi bo qua khong duoc offer khi tu dong"
        config.set("skip_update_version", "")

        # ---- 4. Menu tu-kiem-tra dong bo config ----
        win.act_auto_update.setChecked(False)
        assert config.get("auto_check_update") is False
        win.act_auto_update.setChecked(True)
        assert config.get("auto_check_update") is True

        print("UPDATE GUI SMOKE: OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        errors.append(e)
        print(f"UPDATE GUI SMOKE: FAIL {e!r}")
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
