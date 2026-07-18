# -*- coding: utf-8 -*-
"""Smoke GUI: Ctrl+click chon don doi tuong, quet chu co gach chan,
chon nhieu trang thumbnail."""
import os
import sys
import tempfile
import faulthandler

sys.path.insert(0, r"C:\Users\THIDAUTHAU\Desktop\APP PDF")
os.environ["QT_QPA_PLATFORM"] = "offscreen"
faulthandler.dump_traceback_later(60, exit=True)

WORK = os.path.join(tempfile.gettempdir(), "hpcons_smoke")
os.makedirs(WORK, exist_ok=True)
sample1 = os.path.join(WORK, "hồ sơ thầu 布局.pdf")

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

try:
    pdfmetrics.getFont("ArialT")
except Exception:
    pdfmetrics.registerFont(TTFont("ArialT", r"C:\Windows\Fonts\arial.ttf"))

# PDF co chu GACH CHAN (duong ke ngay duoi chan chu, nhu hop dong/bao gia)
ul_pdf = os.path.join(WORK, "gachchan.pdf")
c = canvas.Canvas(ul_pdf, pagesize=(595, 842))
c.setFont("ArialT", 16)
y = 700
c.drawString(60, y, "GHI CHÚ QUAN TRỌNG CẦN GẠCH CHÂN")
w = c.stringWidth("GHI CHÚ QUAN TRỌNG CẦN GẠCH CHÂN", "ArialT", 16)
c.setLineWidth(1.2)
c.line(60, y - 3, 60 + w, y - 3)  # gach chan sat chan chu
c.showPage()
c.save()

from PyQt6.QtCore import QPointF, QTimer, Qt
from PyQt6.QtWidgets import QApplication
from hpcons_pdf.ui.main_window import MainWindow

app = QApplication(sys.argv)
win = MainWindow()
win.show()
errors = []


class FakeEvent:
    def __init__(self, button=Qt.MouseButton.LeftButton,
                 mods=Qt.KeyboardModifier.NoModifier):
        self._b = button
        self._m = mods
    def button(self):
        return self._b
    def modifiers(self):
        return self._m


CTRL = Qt.KeyboardModifier.ControlModifier


def run():
    try:
        # ================= Ctrl+click chon don doi tuong =================
        win.open_path(sample1)
        tab = win.current_tab()
        view = tab.view
        model = tab.model
        pw0 = view._pages[0]
        app.processEvents()

        view.set_tool("select")
        texts = [o for o in model.native_objects(0) if o.text.strip()]
        assert len(texts) >= 2
        t1, t2 = texts[0], texts[1]

        # click thuong -> chon 1
        view.handle_press(pw0, QPointF(t1.x + 2, t1.y + 2), FakeEvent())
        view.handle_release(pw0, QPointF(t1.x + 2, t1.y + 2))
        assert view._native_sel is not None and len(view._native_sel[1]) == 1

        # Ctrl+click doi tuong 2 -> chon 2
        view.handle_press(pw0, QPointF(t2.x + 2, t2.y + 2), FakeEvent(mods=CTRL))
        assert len(view._native_sel[1]) == 2, view._native_sel

        # Ctrl+click lai doi tuong 2 -> bo, con 1
        view.handle_press(pw0, QPointF(t2.x + 2, t2.y + 2), FakeEvent(mods=CTRL))
        assert len(view._native_sel[1]) == 1

        # Ctrl+click cho trong -> giu nguyen nhom
        view.handle_press(pw0, QPointF(5, 5), FakeEvent(mods=CTRL))
        assert view._native_sel is not None and len(view._native_sel[1]) == 1

        # click thuong cho trong -> bat dau quet vung (nhom cu bo)
        view.handle_press(pw0, QPointF(5, 5), FakeEvent())
        assert view._band_rect is not None
        view.handle_release(pw0, QPointF(6, 6))

        # ================= Quet chu co gach chan =================
        win.open_path(ul_pdf)
        tab2 = win.current_tab()
        view2 = tab2.view
        model2 = tab2.model
        pw = view2._pages[0]
        app.processEvents()
        assert view2.tool == "pan"

        # chu tai y_top = 842-700=142 (chan chu ~142, gach chan ~145)
        # 1) BAM NGAY TREN GACH CHAN (duoi chan chu ~4pt) van bat dau chon
        assert view2.handle_press(pw, QPointF(70, 146), FakeEvent())
        assert view2._tsel_dragging, "bam tren gach chan phai vao che do chon chu"
        # 2) re doc theo gach chan (lech xuong duoi chu) den cuoi dong
        for x in range(90, 380, 40):
            view2.handle_move(pw, QPointF(x, 147))
        view2.handle_move(pw, QPointF(380, 148))
        view2.handle_release(pw, QPointF(380, 148))
        got = view2.selected_text()
        assert "GHI CHÚ" in got and "GẠCH" in got, repr(got)
        assert len(got.strip()) >= 25, repr(got)

        # ================= Chon nhieu trang thumbnail =================
        win.tabs.setCurrentWidget(tab)
        thumbs = tab.thumbs
        thumbs.clearSelection()
        thumbs.item(0).setSelected(True)
        thumbs.item(2).setSelected(True)  # nhu Ctrl+click
        thumbs.item(4).setSelected(True)
        assert thumbs.selected_pages() == [0, 2, 4]
        # thao tac trang dung danh sach chon
        assert win._selected_or_current(tab) == [0, 2, 4]

        print("GUI9 SMOKE: OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        errors.append(e)
        print(f"GUI9 SMOKE: FAIL {e!r}")
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
