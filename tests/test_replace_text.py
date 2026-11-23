# -*- coding: utf-8 -*-
"""Sua chu goc trong file: khi font nhung thieu ky tu -> THAY bang chu moi
(che nen + dat chu moi dung cho, font day du). Kiem _replace_native_with_annot.
Chay: python tests/test_replace_text.py
"""
import os
import sys
import tempfile
import faulthandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["QT_QPA_PLATFORM"] = "offscreen"
faulthandler.dump_traceback_later(60, exit=True)

WORK = os.path.join(tempfile.gettempdir(), "hpcons_replace")
os.makedirs(WORK, exist_ok=True)

from reportlab.pdfgen import canvas  # noqa: E402
src = os.path.join(WORK, "goc.pdf")
c = canvas.Canvas(src, pagesize=(595, 842))
c.setFont("Helvetica", 14)
c.drawString(80, 760, "CONG TY ABC")
c.showPage()
c.save()

import pypdfium2 as pdfium          # noqa: E402
import pypdfium2.raw as pc          # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from hpcons_pdf.ui.main_window import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
win = MainWindow(); win.show()
errors = []


def run():
    try:
        win.open_path(src)
        tab = win.current_tab()
        view = tab.view
        app.processEvents()

        objs = [o for o in tab.model.native_objects(0)
                if o.type == pc.FPDF_PAGEOBJ_TEXT and o.text.strip()]
        assert objs, "khong tim thay chu goc"
        obj = objs[0]
        ref = tab.model.pages[0]
        n0 = len(ref.annots)

        # Thay bang chu moi (co dau tieng Viet)
        view._replace_native_with_annot(0, obj, "Công ty Thủy Dương ăn ở")
        assert len(ref.annots) == n0 + 2, "phai them 2 annot (che + chu)"
        cover, txt = ref.annots[-2], ref.annots[-1]
        assert cover.kind == "whiteout" and txt.kind == "text"
        assert txt.text == "Công ty Thủy Dương ăn ở"
        # dat dung cho chu goc
        assert abs(txt.x - obj.x) < 0.01 and abs(txt.y - obj.y) < 0.01
        assert txt.font_size > obj.h, "co chu nen xap xi chieu cao chu goc"
        # chon san chu moi de chinh them
        assert view._selected == (0, txt)

        # Undo -> go ca 2
        tab.model.undo()
        assert len(ref.annots) == n0, "undo phai go ca 2 annot"

        # Lam lai + bake ra file -> chu moi phai xuat hien
        view._replace_native_with_annot(0, obj, "KIEMTRA789")
        out = os.path.join(WORK, "thay.pdf")
        tab.model.save_as(out)
        d = pdfium.PdfDocument(out)
        tp = d[0].get_textpage(); alltext = tp.get_text_range()
        tp.close(); d.close()
        assert "KIEMTRA789" in alltext, "chu moi phai co trong file da luu"

        print("REPLACE TEXT SMOKE: OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        errors.append(e)
        print(f"REPLACE TEXT SMOKE: FAIL {e!r}")
    finally:
        for i in range(win.tabs.count()):
            w = win.tabs.widget(i)
            if hasattr(w, "model"):
                w.model.modified = False
        win.render_thread.stop()
        app.quit()


from PyQt6.QtCore import QTimer  # noqa: E402
QTimer.singleShot(200, run)
app.exec()
sys.exit(1 if errors else 0)
