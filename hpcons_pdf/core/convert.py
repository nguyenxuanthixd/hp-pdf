"""Chuyen doi: PDF -> anh (PNG/JPG), anh -> PDF, PDF -> text (.txt)."""
from __future__ import annotations

import os

from PIL import Image

from ..utils.errors import FriendlyError
from ..utils.fileutils import save_via_temp, unique_path

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")


def pdf_to_images(model, out_dir: str, *, fmt: str = "PNG", dpi: int = 200,
                  page_indices: list[int] | None = None,
                  progress=None, cancel=None) -> list[str]:
    """Xuat cac trang PDF thanh anh. Tra ve danh sach file da tao."""
    indices = page_indices if page_indices is not None else list(range(model.page_count))
    if not indices:
        raise FriendlyError("Không có trang nào để chuyển đổi.")
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(model.path))[0]
    ext = ".png" if fmt.upper() == "PNG" else ".jpg"
    scale = dpi / 72.0
    results = []
    total = len(indices)
    width = max(3, len(str(model.page_count)))
    for k, i in enumerate(indices):
        if cancel is not None and cancel.is_set():
            raise FriendlyError("Đã hủy thao tác.")
        if progress:
            progress(k, total, f"Đang xuất trang {i + 1} thành ảnh...")
        pil = model.render_page(i, scale)
        dest = unique_path(os.path.join(out_dir, f"{stem}_trang_{i + 1:0{width}d}{ext}"))

        def _write(tmp, im=pil):
            if ext == ".jpg":
                im.convert("RGB").save(tmp, "JPEG", quality=90, dpi=(dpi, dpi))
            else:
                im.save(tmp, "PNG", dpi=(dpi, dpi))

        results.append(save_via_temp(_write, dest))
        if progress:
            progress(k + 1, total, f"Đã xuất {k + 1}/{total} trang")
    return results


_A4_PT = (595.0, 842.0)


def images_to_pdf(image_paths: list[str], dest_path: str, *,
                  page_mode: str = "image",  # "image" | "a4-portrait" | "a4-landscape"
                  progress=None, cancel=None) -> str:
    """Gop nhieu anh thanh 1 file PDF.

    page_mode="image": kich thuoc trang theo tung anh.
    page_mode="a4-*": anh duoc can giua tren nen trang A4 trang.
    """
    if not image_paths:
        raise FriendlyError("Chưa chọn ảnh nào để chuyển thành PDF.")
    pages: list[Image.Image] = []
    total = len(image_paths)
    for k, p in enumerate(image_paths):
        if cancel is not None and cancel.is_set():
            raise FriendlyError("Đã hủy thao tác.")
        if progress:
            progress(k, total, f"Đang xử lý ảnh {os.path.basename(p)}")
        try:
            img = Image.open(p)
            img.load()
        except Exception:
            raise FriendlyError(
                f"Không đọc được file ảnh:\n{p}\n"
                "File có thể bị hỏng hoặc không phải định dạng ảnh.") from None
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            rgba = img.convert("RGBA")
            bg.paste(rgba, mask=rgba.getchannel("A"))
            img = bg
        else:
            img = img.convert("RGB")
        if page_mode.startswith("a4"):
            a4w, a4h = _A4_PT if page_mode.endswith("portrait") else (_A4_PT[1], _A4_PT[0])
            dpi = 150
            cw, ch = int(a4w / 72 * dpi), int(a4h / 72 * dpi)
            canvas_img = Image.new("RGB", (cw, ch), (255, 255, 255))
            margin = int(dpi * 0.4)
            ratio = min((cw - 2 * margin) / img.width, (ch - 2 * margin) / img.height)
            nw, nh = max(1, int(img.width * ratio)), max(1, int(img.height * ratio))
            img = img.resize((nw, nh), Image.LANCZOS)
            canvas_img.paste(img, ((cw - nw) // 2, (ch - nh) // 2))
            canvas_img.info["dpi"] = (dpi, dpi)
            pages.append(canvas_img)
        else:
            pages.append(img)

    if progress:
        progress(total, total, "Đang ghi file PDF...")

    def _write(tmp):
        first, rest = pages[0], pages[1:]
        res = first.info.get("dpi", (96, 96))[0]
        first.save(tmp, "PDF", save_all=True, append_images=rest, resolution=res)

    return save_via_temp(_write, dest_path)


def pdf_to_text(model, dest_path: str, *, page_indices: list[int] | None = None,
                progress=None, cancel=None) -> tuple[str, int]:
    """Trich text tu PDF (can text layer) -> file .txt.

    Tra ve (duong dan file, tong so ky tu). Neu qua it text, UI se goi y OCR.
    """
    indices = page_indices if page_indices is not None else list(range(model.page_count))
    parts = []
    total = len(indices)
    n_chars = 0
    for k, i in enumerate(indices):
        if cancel is not None and cancel.is_set():
            raise FriendlyError("Đã hủy thao tác.")
        if progress:
            progress(k + 1, total, f"Đang trích text trang {i + 1}/{total}")
        txt = model.extract_text(i)
        n_chars += len(txt.strip())
        parts.append(f"===== Trang {i + 1} =====\n{txt}\n")

    def _write(tmp):
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(parts))

    final = save_via_temp(_write, dest_path)
    return final, n_chars
