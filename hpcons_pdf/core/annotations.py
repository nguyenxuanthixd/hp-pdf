"""Ghi chu/chinh sua tren trang PDF: chu, highlight, hinh ve.

Toa do luu theo DIEM (point) cua trang dang hien thi, goc TREN-TRAI
(trung voi toa do ve tren man hinh). Khi luu file, cac ghi chu duoc
"nuong" (burn) vinh vien vao trang bang reportlab + pypdf.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field

from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas

from .overlay import _register_font, pick_font_for_text

# Cac loai: 'text' | 'highlight' | 'rect' | 'ellipse' | 'line' | 'pen'


@dataclass
class Annot:
    kind: str
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    points: list = field(default_factory=list)  # [(x,y)...] cho line/pen
    color: str = "#E53935"
    width: float = 2.0
    opacity: float = 1.0
    text: str = ""
    font_size: float = 14.0

    def bbox(self) -> tuple[float, float, float, float]:
        if self.kind in ("line", "pen", "arrow") and self.points:
            xs = [p[0] for p in self.points]
            ys = [p[1] for p in self.points]
            return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        return (self.x, self.y, self.w, self.h)

    def move_by(self, dx: float, dy: float):
        self.x += dx
        self.y += dy
        if self.points:
            self.points = [(px + dx, py + dy) for (px, py) in self.points]

    def hit(self, px: float, py: float, pad: float = 4.0) -> bool:
        x, y, w, h = self.bbox()
        return (x - pad <= px <= x + w + pad) and (y - pad <= py <= y + h + pad)


def _hex_rgb(hex_color: str) -> tuple[float, float, float]:
    s = hex_color.lstrip("#")
    return (int(s[0:2], 16) / 255.0, int(s[2:4], 16) / 255.0,
            int(s[4:6], 16) / 255.0)


def measure_text(text: str, font_size: float) -> tuple[float, float]:
    """Uoc luong khung chu (point) de hit-test tren man hinh."""
    lines = text.split("\n") or [""]
    w = max((len(ln) for ln in lines), default=1) * font_size * 0.55
    h = len(lines) * font_size * 1.3
    return (max(w, font_size), max(h, font_size))


def draw_annots(c: canvas.Canvas, annots: list[Annot], page_h: float,
                off_x: float = 0.0, off_y: float = 0.0):
    """Ve danh sach ghi chu len canvas reportlab (toa do PDF: goc duoi-trai)."""
    for a in annots:
        r, g, b = _hex_rgb(a.color)

        def fy(y_top: float) -> float:  # doi truc y
            return off_y + page_h - y_top

        if a.kind == "whiteout":
            c.saveState()
            c.setFillColor(Color(1, 1, 1))
            c.rect(off_x + a.x, fy(a.y + a.h), a.w, a.h, stroke=0, fill=1)
            c.restoreState()
        elif a.kind == "highlight":
            c.saveState()
            c.setFillColor(Color(r, g, b, alpha=0.40))
            c.rect(off_x + a.x, fy(a.y + a.h), a.w, a.h, stroke=0, fill=1)
            c.restoreState()
        elif a.kind == "rect":
            c.saveState()
            c.setStrokeColor(Color(r, g, b, alpha=a.opacity))
            c.setLineWidth(a.width)
            c.rect(off_x + a.x, fy(a.y + a.h), a.w, a.h, stroke=1, fill=0)
            c.restoreState()
        elif a.kind == "ellipse":
            c.saveState()
            c.setStrokeColor(Color(r, g, b, alpha=a.opacity))
            c.setLineWidth(a.width)
            c.ellipse(off_x + a.x, fy(a.y + a.h), off_x + a.x + a.w, fy(a.y),
                      stroke=1, fill=0)
            c.restoreState()
        elif a.kind == "hl-ellipse":
            c.saveState()
            c.setFillColor(Color(r, g, b, alpha=0.40))
            c.ellipse(off_x + a.x, fy(a.y + a.h), off_x + a.x + a.w, fy(a.y),
                      stroke=0, fill=1)
            c.restoreState()
        elif a.kind == "line" and len(a.points) >= 2:
            c.saveState()
            c.setStrokeColor(Color(r, g, b, alpha=a.opacity))
            c.setLineWidth(a.width)
            (x1, y1), (x2, y2) = a.points[0], a.points[-1]
            c.line(off_x + x1, fy(y1), off_x + x2, fy(y2))
            c.restoreState()
        elif a.kind == "arrow" and len(a.points) >= 2:
            import math
            c.saveState()
            c.setStrokeColor(Color(r, g, b, alpha=a.opacity))
            c.setLineWidth(a.width)
            c.setLineCap(1)
            (x1, y1), (x2, y2) = a.points[0], a.points[-1]
            c.line(off_x + x1, fy(y1), off_x + x2, fy(y2))
            # dau mui ten (tinh trong toa do hien thi y-xuong)
            ang = math.atan2(y2 - y1, x2 - x1)
            head = max(8.0, a.width * 4 + 6)
            for da in (math.pi * 5 / 6, -math.pi * 5 / 6):
                hx = x2 + head * math.cos(ang + da)
                hy = y2 + head * math.sin(ang + da)
                c.line(off_x + x2, fy(y2), off_x + hx, fy(hy))
            c.restoreState()
        elif a.kind == "pen" and len(a.points) >= 2:
            c.saveState()
            c.setStrokeColor(Color(r, g, b, alpha=a.opacity))
            c.setLineWidth(a.width)
            c.setLineJoin(1)
            c.setLineCap(1)
            path = c.beginPath()
            path.moveTo(off_x + a.points[0][0], fy(a.points[0][1]))
            for (px, py) in a.points[1:]:
                path.lineTo(off_x + px, fy(py))
            c.drawPath(path, stroke=1, fill=0)
            c.restoreState()
        elif a.kind == "text" and a.text:
            font = _register_font(pick_font_for_text(a.text, "Arial"))
            c.saveState()
            c.setFillColor(Color(r, g, b, alpha=a.opacity))
            c.setFont(font, a.font_size)
            for i, line in enumerate(a.text.split("\n")):
                baseline_top = a.y + a.font_size * 0.9 + i * a.font_size * 1.2
                c.drawString(off_x + a.x, fy(baseline_top), line)
            c.restoreState()


def burn_annotations(src_pdf_path: str, dest_path: str,
                     page_annots: dict[int, list[Annot]],
                     progress=None, cancel=None):
    """Nuong ghi chu vao PDF: doc src, tron lop ve, ghi ra dest_path.

    page_annots: {chi_so_trang_trong_file: [Annot...]} — toa do theo kich
    thuoc trang HIEN THI (da xoay). Trang co /Rotate se duoc chuan hoa
    truoc khi tron de toa do khop voi nhung gi nguoi dung thay.
    """
    from pypdf import PdfReader, PdfWriter

    from ..utils.errors import FriendlyError

    reader = PdfReader(src_pdf_path)
    writer = PdfWriter()

    # Chuan hoa xoay + lay kich thuoc cho cac trang co ghi chu
    sizes = {}
    for i in page_annots:
        page = reader.pages[i]
        try:
            if page.get("/Rotate"):
                page.transfer_rotation_to_content()
        except Exception:
            pass
        box = page.mediabox
        sizes[i] = (float(box.left), float(box.bottom),
                    float(box.width), float(box.height))

    # Ve overlay: 1 trang overlay cho moi trang co ghi chu (theo thu tu)
    order = sorted(page_annots.keys())
    buf = io.BytesIO()
    c = None
    for i in order:
        left, bottom, w, h = sizes[i]
        if c is None:
            c = canvas.Canvas(buf, pagesize=(w, h))
        else:
            c.setPageSize((w, h))
        draw_annots(c, page_annots[i], page_h=h, off_x=left, off_y=bottom)
        c.showPage()
    if c is not None:
        c.save()
        ov_reader = PdfReader(io.BytesIO(buf.getvalue()))

    total = len(reader.pages)
    k = 0
    for i, page in enumerate(reader.pages):
        if cancel is not None and cancel.is_set():
            raise FriendlyError("Đã hủy thao tác.")
        if i in page_annots:
            page.merge_page(ov_reader.pages[order.index(i)])
            k += 1
        writer.add_page(page)
        if progress:
            progress(i + 1, total, f"Đang ghi chú trang {i + 1}/{total}")

    with open(dest_path, "wb") as f:
        writer.write(f)
