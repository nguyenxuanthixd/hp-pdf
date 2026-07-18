"""Tien ich file: luu qua thu muc tam roi move ve dich (tranh xung dot OneDrive),
khong bao gio ghi de file goc, ho tro ten file Unicode day du."""
import os
import shutil
import tempfile


def human_size(nbytes: int) -> str:
    """Dinh dang dung luong de doc: 1.2 MB, 345 KB..."""
    size = float(nbytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{nbytes} B"


def unique_path(path: str) -> str:
    """Neu file da ton tai, them (1), (2)... de khong bao gio ghi de."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while True:
        cand = f"{base} ({i}){ext}"
        if not os.path.exists(cand):
            return cand
        i += 1


def suffixed_output(src_path: str, suffix: str, ext: str | None = None,
                    out_dir: str | None = None) -> str:
    """Tao duong dan file xuat: <ten goc><hau to>.<ext>, dam bao khong trung."""
    folder = out_dir or os.path.dirname(src_path)
    stem = os.path.splitext(os.path.basename(src_path))[0]
    extension = ext if ext is not None else os.path.splitext(src_path)[1] or ".pdf"
    if not extension.startswith("."):
        extension = "." + extension
    return unique_path(os.path.join(folder, f"{stem}{suffix}{extension}"))


def save_via_temp(write_fn, dest_path: str, overwrite: bool = False) -> str:
    """Ghi file qua thu muc tam (tempfile.mkdtemp) roi move ve dich.

    Tranh xung dot khoa file do OneDrive dong bo thu muc dich.
    write_fn(tmp_path) phai ghi noi dung vao tmp_path.
    overwrite=True: ghi de dung dest_path (chi dung cho file DO APP TAO ra
    truoc do — "Luu" nhanh); mac dinh chong trung ten, khong bao gio ghi de.
    """
    tmpdir = tempfile.mkdtemp(prefix="hpconspdf_")
    try:
        tmp_file = os.path.join(tmpdir, os.path.basename(dest_path))
        write_fn(tmp_file)
        final = dest_path if overwrite else unique_path(dest_path)
        os.makedirs(os.path.dirname(final) or ".", exist_ok=True)
        if overwrite and os.path.exists(final):
            os.remove(final)
        shutil.move(tmp_file, final)
        return final
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def make_temp_dir() -> str:
    return tempfile.mkdtemp(prefix="hpconspdf_")


def parse_page_ranges(text: str, page_count: int) -> list[int]:
    """Phan tich chuoi khoang trang "1-5, 8, 10-12" -> danh sach chi so 0-based.

    Nem ValueError voi thong bao tieng Viet neu sai cu phap / vuot pham vi.
    """
    result: list[int] = []
    text = (text or "").strip()
    if not text:
        raise ValueError("Vui lòng nhập khoảng trang, ví dụ: 1-5, 8, 10-12")
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            pieces = part.split("-")
            if len(pieces) != 2:
                raise ValueError(f"Khoảng trang không hợp lệ: \"{part}\"")
            a_s, b_s = pieces[0].strip(), pieces[1].strip()
            try:
                a = int(a_s) if a_s else 1
                b = int(b_s) if b_s else page_count
            except ValueError:
                raise ValueError(f"Khoảng trang không hợp lệ: \"{part}\"") from None
        else:
            try:
                a = b = int(part)
            except ValueError:
                raise ValueError(f"Số trang không hợp lệ: \"{part}\"") from None
        if a > b:
            a, b = b, a
        if a < 1 or b > page_count:
            raise ValueError(
                f"Trang {part} nằm ngoài phạm vi tài liệu (1–{page_count}).")
        result.extend(range(a - 1, b))
    if not result:
        raise ValueError("Vui lòng nhập khoảng trang, ví dụ: 1-5, 8, 10-12")
    # Giu thu tu nguoi dung nhap, bo trung lap
    seen = set()
    ordered = []
    for i in result:
        if i not in seen:
            seen.add(i)
            ordered.append(i)
    return ordered
