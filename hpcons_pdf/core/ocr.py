"""OCR: nhan dien PDF scan -> PDF searchable (lop text an duoi anh).

Dung pytesseract (Tesseract OCR) + pypdfium2 de render trang thanh anh.
"""
from __future__ import annotations

import io
import os
import shutil

import pikepdf
import pytesseract

from ..config import config
from ..utils.errors import FriendlyError
from ..utils.fileutils import save_via_temp

OCR_LANG_LABELS = [
    ("vie", "Tiếng Việt"),
    ("eng", "Tiếng Anh"),
    ("chi_sim", "Tiếng Trung giản thể"),
    ("chi_tra", "Tiếng Trung phồn thể"),
]

_COMMON_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs",
                 "Tesseract-OCR", "tesseract.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""),
                 "Tesseract-OCR", "tesseract.exe"),
]


def find_tesseract() -> str | None:
    """Tim tesseract.exe: cau hinh nguoi dung -> PATH -> vi tri pho bien."""
    cfg = config.get("tesseract_path", "")
    if cfg and os.path.exists(cfg):
        return cfg
    which = shutil.which("tesseract")
    if which:
        return which
    for p in _COMMON_PATHS:
        if p and os.path.exists(p):
            return p
    return None


def setup_tesseract() -> str:
    """Cai dat duong dan tesseract cho pytesseract; nem FriendlyError neu thieu."""
    path = find_tesseract()
    if not path:
        raise FriendlyError(
            "Chưa tìm thấy Tesseract OCR trên máy này.\n\n"
            "Cách xử lý:\n"
            "1. Cài Tesseract OCR theo hướng dẫn trong README.md (kèm ứng dụng).\n"
            "2. Khi cài, tick chọn thêm ngôn ngữ: Vietnamese, Chinese Simplified, "
            "Chinese Traditional.\n"
            "3. Nếu đã cài ở vị trí khác, bấm nút \"Chọn tesseract.exe...\" "
            "trong hộp thoại OCR để chỉ định.")
    pytesseract.pytesseract.tesseract_cmd = path
    return path


def installed_languages() -> list[str]:
    try:
        setup_tesseract()
        return pytesseract.get_languages(config="")
    except Exception:
        return []


def check_languages(langs: list[str]):
    installed = installed_languages()
    if not installed:
        return  # khong kiem tra duoc -> de tesseract tu bao loi
    missing = [l for l in langs if l not in installed]
    if missing:
        labels = {k: v for k, v in OCR_LANG_LABELS}
        names = ", ".join(f"{labels.get(m, m)} ({m})" for m in missing)
        raise FriendlyError(
            f"Tesseract chưa có gói ngôn ngữ: {names}.\n"
            "Hãy cài thêm gói ngôn ngữ theo hướng dẫn trong README.md "
            "(mục \"Cài gói ngôn ngữ\").")


def ocr_pdf(model, dest_path: str, *, langs: list[str], dpi: int = 300,
            page_indices: list[int] | None = None,
            progress=None, cancel=None) -> str:
    """OCR tai lieu dang mo (DocumentModel) -> PDF searchable moi.

    Moi trang duoc render thanh anh o `dpi`, Tesseract tao lai trang PDF
    gom anh + lop text an. Phu hop cho PDF scan.
    """
    setup_tesseract()
    check_languages(langs)
    lang_str = "+".join(langs) if langs else "vie"

    indices = page_indices if page_indices is not None else list(range(model.page_count))
    if not indices:
        raise FriendlyError("Không có trang nào để OCR.")

    out = pikepdf.new()
    total = len(indices)
    scale = dpi / 72.0
    for k, i in enumerate(indices):
        if cancel is not None and cancel.is_set():
            raise FriendlyError("Đã hủy thao tác.")
        if progress:
            progress(k, total, f"Đang OCR trang {k + 1}/{total}...")
        pil = model.render_page(i, scale)
        pil.info["dpi"] = (dpi, dpi)
        try:
            page_pdf = pytesseract.image_to_pdf_or_hocr(
                pil, extension="pdf", lang=lang_str)
        except pytesseract.TesseractNotFoundError:
            raise FriendlyError(
                "Không chạy được Tesseract OCR. Hãy kiểm tra lại cài đặt "
                "(xem README.md).") from None
        except pytesseract.TesseractError as e:
            raise FriendlyError(
                f"Lỗi Tesseract khi OCR trang {i + 1}:\n{e}") from None
        with pikepdf.open(io.BytesIO(page_pdf)) as page_doc:
            out.pages.extend(page_doc.pages)
        if progress:
            progress(k + 1, total, f"Đã OCR {k + 1}/{total} trang")

    final = save_via_temp(lambda t: out.save(t), dest_path)
    out.close()
    return final
