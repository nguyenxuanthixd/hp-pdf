"""Chuyen loi ky thuat thanh thong bao tieng Viet than thien."""
import os


class FriendlyError(Exception):
    """Loi da co thong bao tieng Viet, hien truc tiep cho nguoi dung."""


def friendly_message(exc: Exception) -> str:
    """Tra ve thong bao tieng Viet cho cac loi thuong gap."""
    if isinstance(exc, FriendlyError):
        return str(exc)

    name = type(exc).__name__
    text = str(exc)

    # pikepdf
    if name == "PasswordError":
        return ("File PDF này được bảo vệ bằng mật khẩu.\n"
                "Vui lòng nhập đúng mật khẩu để tiếp tục, hoặc dùng chức năng "
                "\"Bảo mật → Gỡ mật khẩu\" nếu Sếp biết mật khẩu.")
    if name in ("PdfError", "DataDecodingError", "ForeignObjectError"):
        return ("Không đọc được file PDF — file có thể bị hỏng hoặc không đúng "
                "định dạng PDF.\nHãy thử mở file bằng trình đọc khác để kiểm tra, "
                "hoặc dùng bản gốc của file.")

    # pypdfium2
    if name == "PdfiumError":
        low = text.lower()
        if "password" in low:
            return ("File PDF này được bảo vệ bằng mật khẩu.\n"
                    "Vui lòng nhập đúng mật khẩu để mở file.")
        return ("Không hiển thị được file PDF — file có thể bị hỏng.\n"
                "Hãy thử tải lại file gốc hoặc kiểm tra file bằng trình đọc khác.")

    # pytesseract
    if name == "TesseractNotFoundError":
        return ("Chưa tìm thấy Tesseract OCR trên máy này.\n\n"
                "Cách xử lý:\n"
                "1. Cài đặt Tesseract OCR (xem hướng dẫn trong file README.md "
                "kèm theo ứng dụng).\n"
                "2. Khi cài, nhớ chọn thêm ngôn ngữ Vietnamese, Chinese "
                "(Simplified/Traditional).\n"
                "3. Nếu đã cài mà vẫn báo lỗi, vào hộp thoại OCR → "
                "\"Đường dẫn Tesseract\" để chọn file tesseract.exe.")
    if name == "TesseractError":
        if "language" in text.lower() or "tessdata" in text.lower():
            return ("Tesseract thiếu gói ngôn ngữ được chọn.\n"
                    "Hãy cài thêm gói ngôn ngữ (vie / chi_sim / chi_tra) — "
                    "xem hướng dẫn trong README.md.")
        return f"Lỗi khi chạy OCR:\n{text}"

    if isinstance(exc, PermissionError):
        fn = getattr(exc, "filename", "") or ""
        return (f"Không có quyền ghi/đọc file{(': ' + os.path.basename(fn)) if fn else ''}.\n"
                "File có thể đang được mở trong chương trình khác — hãy đóng lại "
                "rồi thử lần nữa.")
    if isinstance(exc, FileNotFoundError):
        fn = getattr(exc, "filename", "") or text
        return f"Không tìm thấy file:\n{fn}"
    if isinstance(exc, OSError):
        return f"Lỗi truy cập file:\n{text}"
    if isinstance(exc, ValueError):
        return text or "Dữ liệu nhập không hợp lệ."
    if isinstance(exc, MemoryError):
        return ("Không đủ bộ nhớ để xử lý — file quá lớn.\n"
                "Hãy thử tách file nhỏ hơn hoặc giảm DPI.")

    return f"Đã xảy ra lỗi không mong muốn ({name}):\n{text}"
