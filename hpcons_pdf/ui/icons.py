"""Bo icon phang ve bang glyph font he thong (Segoe MDL2 Assets / Segoe UI Symbol).

Khong can file anh ngoai; neu font/glyph thieu, chu nhan duoi nut van ro nghia.
"""
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPixmap

from . import theme

# ten -> (glyph, mau). Glyph 1 ky tu vung E7xx-E9xx: Segoe MDL2 Assets;
# ky tu unicode thuong: Segoe UI Symbol; chuoi >1 ky tu: ve dang chu.
_ICONS = {
    "open":      ("", theme.GRAY),
    "save":      ("", theme.GRAY),
    "merge":     ("", theme.BLUE),
    "split":     ("", theme.BLUE),
    "rotate-l":  ("↺", theme.BLUE),
    "rotate-r":  ("↻", theme.BLUE),
    "delete":    ("", theme.BLUE),
    "insert":    ("", theme.BLUE),
    "extract":   ("", theme.BLUE),
    "number":    ("#", theme.GREEN),
    "watermark": ("W", theme.GREEN),
    "ocr":       ("Aa", theme.GREEN),
    "convert":   ("", theme.GREEN),
    "compress":  ("⇊", theme.GREEN),
    "lock":      ("", theme.GREEN),
    "search":    ("", theme.GRAY),
    "zoom-in":   ("", theme.GRAY),
    "zoom-out":  ("", theme.GRAY),
    "fit-width": ("↔", theme.GRAY),
    "fit-page":  ("⛶", theme.GRAY),
    "prev":      ("", theme.GRAY),
    "next":      ("", theme.GRAY),
    "up":        ("", theme.GRAY),
    "down":      ("", theme.GRAY),
    "close":     ("", theme.GRAY),
    # Nut menu gon (Trang / Cong cu)
    "page-menu": ("", theme.BLUE),
    "tools-menu": ("", theme.GREEN),
    # Cong cu chinh sua
    "select":    ("↖", theme.GRAY),
    "text-tool": ("T", theme.GRAY),
    "highlighter": ("", "#D9A800"),
    "shape":     ("□", theme.GRAY),
    "shape-ellipse": ("○", theme.GRAY),
    "shape-line": ("╱", theme.GRAY),
    "shape-arrow": ("↗", theme.GRAY),
    "pen-tool":  ("✎", theme.GRAY),
    "sidebar":   ("▤", theme.GRAY),
    "pan":       ("✋", theme.GRAY),
    "undo":      ("↶", theme.GRAY),
    "erase":     ("⌫", "#C0392B"),
    "print":     ("", theme.GRAY),
}

_cache: dict[tuple, QIcon] = {}
_mdl2_ok: bool | None = None


def _mdl2_available() -> bool:
    global _mdl2_ok
    if _mdl2_ok is None:
        _mdl2_ok = "Segoe MDL2 Assets" in QFontDatabase.families()
    return _mdl2_ok


def _pick_font(glyph: str, px: int) -> QFont:
    if len(glyph) > 1:
        f = QFont("Segoe UI", -1)
        f.setPixelSize(int(px * 0.62))
        f.setBold(True)
        return f
    code = ord(glyph)
    if 0xE700 <= code <= 0xF8FF and _mdl2_available():
        f = QFont("Segoe MDL2 Assets")
        f.setPixelSize(int(px * 0.78))
        return f
    f = QFont("Segoe UI Symbol")
    f.setPixelSize(int(px * 0.82))
    return f


def _paint_cover(p: QPainter, size: int):
    """Icon che trang: cac dong chu bi hop trang de len."""
    p.setPen(QColor("#9AA0A5"))
    for frac in (0.22, 0.38, 0.54, 0.70):
        y = int(size * frac)
        p.drawLine(int(size * 0.10), y, int(size * 0.90), y)
    p.setPen(QColor("#B0B4B8"))
    p.setBrush(QColor("#FFFFFF"))
    p.drawRoundedRect(QRect(int(size * 0.28), int(size * 0.30),
                            int(size * 0.62), int(size * 0.48)), 3, 3)


def _paint_hl_ellipse(p: QPainter, size: int):
    """Icon danh dau elip: vong elip vang mo quanh chu A."""
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(247, 213, 77, 150))
    p.drawEllipse(QRect(int(size * 0.08), int(size * 0.18),
                        int(size * 0.84), int(size * 0.62)))
    f = QFont("Segoe UI", -1)
    f.setPixelSize(int(size * 0.46))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(theme.GRAY))
    p.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "A")


def _paint_highlighter(p: QPainter, size: int):
    """Icon danh dau: chu A + vet to vang ben duoi (de hieu hon glyph)."""
    f = QFont("Segoe UI", -1)
    f.setPixelSize(int(size * 0.52))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(theme.GRAY))
    p.drawText(QRect(0, 0, size, int(size * 0.72)),
               Qt.AlignmentFlag.AlignCenter, "A")
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#F7D54D"))
    p.drawRoundedRect(QRect(int(size * 0.14), int(size * 0.74),
                            int(size * 0.72), int(size * 0.18)), 3, 3)


def get_icon(name: str, size: int = 40, color: str | None = None) -> QIcon:
    glyph, default_color = _ICONS.get(name, ("?", theme.GRAY))
    col = color or default_color
    key = (name, size, col)
    if key in _cache:
        return _cache[key]
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    if name in ("highlighter", "cover", "hl-ellipse"):
        if name == "highlighter":
            _paint_highlighter(p, size)
        elif name == "hl-ellipse":
            _paint_hl_ellipse(p, size)
        else:
            _paint_cover(p, size)
        p.end()
        icon = QIcon(pm)
        _cache[key] = icon
        return icon
    fallback = len(glyph) == 1 and ord(glyph) >= 0xE700 and not _mdl2_available()
    if fallback:
        # Khong co font MDL2 -> ve hinh vuong bo tron don gian
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(col))
        p.drawRoundedRect(QRect(size // 5, size // 5, size * 3 // 5, size * 3 // 5), 4, 4)
    else:
        p.setPen(QColor(col))
        p.setFont(_pick_font(glyph, size))
        p.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, glyph)
    p.end()
    icon = QIcon(pm)
    _cache[key] = icon
    return icon
