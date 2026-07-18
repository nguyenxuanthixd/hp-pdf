# -*- coding: utf-8 -*-
"""Test: quet chu keo theo gach chan (khong keo duong ke bang), gop nhanh
khi tha file, keo sap xep trang, Luu nhanh Ctrl+S, chen truoc trang hien tai.
Chay: python tests/test_batch4.py
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

from fixtures import ensure_font, make_all  # noqa: E402

WORK = make_all()
sample1 = os.path.join(WORK, "hồ sơ thầu 布局.pdf")
sample2 = os.path.join(WORK, "phụ lục.pdf")

from reportlab.pdfgen import canvas  # noqa: E402

ensure_font()
# Trang co: tieu de GACH CHAN + duong ke bang dai + chu trong o
deco_pdf = os.path.join(WORK, "deco.pdf")
c = canvas.Canvas(deco_pdf, pagesize=(595, 842))
c.setFont("ArialT", 16)
c.drawString(60, 700, "Ghi chú quan trọng")
w = c.stringWidth("Ghi chú quan trọng", "ArialT", 16)
c.setLineWidth(1)
c.line(60, 697, 60 + w, 697)          # gach chan OM SAT chu
c.line(40, 650, 555, 650)             # duong ke bang DAI (khong duoc keo theo)
c.setFont("ArialT", 12)
c.drawString(60, 620, "Nội dung dòng hai")
c.showPage()
c.save()

import pikepdf  # noqa: E402
import pypdfium2.raw as pdfium_c  # noqa: E402
from hpcons_pdf.core.document import DocumentModel  # noqa: E402

passed, failed = [], []


def check(name, fn):
    try:
        fn()
        passed.append(name)
        print(f"  OK   {name}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        failed.append((name, repr(e)))
        print(f"  FAIL {name}: {e!r}")


# ---------- 1. Quet chu keo theo gach chan, khong keo duong ke bang ----------
def t_decoration():
    m = DocumentModel(deco_pdf)
    picked = m.natives_in_region(0, 30, 100, 540, 150)  # vung tieu de + ke bang
    kinds = [(o.type, round(o.w)) for o in picked]
    texts = [o for o in picked if o.type == pdfium_c.FPDF_PAGEOBJ_TEXT]
    paths = [o for o in picked if o.type == pdfium_c.FPDF_PAGEOBJ_PATH]
    assert texts, kinds
    assert len(paths) == 1, f"phai keo theo DUNG gach chan: {kinds}"
    assert paths[0].w < 200, "duong ke bang dai khong duoc keo theo"
    # di chuyen nhom -> gach chan di theo chu
    x_before = paths[0].x
    m.move_natives(0, picked, 0, 50)
    objs = m.native_objects(0)
    ul = [o for o in objs if o.type == pdfium_c.FPDF_PAGEOBJ_PATH
          and o.w < 200]
    assert ul and abs(ul[0].x - x_before) < 1
    m.undo()
    m.close()
check("quet chu keo theo gach chan (chua duong ke bang)", t_decoration)


# ---------- 2. Luu nhanh (overwrite file da xuat) ----------
def t_quick_save():
    m = DocumentModel(sample1)
    m.rotate_pages([0], 90)
    dest = os.path.join(WORK, "quicksave.pdf")
    for leftover in (dest, os.path.join(WORK, "quicksave (1).pdf")):
        if os.path.exists(leftover):
            os.remove(leftover)
    p1 = m.save_as(dest)
    assert p1 == dest
    m.rotate_pages([1], 90)
    p2 = m.save_as(dest, overwrite=True)  # ghi de dung file do
    assert p2 == dest
    with pikepdf.open(dest) as p:
        assert len(p.pages) == 6
    # khong overwrite -> chong trung ten
    p3 = m.save_as(dest)
    assert p3 != dest and os.path.exists(p3)
    m.close()
check("Luu nhanh: overwrite dung file da xuat; mac dinh van chong trung", t_quick_save)


# ---------- 3. GUI: gop nhanh khi tha + keo sap xep + chen truoc trang ----------
def t_gui():
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication
    from hpcons_pdf.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.show()
    state = {}

    def run():
        try:
            win.open_path(sample1)
            tab = win.current_tab()
            app.processEvents()
            # gop nhanh: khong hop thoai, chen ngay tai vi tri tha (truoc trang 3)
            win._merge_dropped_files([sample2], 2)
            assert tab.model.page_count == 9, tab.model.page_count
            assert tab.thumbs.count() == 9
            # trang chen vao dung vi tri: trang 3 gio la PHU LUC 1
            assert "PHỤ LỤC 1" in tab.model.extract_text(2)
            # hoan tac ca cum
            win.undo()
            assert tab.model.page_count == 6
            # keo sap xep trang (mo phong _sync_after_move nhu drop noi bo)
            it = tab.thumbs.takeItem(0)
            tab.thumbs.insertItem(3, it)
            tab.thumbs._sync_after_move()
            app.processEvents()
            assert "Trang gốc 2" in tab.model.extract_text(0)
            win.undo()
            # Luu Ctrl+S: ghi thang vao file dang mo + nap lai tu dia
            import shutil as _sh
            qs_path = os.path.join(WORK, "qs_truc_tiep.pdf")
            _sh.copyfile(sample2, qs_path)
            win.open_path(qs_path)
            tab_qs = win.current_tab()
            tab_qs.model.rotate_pages([0], 90)
            assert tab_qs.model.modified
            ok = win.quick_save()
            assert ok, "quick_save phai thanh cong"
            tab_qs = win.current_tab()
            # file tren dia da nhan chinh sua (trang 1 xoay ngang)
            with pikepdf.open(qs_path) as p:
                assert int(p.pages[0].get("/Rotate", 0)) % 360 == 90
            # model da nap lai: het modified, het undo, trang hien ngang
            assert not tab_qs.model.modified
            assert not tab_qs.model.undo_stack
            w0, h0 = tab_qs.model.page_size(0)
            assert w0 > h0
            win._close_tab(win.tabs.indexOf(tab_qs))
            # nut Chen trang co tren toolbar
            assert win.act_insert.iconText() == "Chèn trang"
            state["ok"] = True
        except Exception as e:
            import traceback
            traceback.print_exc()
            state["err"] = e
        finally:
            for i in range(win.tabs.count()):
                w = win.tabs.widget(i)
                if hasattr(w, "model"):
                    w.model.modified = False
            win.render_thread.stop()
            app.quit()

    QTimer.singleShot(200, run)
    app.exec()
    assert state.get("ok"), state.get("err")
check("GUI: gop nhanh tai vi tri tha + sap xep + Luu nhanh + nut Chen trang", t_gui)

print()
print(f"KET QUA: {len(passed)} OK, {len(failed)} FAIL")
sys.exit(1 if failed else 0)
