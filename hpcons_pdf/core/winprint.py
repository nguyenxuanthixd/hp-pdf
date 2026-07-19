"""In qua Windows GDI dung DEVMODE tu hop thoai native cua driver may in.

- prompt_devmode(): mo THANG hop thoai thiet lap cua driver (Canon...) —
  dung giao dien goc, day du (2 mat, dong ghim, khay giay...).
- gdi_print(): in bang chinh DEVMODE do -> GIU NGUYEN moi thiet lap.
- get_default_devmode(): lay thiet lap hien tai (de nho / lam diem xuat phat).

DEVMODE duoc luu dang bytes de "ghi nho kieu in" trong phien; dong file thi
bo (ve mac dinh) — do phia UI quyet dinh vong doi.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

CCHDEVICENAME = 32
CCHFORMNAME = 32

DM_OUT_BUFFER = 2
DM_IN_PROMPT = 4
DM_IN_BUFFER = 8
IDOK = 1

# dmFields bit
DM_ORIENTATION = 0x00000001
DM_PAPERSIZE = 0x00000002
DM_COPIES = 0x00000100
DM_COLOR = 0x00000800
DM_DUPLEX = 0x00001000

# dmPaperSize (DMPAPER_*)
PAPER_SIZES = {
    "A4": 9, "A3": 8, "A5": 11, "Letter": 1, "Legal": 5, "Tabloid (11x17)": 3,
}
# dmDuplex
DMDUP_SIMPLEX = 1     # 1 mat
DMDUP_VERTICAL = 2    # 2 mat, lat canh dai (nhu quyen sach)
DMDUP_HORIZONTAL = 3  # 2 mat, lat canh ngan (nhu bloc)

# GetDeviceCaps
HORZRES = 8
VERTRES = 10
LOGPIXELSX = 88
LOGPIXELSY = 90

BI_RGB = 0
DIB_RGB_COLORS = 0
SRCCOPY = 0x00CC0020

CANCELLED = object()
UNAVAILABLE = object()


class DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * CCHDEVICENAME),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmOrientation", ctypes.c_short),
        ("dmPaperSize", ctypes.c_short),
        ("dmPaperLength", ctypes.c_short),
        ("dmPaperWidth", ctypes.c_short),
        ("dmScale", ctypes.c_short),
        ("dmCopies", ctypes.c_short),
        ("dmDefaultSource", ctypes.c_short),
        ("dmPrintQuality", ctypes.c_short),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", wintypes.WCHAR * CCHFORMNAME),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]


PDEVMODE = ctypes.POINTER(DEVMODEW)


class DOCINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_int),
        ("lpszDocName", wintypes.LPCWSTR),
        ("lpszOutput", wintypes.LPCWSTR),
        ("lpszDatatype", wintypes.LPCWSTR),
        ("fwType", wintypes.DWORD),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def _spool():
    ws = ctypes.WinDLL("winspool.drv")
    ws.OpenPrinterW.argtypes = [wintypes.LPCWSTR,
                                ctypes.POINTER(wintypes.HANDLE), wintypes.LPVOID]
    ws.OpenPrinterW.restype = wintypes.BOOL
    ws.ClosePrinter.argtypes = [wintypes.HANDLE]
    ws.DocumentPropertiesW.argtypes = [
        wintypes.HWND, wintypes.HANDLE, wintypes.LPCWSTR,
        PDEVMODE, PDEVMODE, wintypes.DWORD]
    ws.DocumentPropertiesW.restype = ctypes.c_long
    return ws


def _dev_size(ws, hPrinter, name) -> int:
    return ws.DocumentPropertiesW(0, hPrinter, name, None, None, 0)


def get_default_devmode(name: str):
    """Bytes DEVMODE mac dinh hien tai cua may in (None neu that bai)."""
    if not name:
        return None
    try:
        ws = _spool()
    except Exception:
        return None
    h = wintypes.HANDLE()
    if not ws.OpenPrinterW(name, ctypes.byref(h), None):
        return None
    try:
        size = _dev_size(ws, h, name)
        if size <= 0:
            return None
        buf = ctypes.create_string_buffer(size)
        if ws.DocumentPropertiesW(0, h, name, ctypes.cast(buf, PDEVMODE),
                                  None, DM_OUT_BUFFER) < 0:
            return None
        return bytes(buf)
    finally:
        ws.ClosePrinter(h)


def prompt_devmode(name: str, hwnd: int = 0, devmode_in: bytes | None = None):
    """Mo hop thoai thiet lap cua driver. Tra ve:
    - bytes DEVMODE moi neu OK,
    - CANCELLED neu bam Cancel,
    - UNAVAILABLE neu khong goi duoc (nen dung hop thoai Qt thay the)."""
    if not name:
        return UNAVAILABLE
    try:
        ws = _spool()
    except Exception:
        return UNAVAILABLE
    h = wintypes.HANDLE()
    if not ws.OpenPrinterW(name, ctypes.byref(h), None):
        return UNAVAILABLE
    try:
        size = _dev_size(ws, h, name)
        if size <= 0:
            return UNAVAILABLE
        out = ctypes.create_string_buffer(size)
        if devmode_in and len(devmode_in) >= ctypes.sizeof(DEVMODEW):
            in_buf = ctypes.create_string_buffer(devmode_in, len(devmode_in))
            ret = ws.DocumentPropertiesW(
                hwnd, h, name, ctypes.cast(out, PDEVMODE),
                ctypes.cast(in_buf, PDEVMODE),
                DM_IN_BUFFER | DM_OUT_BUFFER | DM_IN_PROMPT)
        else:
            if ws.DocumentPropertiesW(0, h, name, ctypes.cast(out, PDEVMODE),
                                      None, DM_OUT_BUFFER) < 0:
                return UNAVAILABLE
            ret = ws.DocumentPropertiesW(
                hwnd, h, name, ctypes.cast(out, PDEVMODE),
                ctypes.cast(out, PDEVMODE),
                DM_IN_BUFFER | DM_OUT_BUFFER | DM_IN_PROMPT)
        if ret != IDOK:
            return CANCELLED
        return bytes(out)
    finally:
        ws.ClosePrinter(h)


def gdi_print(name: str, devmode_bytes: bytes | None, page_indices: list[int],
              get_bgr, doc_name: str = "HP Cons PDF",
              progress=None, cancel=None, output_file: str | None = None,
              scale_mode: str = "fit", custom_percent: float = 100.0):
    """In qua GDI. get_bgr(i, max_w_px, max_h_px) -> (w, h, bytes_bgr_topdown,
    render_dpi) hoac None de bo qua trang. Tra ve so trang da in / UNAVAILABLE.
    scale_mode: 'fit' (vua le giay) | 'actual' (co that 100%) | 'custom' (%)."""
    gdi = ctypes.windll.gdi32
    gdi.CreateDCW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR,
                              wintypes.LPCWSTR, PDEVMODE]
    gdi.CreateDCW.restype = wintypes.HDC
    gdi.GetDeviceCaps.argtypes = [wintypes.HDC, ctypes.c_int]
    gdi.GetDeviceCaps.restype = ctypes.c_int
    gdi.StartDocW.argtypes = [wintypes.HDC, ctypes.POINTER(DOCINFOW)]
    gdi.StartPage.argtypes = [wintypes.HDC]
    gdi.EndPage.argtypes = [wintypes.HDC]
    gdi.EndDoc.argtypes = [wintypes.HDC]
    gdi.AbortDoc.argtypes = [wintypes.HDC]
    gdi.DeleteDC.argtypes = [wintypes.HDC]
    gdi.StretchDIBits.argtypes = [
        wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_void_p, ctypes.POINTER(BITMAPINFOHEADER),
        wintypes.UINT, wintypes.DWORD]
    gdi.StretchDIBits.restype = ctypes.c_int

    pdev = None
    if devmode_bytes and len(devmode_bytes) >= ctypes.sizeof(DEVMODEW):
        dbuf = ctypes.create_string_buffer(devmode_bytes, len(devmode_bytes))
        pdev = ctypes.cast(dbuf, PDEVMODE)
    hdc = gdi.CreateDCW(None, name, None, pdev)
    if not hdc:
        return UNAVAILABLE
    try:
        hres = gdi.GetDeviceCaps(hdc, HORZRES)
        vres = gdi.GetDeviceCaps(hdc, VERTRES)
        if hres <= 0 or vres <= 0:
            return UNAVAILABLE
        di = DOCINFOW()
        di.cbSize = ctypes.sizeof(DOCINFOW)
        di.lpszDocName = doc_name
        di.lpszOutput = output_file  # None = ra may in; duong dan = ghi file
        if gdi.StartDocW(hdc, ctypes.byref(di)) <= 0:
            return UNAVAILABLE
        # DPI vat ly cua may in (cham/inch) de tinh "co that" / "tuy chinh %"
        dev_dpi_x = gdi.GetDeviceCaps(hdc, LOGPIXELSX) or 300
        dev_dpi_y = gdi.GetDeviceCaps(hdc, LOGPIXELSY) or 300
        done = 0
        aborted = False
        total = len(page_indices)
        for k, i in enumerate(page_indices):
            if cancel is not None and cancel.is_set():
                gdi.AbortDoc(hdc)
                aborted = True
                break
            if progress:
                progress(k, total, f"Đang in trang {i + 1} ({k + 1}/{total})...")
            res = get_bgr(i, hres, vres)
            if res is None:
                continue
            if len(res) == 4:
                w, h, data, render_dpi = res
            else:
                w, h, data = res
                render_dpi = 0
            if gdi.StartPage(hdc) <= 0:
                continue
            if scale_mode in ("actual", "custom") and render_dpi:
                # Kich thuoc that: so pixel anh / dpi render = so inch cua trang
                pct = (custom_percent / 100.0) if scale_mode == "custom" else 1.0
                dw = int(w * dev_dpi_x / render_dpi * pct)
                dh = int(h * dev_dpi_y / render_dpi * pct)
            else:
                # Vua le giay (giu ti le)
                ratio = min(hres / w, vres / h)
                dw, dh = int(w * ratio), int(h * ratio)
            dx, dy = (hres - dw) // 2, (vres - dh) // 2
            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = w
            bmi.biHeight = -h  # top-down
            bmi.biPlanes = 1
            bmi.biBitCount = 24
            bmi.biCompression = BI_RGB
            gdi.StretchDIBits(hdc, dx, dy, dw, dh, 0, 0, w, h,
                              data, ctypes.byref(bmi), DIB_RGB_COLORS, SRCCOPY)
            gdi.EndPage(hdc)
            done += 1
        if not aborted:
            gdi.EndDoc(hdc)
            if progress:
                progress(total, total, "Xong")
        return done
    finally:
        gdi.DeleteDC(hdc)


def set_devmode_fields(devmode_bytes: bytes | None, copies=None,
                       orientation=None, color=None, paper=None,
                       duplex=None) -> bytes | None:
    """Ghi de mot so thiet lap vao DEVMODE.
    orientation: 'portrait'|'landscape'; color: True(mau)/False(den trang);
    paper: ten kho giay trong PAPER_SIZES (vd 'A4'); duplex: 1|2|3 (DMDUP_*)."""
    if not devmode_bytes or len(devmode_bytes) < ctypes.sizeof(DEVMODEW):
        return devmode_bytes
    buf = ctypes.create_string_buffer(devmode_bytes, len(devmode_bytes))
    dm = ctypes.cast(buf, PDEVMODE).contents
    if copies is not None and copies >= 1:
        dm.dmCopies = int(copies)
        dm.dmFields |= DM_COPIES
    if orientation in ("portrait", "landscape"):
        dm.dmOrientation = 1 if orientation == "portrait" else 2
        dm.dmFields |= DM_ORIENTATION
    if color is not None:
        dm.dmColor = 2 if color else 1
        dm.dmFields |= DM_COLOR
    if paper and paper in PAPER_SIZES:
        dm.dmPaperSize = PAPER_SIZES[paper]
        dm.dmFields |= DM_PAPERSIZE
    if duplex in (DMDUP_SIMPLEX, DMDUP_VERTICAL, DMDUP_HORIZONTAL):
        dm.dmDuplex = int(duplex)
        dm.dmFields |= DM_DUPLEX
    return bytes(buf)


def read_copies(devmode_bytes: bytes | None) -> int:
    if not devmode_bytes or len(devmode_bytes) < ctypes.sizeof(DEVMODEW):
        return 1
    dm = ctypes.cast(ctypes.create_string_buffer(devmode_bytes,
                     len(devmode_bytes)), PDEVMODE).contents
    return max(1, int(dm.dmCopies)) if dm.dmCopies else 1
