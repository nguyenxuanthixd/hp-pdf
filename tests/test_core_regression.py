# -*- coding: utf-8 -*-
"""Hoi quy loi quan trong nhat cua HP Cons PDF. Chay:
    python tests/test_core_regression.py

Gom 3 nhom loi tung gap thuc te:
1. "Dai den" — gen_content lam mat mau colorspace ICCBased (_safe_gen_content).
2. Chinh sua tren trang xoay (/Rotate) — anh xa toa do hien thi <-> trang.
3. Quet vung uu tien CHU, bo qua nen; xoa vung giu nen.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WORK = os.path.join(tempfile.gettempdir(), "hpcons_smoke")

from fixtures import ensure_font, make_all  # noqa: E402

make_all()

import pikepdf  # noqa: E402
from PIL import ImageCms  # noqa: E402
from reportlab.lib.colors import Color  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

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


def region_stats(img, box):
    crop = img.crop(box)
    px = list(crop.getdata())
    n = max(len(px), 1)
    dark = sum(1 for (r, g, b) in px if r < 60 and g < 60 and b < 60) / n
    blueish = sum(1 for (r, g, b) in px
                  if 140 < r < 190 and 180 < g < 220 and b > 215) / n
    return dark, blueish


# ===== 1. ICC colorspace (loi dai den) =====
def t_icc():
    icc_path = os.path.join(WORK, "icc_test.pdf")
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(595, 842))
    icc_stream = pikepdf.Stream(pdf, profile.tobytes())
    icc_stream["/N"] = 3
    icc_stream["/Alternate"] = pikepdf.Name("/DeviceRGB")
    page.obj["/Resources"] = pikepdf.Dictionary(
        ColorSpace=pikepdf.Dictionary(CS1=pikepdf.Array(
            [pikepdf.Name("/ICCBased"), pdf.make_indirect(icc_stream)])),
        Font=pikepdf.Dictionary(F1=pikepdf.Dictionary(
            Type=pikepdf.Name("/Font"), Subtype=pikepdf.Name("/Type1"),
            BaseFont=pikepdf.Name("/Helvetica"))))
    content = (b"/CS1 cs 0.651 0.788 0.925 sc 50 600 495 150 re f "
               b"0 0 0 sc BT /F1 24 Tf 60 400 Td (HELLO WORLD) Tj ET")
    page.obj["/Contents"] = pdf.make_indirect(pikepdf.Stream(pdf, content))
    pdf.save(icc_path)
    pdf.close()

    m = DocumentModel(icc_path)
    box = (60, 100, 535, 235)
    dark0, blue0 = region_stats(m.render_page(0, 1.0), box)
    assert blue0 > 0.9
    target = next(o for o in m.native_objects(0) if "HELLO" in o.text)
    m.move_natives(0, [target], 20, 30)
    dark1, blue1 = region_stats(m.render_page(0, 1.0), box)
    assert dark1 < 0.05, f"vung mau bi den ({dark1:.3f}) — loi dai den quay lai!"
    assert blue1 > 0.9
    m.undo()
    out = m.save_as(os.path.join(WORK, "icc_out.pdf"))
    m2 = DocumentModel(out)
    dark2, blue2 = region_stats(m2.render_page(0, 1.0), box)
    assert dark2 < 0.05 and blue2 > 0.9
    m2.close()
    m.close()


check("ICC colorspace: sua/undo/luu khong mat mau (loi dai den)", t_icc)


# ===== 2. Chinh sua tren trang xoay =====
def t_rotated():
    ensure_font()
    base = os.path.join(WORK, "rotpage_base.pdf")
    c = canvas.Canvas(base, pagesize=(400, 600))
    c.setFont("ArialT", 20)
    c.drawString(100, 520, "CHU XOAY")
    c.rect(100, 200, 60, 40, fill=1, stroke=0)
    c.showPage()
    c.save()
    for rot in (90, 180, 270):
        path = os.path.join(WORK, f"rotpage_{rot}.pdf")
        with pikepdf.open(base) as p:
            p.pages[0].Rotate = rot
            p.save(path)
        m = DocumentModel(path)
        objs = m.native_objects(0)
        txt = next(o for o in objs if "CHU XOAY" in (o.text or ""))
        hit = m.hit_native(0, txt.x + txt.w / 2, txt.y + txt.h / 2)
        assert hit is not None and "CHU XOAY" in hit.text, rot
        idx = m.text_hit(0, txt.x + txt.w / 2, txt.y + txt.h / 2, tol=6)
        assert idx >= 0, rot
        m.move_natives(0, [txt], 50, 30)
        txt2 = next(o for o in m.native_objects(0)
                    if "CHU XOAY" in (o.text or ""))
        assert abs(txt2.x - (txt.x + 50)) < 1.5, (rot, txt.x, txt2.x)
        assert abs(txt2.y - (txt.y + 30)) < 1.5, (rot, txt.y, txt2.y)
        m.undo()
        m.delete_natives(0, [txt])
        assert not any("CHU XOAY" in (o.text or "")
                       for o in m.native_objects(0))
        m.undo()
        assert any("CHU XOAY" in (o.text or "") for o in m.native_objects(0))
        srects = m.search_page(0, "XOAY")
        assert srects and all(v >= 0 for v in srects[0])
        m.close()


check("trang xoay 90/180/270: chon/di chuyen/xoa/undo/tim", t_rotated)


# ===== 3. Quet vung uu tien chu =====
def t_priority():
    ensure_font()
    pdf = os.path.join(WORK, "cell_test.pdf")
    c = canvas.Canvas(pdf, pagesize=(842, 595))
    c.setFillColor(Color(0.65, 0.79, 0.93))
    c.rect(50, 400, 700, 80, fill=1, stroke=0)
    c.setFillColor(Color(0, 0, 0))
    c.setFont("ArialT", 14)
    c.drawString(70, 430, "Phát sinh vách chắn đất đoạn A1-B")
    c.drawString(70, 410, "bằng bê tông cốt thép")
    c.showPage()
    c.save()
    m = DocumentModel(pdf)
    # Cong cu CHON quet vung: uu tien chu (khong keo theo o nen)
    picked = m.natives_in_region(0, 40, 100, 760, 110)
    assert picked and all(o.type == pdfium_c.FPDF_PAGEOBJ_TEXT for o in picked)
    hit = m.hit_native(0, 700, 150)
    assert hit is not None and hit.type == pdfium_c.FPDF_PAGEOBJ_PATH
    # XOA VUNG (theo toa do that): khoanh TRUM ca o -> xoa SACH ca nen lan chu
    n = m.erase_region(0, 40, 100, 760, 110)
    paths = [o for o in m.native_objects(0)
             if o.type == pdfium_c.FPDF_PAGEOBJ_PATH]
    assert n == 3 and len(paths) == 0, (n, len(paths))
    m.undo()
    # Khoanh HEP chi trum chu (o nen lo ra ngoai) -> GIU nen, chi xoa chu
    n2 = m.erase_region(0, 65, 148, 250, 42)
    paths2 = [o for o in m.native_objects(0)
              if o.type == pdfium_c.FPDF_PAGEOBJ_PATH]
    assert n2 == 2 and len(paths2) == 1, (n2, len(paths2))
    m.undo()
    m.close()


check("xoa vung theo toa do: trum ca o -> xoa het, hep chi chu -> giu nen",
      t_priority)

print()
print(f"KET QUA: {len(passed)} OK, {len(failed)} FAIL")
sys.exit(1 if failed else 0)
