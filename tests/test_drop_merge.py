# -*- coding: utf-8 -*-
"""Test tha file PDF THAT (QDropEvent): tha len thanh trang -> GOP; tha len
vung xem -> mo tab moi. Chay: python tests/test_drop_merge.py
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
s1 = os.path.join(WORK, "hồ sơ thầu 布局.pdf")   # 6 trang
s2 = os.path.join(WORK, "phụ lục.pdf")           # 3 trang

from PyQt6.QtCore import QMimeData, QPoint, QPointF, QTimer, Qt, QUrl  # noqa
from PyQt6.QtGui import QDropEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog  # noqa: E402
from hpcons_pdf.ui.main_window import MainWindow  # noqa: E402
from hpcons_pdf.ui.dialogs import merge_drop  # noqa: E402

app = QApplication(sys.argv)
win = MainWindow()
win.resize(1100, 760)
win.show()
errors = []

# Tu dong "OK" hop thoai vi tri ghep, ghi lai lua chon de kiem tra
_dlg_choice = {"mode": "drop"}  # drop|start|end|at
_last_insert_at = {"val": None}


class _AutoMergeDialog(merge_drop.MergeDropDialog):
    def exec(self):
        m = _dlg_choice["mode"]
        if m == "start":
            self.rb_start.setChecked(True)
        elif m == "end":
            self.rb_end.setChecked(True)
        elif m == "at":
            self.rb_at.setChecked(True)
        elif self.rb_drop is not None:
            self.rb_drop.setChecked(True)
        _last_insert_at["val"] = self.insert_at()
        return QDialog.DialogCode.Accepted.value


merge_drop.MergeDropDialog = _AutoMergeDialog


def drop_file(path, win_pos: QPoint):
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(path)])
    ev = QDropEvent(QPointF(win_pos), Qt.DropAction.CopyAction, md,
                    Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                    QDropEvent.Type.Drop)
    win.dropEvent(ev)
    app.processEvents()


def run():
    try:
        win.open_path(s1)
        tab = win.current_tab()
        app.processEvents()
        assert tab.model.page_count == 6
        assert win.tabs.count() == 1

        # ---- Tha s2 len THANH TRANG THU NHO -> hoi vi tri -> GOP ----
        thumbs = tab.thumbs
        assert thumbs.isVisible()
        tp_center = thumbs.rect().center()
        win_pos = thumbs.mapTo(win, tp_center)

        # (a) chon "Cuoi tai lieu" -> gop vao cuoi (trang 7 la PHU LUC 1)
        _dlg_choice["mode"] = "end"
        drop_file(s2, win_pos)
        assert win.tabs.count() == 1, f"khong duoc mo tab moi ({win.tabs.count()})"
        assert tab.model.page_count == 9, tab.model.page_count
        assert _last_insert_at["val"] == 6, _last_insert_at["val"]
        assert "PHỤ LỤC 1" in tab.model.extract_text(6)
        win.undo()
        assert tab.model.page_count == 6

        # (b) chon "Dau tai lieu" -> gop vao dau
        _dlg_choice["mode"] = "start"
        drop_file(s2, win_pos)
        assert _last_insert_at["val"] == 0
        assert tab.model.page_count == 9
        assert "PHỤ LỤC 1" in tab.model.extract_text(0)
        win.undo()
        assert tab.model.page_count == 6

        # ---- Tha s2 len VUNG XEM (ngoai thumbnail) -> mo TAB MOI ----
        view = tab.view
        v_center = view.rect().center()
        win_pos2 = view.mapTo(win, v_center)
        drop_file(s2, win_pos2)
        assert win.tabs.count() == 2, f"phai mo tab moi ({win.tabs.count()})"
        assert win.current_tab().model.page_count == 3

        print("DROP MERGE SMOKE: OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        errors.append(e)
        print(f"DROP MERGE SMOKE: FAIL {e!r}")
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
