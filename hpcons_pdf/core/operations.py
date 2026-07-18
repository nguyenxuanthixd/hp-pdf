"""Cac thao tac PDF cap file: ghep, tach. Dung pikepdf."""
from __future__ import annotations

import os

import pikepdf

from ..utils.errors import FriendlyError
from ..utils.fileutils import save_via_temp, suffixed_output, unique_path


def open_pdf(path: str, password: str = "") -> pikepdf.Pdf:
    return pikepdf.open(path, password=password or "")


def merge_pdfs(paths: list[str], dest_path: str, passwords: dict[str, str] | None = None,
               progress=None, cancel=None) -> str:
    """Ghep nhieu PDF thanh 1 file moi. Tra ve duong dan file ket qua."""
    passwords = passwords or {}
    if len(paths) < 2:
        raise FriendlyError("Cần chọn ít nhất 2 file PDF để ghép.")
    out = pikepdf.new()
    sources = []
    try:
        total = len(paths)
        for k, p in enumerate(paths):
            if cancel is not None and cancel.is_set():
                raise FriendlyError("Đã hủy thao tác.")
            if progress:
                progress(k, total, f"Đang ghép: {os.path.basename(p)}")
            src = pikepdf.open(p, password=passwords.get(p, ""))
            sources.append(src)
            out.pages.extend(src.pages)
        if progress:
            progress(total, total, "Đang ghi file kết quả...")
        final = save_via_temp(lambda t: out.save(t), dest_path)
        return final
    finally:
        out.close()
        for s in sources:
            try:
                s.close()
            except Exception:
                pass


def split_by_ranges(path: str, page_indices: list[int], dest_path: str,
                    password: str = "") -> str:
    """Trich cac trang (0-based, theo thu tu) ra 1 file moi."""
    with pikepdf.open(path, password=password or "") as src:
        out = pikepdf.new()
        for i in page_indices:
            out.pages.append(src.pages[i])
        final = save_via_temp(lambda t: out.save(t), dest_path)
        out.close()
    return final


def split_each_page(path: str, out_dir: str, password: str = "",
                    progress=None, cancel=None) -> list[str]:
    """Tach moi trang thanh 1 file rieng: <ten>_trang_001.pdf ..."""
    results = []
    stem = os.path.splitext(os.path.basename(path))[0]
    with pikepdf.open(path, password=password or "") as src:
        total = len(src.pages)
        width = max(3, len(str(total)))
        for i in range(total):
            if cancel is not None and cancel.is_set():
                raise FriendlyError("Đã hủy thao tác.")
            if progress:
                progress(i + 1, total, f"Đang tách trang {i + 1}/{total}")
            out = pikepdf.new()
            out.pages.append(src.pages[i])
            dest = os.path.join(out_dir, f"{stem}_trang_{i + 1:0{width}d}.pdf")
            results.append(save_via_temp(lambda t, o=out: o.save(t), dest))
            out.close()
    return results


def _estimate_page_sizes(src: pikepdf.Pdf) -> list[int]:
    """Uoc luong dung luong tung trang (byte) tu do dai stream noi dung + anh."""
    sizes = []
    for page in src.pages:
        total = 2048  # phan cung: object, font tham chieu...
        try:
            contents = page.obj.get("/Contents")
            streams = []
            if contents is not None:
                if isinstance(contents, pikepdf.Array):
                    streams = list(contents)
                else:
                    streams = [contents]
            for s in streams:
                try:
                    total += int(s.get("/Length", 0))
                except Exception:
                    pass
            res = page.obj.get("/Resources")
            xobjs = res.get("/XObject") if res is not None else None
            if xobjs is not None:
                for _, xo in xobjs.items():
                    try:
                        total += int(xo.get("/Length", 0))
                    except Exception:
                        pass
        except Exception:
            pass
        sizes.append(total)
    return sizes


def split_by_size(path: str, max_bytes: int, out_dir: str, password: str = "",
                  progress=None, cancel=None) -> list[str]:
    """Tach file thanh nhieu phan, moi phan xap xi khong vuot qua max_bytes.

    Dung luong tung phan la uoc luong (tai nguyen dung chung co the lam
    ket qua chenh lech) — moi phan luon co it nhat 1 trang.
    """
    results = []
    stem = os.path.splitext(os.path.basename(path))[0]
    with pikepdf.open(path, password=password or "") as src:
        n = len(src.pages)
        est = _estimate_page_sizes(src)
        chunks: list[list[int]] = []
        cur: list[int] = []
        cur_size = 0
        for i in range(n):
            if cur and cur_size + est[i] > max_bytes:
                chunks.append(cur)
                cur, cur_size = [], 0
            cur.append(i)
            cur_size += est[i]
        if cur:
            chunks.append(cur)
        total = len(chunks)
        for k, chunk in enumerate(chunks):
            if cancel is not None and cancel.is_set():
                raise FriendlyError("Đã hủy thao tác.")
            if progress:
                progress(k + 1, total, f"Đang ghi phần {k + 1}/{total}")
            out = pikepdf.new()
            for i in chunk:
                out.pages.append(src.pages[i])
            dest = os.path.join(out_dir, f"{stem}_phan_{k + 1:02d}.pdf")
            results.append(save_via_temp(lambda t, o=out: o.save(t), dest))
            out.close()
    return results
