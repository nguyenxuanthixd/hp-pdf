"""Nen PDF: downsample + nen lai anh ben trong file bang pikepdf + Pillow."""
from __future__ import annotations

import io
import os
import zlib

import pikepdf
from PIL import Image

from ..utils.errors import FriendlyError
from ..utils.fileutils import save_via_temp

# Muc nen: (nhan, max canh dai px, chat luong JPEG)
COMPRESS_LEVELS = {
    "light": ("Nhẹ — giữ chất lượng cao (ảnh tối đa 2000px, JPEG 80)", 2000, 80),
    "medium": ("Vừa — cân bằng (ảnh tối đa 1400px, JPEG 65)", 1400, 65),
    "strong": ("Mạnh — dung lượng nhỏ nhất (ảnh tối đa 1000px, JPEG 45)", 1000, 45),
}


def _recompress_image(raw_obj, max_dim: int, quality: int) -> bool:
    """Thu nen lai 1 anh trong PDF. Tra ve True neu da thay the."""
    # Bo qua anh co mat na trong suot / stencil de khong pha layout
    if "/SMask" in raw_obj or raw_obj.get("/ImageMask", False):
        return False
    try:
        pimg = pikepdf.PdfImage(raw_obj)
        pil = pimg.as_pil_image()
    except Exception:
        return False
    if pil.width < 32 or pil.height < 32:
        return False

    try:
        if pil.mode in ("1", "P", "PA", "LA", "RGBA", "CMYK", "I;16", "I"):
            pil = pil.convert("RGB")
        elif pil.mode not in ("RGB", "L"):
            pil = pil.convert("RGB")
    except Exception:
        return False

    orig_len = int(raw_obj.get("/Length", 0))
    if pil.width > max_dim or pil.height > max_dim:
        ratio = max_dim / max(pil.width, pil.height)
        pil = pil.resize((max(1, int(pil.width * ratio)),
                          max(1, int(pil.height * ratio))), Image.LANCZOS)

    buf = io.BytesIO()
    pil.save(buf, "JPEG", quality=quality, optimize=True)
    data = buf.getvalue()
    if orig_len and len(data) >= orig_len * 0.95:
        return False  # khong loi gi thi giu nguyen

    raw_obj.write(data, filter=pikepdf.Name("/DCTDecode"))
    raw_obj.Width = pil.width
    raw_obj.Height = pil.height
    raw_obj.BitsPerComponent = 8
    raw_obj.ColorSpace = (pikepdf.Name("/DeviceRGB") if pil.mode == "RGB"
                          else pikepdf.Name("/DeviceGray"))
    for key in ("/DecodeParms", "/Decode", "/Interpolate", "/Intent"):
        if key in raw_obj:
            del raw_obj[key]
    return True


def compress_pdf(src_path: str, dest_path: str, *, level: str = "medium",
                 password: str = "", progress=None, cancel=None) -> tuple[str, int, int]:
    """Nen PDF -> file moi. Tra ve (duong dan, dung luong truoc, sau)."""
    if level not in COMPRESS_LEVELS:
        level = "medium"
    _, max_dim, quality = COMPRESS_LEVELS[level]
    before = os.path.getsize(src_path)

    with pikepdf.open(src_path, password=password or "") as pdf:
        total = len(pdf.pages)
        done_ids = set()
        for i, page in enumerate(pdf.pages):
            if cancel is not None and cancel.is_set():
                raise FriendlyError("Đã hủy thao tác.")
            if progress:
                progress(i + 1, total, f"Đang nén ảnh trang {i + 1}/{total}")
            try:
                images = dict(page.images)
            except Exception:
                continue
            for _, raw in images.items():
                try:
                    objid = raw.objgen
                    if objid in done_ids:
                        continue
                    done_ids.add(objid)
                    _recompress_image(raw, max_dim, quality)
                except Exception:
                    continue

        def _write(tmp):
            pdf.save(tmp,
                     compress_streams=True,
                     recompress_flate=True,
                     object_stream_mode=pikepdf.ObjectStreamMode.generate)

        final = save_via_temp(_write, dest_path)

    after = os.path.getsize(final)
    return final, before, after
