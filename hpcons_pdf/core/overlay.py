"""Danh so trang & watermark/dong dau — ve lop phu bang reportlab (font vector,
ho tro tieng Viet/Trung), tron vao trang bang pypdf."""
from __future__ import annotations

import io
import os

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from PIL import Image

from ..utils.errors import FriendlyError
from ..utils.fileutils import save_via_temp

_FONTS_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

# Ten hien thi -> (file ttf, subfont index cho .ttc)
_FONT_FILES = {
    "Arial": ("arial.ttf", None),
    "Arial đậm": ("arialbd.ttf", None),
    "Times New Roman": ("times.ttf", None),
    "Segoe UI": ("segoeui.ttf", None),
    "Microsoft YaHei (Trung)": ("msyh.ttc", 0),
}
_registered: set[str] = set()


def available_fonts() -> list[str]:
    return [name for name, (fn, _) in _FONT_FILES.items()
            if os.path.exists(os.path.join(_FONTS_DIR, fn))]


def _register_font(name: str) -> str:
    """Dang ky font TTF voi reportlab, tra ve ten font dung trong canvas."""
    if name in _registered:
        return name
    entry = _FONT_FILES.get(name)
    if entry is None:
        entry = _FONT_FILES["Arial"]
        name = "Arial"
        if name in _registered:
            return name
    fn, sub = entry
    path = os.path.join(_FONTS_DIR, fn)
    if not os.path.exists(path):
        raise FriendlyError(
            f"Không tìm thấy font \"{name}\" trên máy ({fn}).\n"
            "Hãy chọn font khác trong danh sách.")
    if sub is None:
        pdfmetrics.registerFont(TTFont(name, path))
    else:
        pdfmetrics.registerFont(TTFont(name, path, subfontIndex=sub))
    _registered.add(name)
    return name


def _has_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" or "㐀" <= ch <= "䶿" for ch in text)


def pick_font_for_text(text: str, preferred: str = "Arial") -> str:
    """Chon font phu hop: chu Trung -> YaHei neu co."""
    if _has_cjk(text) and os.path.exists(os.path.join(_FONTS_DIR, "msyh.ttc")):
        return "Microsoft YaHei (Trung)"
    return preferred


# 6 vi tri danh so: (khoa, nhan tieng Viet)
NUMBER_POSITIONS = [
    ("top-left", "Trên – trái"),
    ("top-center", "Trên – giữa"),
    ("top-right", "Trên – phải"),
    ("bottom-left", "Dưới – trái"),
    ("bottom-center", "Dưới – giữa"),
    ("bottom-right", "Dưới – phải"),
]

STAMP_POSITIONS = [
    ("top-left", "Góc trên – trái"),
    ("top-center", "Trên – giữa"),
    ("top-right", "Góc trên – phải"),
    ("middle-left", "Giữa – trái"),
    ("center", "Chính giữa"),
    ("middle-right", "Giữa – phải"),
    ("bottom-left", "Góc dưới – trái"),
    ("bottom-center", "Dưới – giữa"),
    ("bottom-right", "Góc dưới – phải"),
]


def _pages_and_sizes(reader: PdfReader):
    """Chuan hoa /Rotate vao noi dung de lop phu luon dung chieu."""
    sizes = []
    for page in reader.pages:
        try:
            if page.get("/Rotate"):
                page.transfer_rotation_to_content()
        except Exception:
            pass
        box = page.mediabox
        sizes.append((float(box.width), float(box.height)))
    return sizes


def _merge_and_save(reader: PdfReader, overlay_bytes: bytes, apply_set: set[int],
                    dest_path: str, progress=None, cancel=None) -> str:
    ov_reader = PdfReader(io.BytesIO(overlay_bytes))
    writer = PdfWriter()
    total = len(reader.pages)
    k = 0
    for i, page in enumerate(reader.pages):
        if cancel is not None and cancel.is_set():
            raise FriendlyError("Đã hủy thao tác.")
        if i in apply_set:
            page.merge_page(ov_reader.pages[k])
            k += 1
        writer.add_page(page)
        if progress:
            progress(i + 1, total, f"Đang xử lý trang {i + 1}/{total}")

    def _write(tmp):
        with open(tmp, "wb") as f:
            writer.write(f)

    return save_via_temp(_write, dest_path)


def add_page_numbers(src_path: str, dest_path: str, *, position: str = "bottom-center",
                     font: str = "Arial", size: int = 11,
                     fmt: str = "Trang {n}/{total}", start: int = 1,
                     page_indices: list[int] | None = None, margin_mm: float = 10,
                     total_override: int | None = None, password: str = "",
                     progress=None, cancel=None) -> str:
    """Danh so trang -> file moi.

    - page_indices: cac trang (0-based) duoc danh so; None = tat ca.
    - start: so bat dau; total_override: tong so hien thi (phuc vu danh so
      lien tuc khi ghep nhieu file).
    """
    reader = PdfReader(src_path, password=password or None)
    sizes = _pages_and_sizes(reader)
    n = len(sizes)
    apply = list(range(n)) if page_indices is None else sorted(set(page_indices))
    apply_set = set(apply)
    total_num = total_override if total_override is not None else start + len(apply) - 1

    font_name = _register_font(pick_font_for_text(fmt, font))
    margin = margin_mm * 72.0 / 25.4

    buf = io.BytesIO()
    c = None
    num = start
    for i in apply:
        w, h = sizes[i]
        if c is None:
            c = canvas.Canvas(buf, pagesize=(w, h))
        else:
            c.setPageSize((w, h))
        text = (fmt.replace("{n}", str(num)).replace("{total}", str(total_num)))
        c.setFont(font_name, size)
        c.setFillColor(Color(0.29, 0.31, 0.33))  # xam dam #4A4F54
        y = h - margin - size * 0.8 if position.startswith("top") else margin
        if position.endswith("left"):
            c.drawString(margin, y, text)
        elif position.endswith("right"):
            c.drawRightString(w - margin, y, text)
        else:
            c.drawCentredString(w / 2, y, text)
        c.showPage()
        num += 1
    if c is None:
        raise FriendlyError("Không có trang nào trong phạm vi đánh số.")
    c.save()

    return _merge_and_save(reader, buf.getvalue(), apply_set, dest_path,
                           progress=progress, cancel=cancel)


def add_text_watermark(src_path: str, dest_path: str, *, text: str,
                       font: str = "Arial", size: int = 0, opacity: float = 0.15,
                       angle: float = 45.0, color: tuple = (0.29, 0.31, 0.33),
                       page_indices: list[int] | None = None, password: str = "",
                       progress=None, cancel=None) -> str:
    """Watermark chu xoay cheo giua trang -> file moi. size=0: tu dong theo trang."""
    if not text.strip():
        raise FriendlyError("Vui lòng nhập nội dung watermark.")
    reader = PdfReader(src_path, password=password or None)
    sizes = _pages_and_sizes(reader)
    n = len(sizes)
    apply = list(range(n)) if page_indices is None else sorted(set(page_indices))
    apply_set = set(apply)

    font_name = _register_font(pick_font_for_text(text, font))

    buf = io.BytesIO()
    c = None
    for i in apply:
        w, h = sizes[i]
        if c is None:
            c = canvas.Canvas(buf, pagesize=(w, h))
        else:
            c.setPageSize((w, h))
        fs = size
        if fs <= 0:
            # Tu dong: vua chieu cheo trang
            import math
            diag = math.hypot(w, h)
            text_w = pdfmetrics.stringWidth(text, font_name, 100)
            fs = max(18, min(140, 100 * (diag * 0.7) / max(text_w, 1)))
        c.saveState()
        c.translate(w / 2, h / 2)
        c.rotate(angle)
        c.setFont(font_name, fs)
        c.setFillColor(Color(color[0], color[1], color[2], alpha=max(0.02, min(1.0, opacity))))
        c.drawCentredString(0, -fs / 3, text)
        c.restoreState()
        c.showPage()
    if c is None:
        raise FriendlyError("Không có trang nào trong phạm vi áp dụng.")
    c.save()

    return _merge_and_save(reader, buf.getvalue(), apply_set, dest_path,
                           progress=progress, cancel=cancel)


def add_image_stamp(src_path: str, dest_path: str, *, image_path: str,
                    position: str = "bottom-right", scale_percent: float = 30.0,
                    opacity: float = 1.0, margin_mm: float = 10,
                    page_indices: list[int] | None = None, password: str = "",
                    progress=None, cancel=None) -> str:
    """Dong dau anh (PNG trong suot) -> file moi.

    scale_percent: chieu rong dau theo % chieu rong trang.
    """
    if not os.path.exists(image_path):
        raise FriendlyError("Không tìm thấy file ảnh con dấu.")
    img = Image.open(image_path).convert("RGBA")
    if opacity < 1.0:
        alpha = img.getchannel("A").point(lambda a: int(a * max(0.05, opacity)))
        img.putalpha(alpha)
    img_ratio = img.height / img.width

    reader = PdfReader(src_path, password=password or None)
    sizes = _pages_and_sizes(reader)
    n = len(sizes)
    apply = list(range(n)) if page_indices is None else sorted(set(page_indices))
    apply_set = set(apply)
    margin = margin_mm * 72.0 / 25.4
    ir = ImageReader(img)

    buf = io.BytesIO()
    c = None
    for i in apply:
        w, h = sizes[i]
        if c is None:
            c = canvas.Canvas(buf, pagesize=(w, h))
        else:
            c.setPageSize((w, h))
        sw = w * max(1.0, min(100.0, scale_percent)) / 100.0
        sh = sw * img_ratio
        if position.endswith("left"):
            x = margin
        elif position.endswith("right"):
            x = w - margin - sw
        else:
            x = (w - sw) / 2
        if position.startswith("top"):
            y = h - margin - sh
        elif position.startswith("bottom"):
            y = margin
        else:
            y = (h - sh) / 2
        c.drawImage(ir, x, y, width=sw, height=sh, mask="auto")
        c.showPage()
    if c is None:
        raise FriendlyError("Không có trang nào trong phạm vi áp dụng.")
    c.save()

    return _merge_and_save(reader, buf.getvalue(), apply_set, dest_path,
                           progress=progress, cancel=cancel)
