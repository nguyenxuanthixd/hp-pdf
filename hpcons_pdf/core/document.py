"""Mo hinh tai lieu dang mo trong trinh xem.

- Render trang bang pypdfium2 (pdfium KHONG thread-safe -> moi truy cap
  phai giu PDFIUM_LOCK, ke ca tu worker thread).
- Cac thao tac trang (xoay, xoa, sap xep, chen tu PDF khac) chi thay doi
  danh sach PageRef trong bo nho; khi "Luu thanh..." moi ghi ra file moi
  bang pikepdf. File goc khong bao gio bi ghi de.
"""
from __future__ import annotations

import ctypes
import os
import threading
from dataclasses import dataclass, field

import pikepdf
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from PIL import Image

from ..utils.errors import FriendlyError
from ..utils.fileutils import make_temp_dir, save_via_temp

# Loai doi tuong goc trong PDF
NATIVE_TYPE_NAMES = {
    pdfium_c.FPDF_PAGEOBJ_TEXT: "chữ",
    pdfium_c.FPDF_PAGEOBJ_PATH: "hình vẽ",
    pdfium_c.FPDF_PAGEOBJ_IMAGE: "ảnh",
    pdfium_c.FPDF_PAGEOBJ_SHADING: "tô màu",
    pdfium_c.FPDF_PAGEOBJ_FORM: "nhóm",
}


@dataclass
class NativeObj:
    """Mo ta 1 doi tuong goc tren trang (khong giu handle pdfium song)."""
    obj_index: int
    type: int            # FPDF_PAGEOBJ_*
    x: float             # bounds theo hien thi, goc tren-trai, don vi point
    y: float
    w: float
    h: float
    text: str = ""       # noi dung (chi voi doi tuong chu)
    background: bool = False  # anh/nen phu gan het trang -> bo qua khi chon

    @property
    def type_name(self) -> str:
        return NATIVE_TYPE_NAMES.get(self.type, "đối tượng")

# Khoa toan cuc cho moi loi goi pdfium (thu vien khong thread-safe)
PDFIUM_LOCK = threading.RLock()


def _safe_gen_content(page):
    """Chuan hoa mau ve DeviceRGB roi moi ghi lai noi dung trang.

    pdfium co loi: FPDFPage_GenerateContent lam MAT lenh mau cua cac
    colorspace dac biet (ICCBased...) -> moi hinh to nen bien thanh DEN.
    Doc mau qua GetFillColor/GetStrokeColor (pdfium tu quy doi ve RGB)
    roi gan lai bang SetFillColor/SetStrokeColor de mau duoc giu nguyen.
    Goi ham nay THAY CHO page.gen_content() o moi cho chinh sua.
    """
    editable = (pdfium_c.FPDF_PAGEOBJ_TEXT, pdfium_c.FPDF_PAGEOBJ_PATH)
    r = ctypes.c_uint()
    g = ctypes.c_uint()
    b = ctypes.c_uint()
    a = ctypes.c_uint()
    for obj in page.get_objects(max_depth=1):
        if obj.type not in editable:
            continue
        try:
            if pdfium_c.FPDFPageObj_GetFillColor(
                    obj.raw, ctypes.byref(r), ctypes.byref(g),
                    ctypes.byref(b), ctypes.byref(a)):
                pdfium_c.FPDFPageObj_SetFillColor(
                    obj.raw, r.value, g.value, b.value, a.value)
            if pdfium_c.FPDFPageObj_GetStrokeColor(
                    obj.raw, ctypes.byref(r), ctypes.byref(g),
                    ctypes.byref(b), ctypes.byref(a)):
                pdfium_c.FPDFPageObj_SetStrokeColor(
                    obj.raw, r.value, g.value, b.value, a.value)
        except Exception:
            continue
    page.gen_content()


def is_password_error(exc: Exception) -> bool:
    return "password" in str(exc).lower()


# ---------- Anh xa toa do trang xoay (da kiem chung bang do pixel) ----------
# Khong gian TRANG: goc duoi-trai, y huong len, kich thuoc CHUA xoay (pw, ph).
# Khong gian HIEN THI: goc tren-trai, y huong xuong, dung nhu nguoi dung thay.
# R = (/Rotate goc + xoay them) % 360, chieu kim dong ho.

def _disp_from_page(R: int, pw: float, ph: float, x: float, y: float):
    if R == 90:
        return (y, x)
    if R == 180:
        return (pw - x, y)
    if R == 270:
        return (ph - y, pw - x)
    return (x, ph - y)


def _page_from_disp(R: int, pw: float, ph: float, dx: float, dy: float):
    if R == 90:
        return (dy, dx)
    if R == 180:
        return (pw - dx, dy)
    if R == 270:
        return (pw - dy, ph - dx)
    return (dx, ph - dy)


def _pagedelta_from_dispdelta(R: int, ddx: float, ddy: float):
    """Do lech hien thi -> do lech khong gian trang (dung cho ma tran dich)."""
    if R == 90:
        return (ddy, ddx)
    if R == 180:
        return (-ddx, ddy)
    if R == 270:
        return (-ddy, -ddx)
    return (ddx, -ddy)


def _disp_rect_from_page(geo, l: float, b: float, r: float, t: float):
    """Khung (l,b,r,t) khong gian trang -> (x, y, w, h) hien thi."""
    R, x0, y0, pw, ph = geo
    ax, ay = _disp_from_page(R, pw, ph, l - x0, b - y0)
    bx, by = _disp_from_page(R, pw, ph, r - x0, t - y0)
    return (min(ax, bx), min(ay, by), abs(bx - ax), abs(by - ay))


def _page_geometry(page, extra_rotation: int):
    """(R, x0, y0, pw, ph) tu 1 trang dang mo (pw/ph = kich thuoc CHUA xoay)."""
    base = page.get_rotation()
    try:
        x0, y0, x1, y1 = page.get_cropbox()
    except Exception:
        try:
            x0, y0, x1, y1 = page.get_mediabox()
        except Exception:
            x0, y0 = 0.0, 0.0
            x1, y1 = page.get_width(), page.get_height()
            if base in (90, 270):
                x1, y1 = y1, x1
    return ((base + extra_rotation) % 360, x0, y0, x1 - x0, y1 - y0)


@dataclass
class SourceDoc:
    """Mot file PDF nguon dang duoc tham chieu boi tai lieu.

    current_path: file tam chua ban DA CHINH SUA doi tuong goc (phau thuat
    content stream). None = chua sua, dung file goc. Hoan tac = tro lai
    file tam truoc do trong chuoi.
    """
    path: str
    password: str = ""
    native_modified: bool = False  # da sua/xoa/di chuyen doi tuong goc
    current_path: str | None = None
    _doc: pdfium.PdfDocument | None = field(default=None, repr=False)

    @property
    def effective_path(self) -> str:
        return self.current_path or self.path

    @property
    def effective_password(self) -> str:
        # File tam do app ghi ra khong ma hoa
        return "" if self.current_path else self.password

    @property
    def doc(self) -> pdfium.PdfDocument:
        if self._doc is None:
            with PDFIUM_LOCK:
                self._doc = pdfium.PdfDocument(
                    self.effective_path,
                    password=self.effective_password or None)
        return self._doc

    def reload(self):
        """Dong doc de lan truy cap sau mo lai tu effective_path."""
        self.close()

    def close(self):
        if self._doc is not None:
            with PDFIUM_LOCK:
                try:
                    self._doc.close()
                except Exception:
                    pass
            self._doc = None


@dataclass
class PageRef:
    """Tham chieu 1 trang: (file nguon, chi so trang goc, goc xoay them).

    annots: ghi chu/hinh ve nguoi dung them (toa do theo trang hien thi);
    duoc "nuong" vinh vien vao file khi Luu thanh.
    """
    source: SourceDoc
    index: int
    rotation: int = 0  # 0/90/180/270, cong them vao /Rotate goc
    annots: list = field(default_factory=list)


class DocumentModel:
    """Tai lieu dang mo: danh sach trang + trang thai chinh sua."""

    def __init__(self, path: str, password: str = ""):
        self.path = path
        self.main_source = SourceDoc(path, password)
        # Mo ngay de bao loi som (file hong / sai mat khau)
        _ = self.main_source.doc
        n = len(self.main_source.doc)
        self.pages: list[PageRef] = [PageRef(self.main_source, i) for i in range(n)]
        self.extra_sources: list[SourceDoc] = []
        self.modified = False
        # Cache textpage cho hover/quet chon chu (dong bang PDFIUM_LOCK)
        self._tp_cache: dict[int, tuple] = {}
        # Cache khung bao path tinh tu content stream (cho file ma pdfium
        # khong tra duoc vi tri doi tuong ve). Key: (effective_path, index)
        self._pathbbox_cache: dict[tuple, dict] = {}
        # Thu muc tam chua cac ban da chinh sua (don khi dong tai lieu)
        self._edit_tmpdirs: list[str] = []
        # Ngan xep hoan tac: (mo ta, ham hoan tac)
        self.undo_stack: list[tuple[str, object]] = []

    # ---------- Hoan tac ----------
    def push_undo(self, desc: str, fn):
        self.undo_stack.append((desc, fn))
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    def undo(self) -> str | None:
        """Hoan tac thao tac gan nhat. Tra ve mo ta, None neu het."""
        if not self.undo_stack:
            return None
        desc, fn = self.undo_stack.pop()
        fn()
        self._invalidate_tp_cache()
        return desc

    def _snapshot_pages_undo(self, desc: str):
        """Day undo khoi phuc nguyen danh sach trang (dung cho xoa/sap xep/chen)."""
        before = list(self.pages)

        def _undo():
            self.pages = before
        self.push_undo(desc, _undo)

    # ---------- Thong tin ----------
    @property
    def page_count(self) -> int:
        return len(self.pages)

    def page_size(self, i: int) -> tuple[float, float]:
        """Kich thuoc trang (point), da tinh goc xoay them."""
        ref = self.pages[i]
        with PDFIUM_LOCK:
            w, h = ref.source.doc.get_page_size(ref.index)
        if ref.rotation in (90, 270):
            w, h = h, w
        return w, h

    # ---------- Render ----------
    def render_page(self, i: int, scale: float,
                    for_print: bool = False) -> Image.Image:
        """Render trang thanh anh PIL RGB. Goi duoc tu moi thread (co lock).

        for_print=True: render TOI UU CHO IN (chu/net den sac canh, khong bi
        khu rang cua thanh vien xam -> in ra net nhu Excel)."""
        ref = self.pages[i]
        with PDFIUM_LOCK:
            page = ref.source.doc[ref.index]
            try:
                if for_print:
                    # Uu tien IN: tat khu rang cua chu/net -> canh DEN SAC
                    # (in ra net nhu vector, khong bi vien xam mo)
                    try:
                        bitmap = page.render(
                            scale=scale, rotation=ref.rotation,
                            optimize_mode="print",
                            no_smoothtext=True, no_smoothpath=True)
                    except (TypeError, ValueError):
                        bitmap = page.render(scale=scale, rotation=ref.rotation)
                else:
                    bitmap = page.render(scale=scale, rotation=ref.rotation)
                pil = bitmap.to_pil().convert("RGB")
                bitmap.close()
            finally:
                page.close()
        return pil

    def extract_text(self, i: int) -> str:
        ref = self.pages[i]
        with PDFIUM_LOCK:
            page = ref.source.doc[ref.index]
            try:
                tp = page.get_textpage()
                try:
                    return tp.get_text_range() or ""
                finally:
                    tp.close()
            finally:
                page.close()

    # ---------- Quet chon / copy chu (nhu Foxit Phantom) ----------
    def _get_textpage(self, i: int):
        """(textpage, geometry) cache cho trang i — ho tro ca trang xoay.

        Trang + textpage duoc GIU MO trong cache de hover/keo chon nhanh;
        phai goi _invalidate_tp_cache() khi noi dung/danh sach trang doi.
        """
        with PDFIUM_LOCK:
            if i in self._tp_cache:
                entry = self._tp_cache[i]
                return entry[1], entry[2]
            ref = self.pages[i]
            page = ref.source.doc[ref.index]
            geo = _page_geometry(page, ref.rotation)
            tp = page.get_textpage()
            self._tp_cache[i] = (page, tp, geo)
            # Gioi han cache 4 trang
            while len(self._tp_cache) > 4:
                k = next(iter(self._tp_cache))
                if k == i:
                    k = next(x for x in self._tp_cache if x != i)
                pg, t, _g = self._tp_cache.pop(k)
                for h in (t, pg):
                    if h is not None:
                        try:
                            h.close()
                        except Exception:
                            pass
            return tp, geo

    def sample_bg_color(self, i: int, x: float, y: float, w: float,
                        h: float) -> str:
        """Lay mau NEN o VIEN vung (x,y,w,h hien thi) -> hex, de che trang
        theo mau nen (vd file scan nen nga/xam). '' neu khong lay duoc."""
        try:
            pw, ph = self.page_size(i)
            scale = min(2.0, max(0.5, 1400.0 / max(pw, ph, 1)))
            pil = self.render_page(i, scale).convert("RGB")
            W, H = pil.size
            px = pil.load()
            x0, y0 = int(x * scale), int(y * scale)
            x1, y1 = int((x + w) * scale), int((y + h) * scale)
            x0 = max(0, min(W - 1, x0))
            x1 = max(0, min(W, x1))
            y0 = max(0, min(H - 1, y0))
            y1 = max(0, min(H, y1))
            if x1 - x0 < 2 or y1 - y0 < 2:
                return ""
            samples = []
            sx = max(1, (x1 - x0) // 40)
            for xx in range(x0, x1, sx):
                samples.append(px[xx, y0])
                samples.append(px[xx, y1 - 1])
            sy = max(1, (y1 - y0) // 40)
            for yy in range(y0, y1, sy):
                samples.append(px[x0, yy])
                samples.append(px[x1 - 1, yy])
            if not samples:
                return ""
            rs = sorted(s[0] for s in samples)
            gs = sorted(s[1] for s in samples)
            bs = sorted(s[2] for s in samples)
            m = len(samples) // 2
            return "#%02X%02X%02X" % (rs[m], gs[m], bs[m])
        except Exception:
            return ""

    def _invalidate_tp_cache(self):
        with PDFIUM_LOCK:
            for pg, t, _g in self._tp_cache.values():
                for h in (t, pg):
                    if h is not None:
                        try:
                            h.close()
                        except Exception:
                            pass
            self._tp_cache.clear()
        self._pathbbox_cache.clear()

    def text_hit(self, i: int, x: float, y_top: float, tol: float = 4.0,
                 wait: bool = True) -> int:
        """Chi so ky tu tai diem hien thi (x, y_top); -1 neu khong co chu.

        wait=False: neu luong render dang giu khoa pdfium (trang nang) thi
        BO QUA ngay (tra -1) thay vi cho — dung cho hover de giao dien khong
        bi dung khi chuyen trang tren file ban ve nang.
        """
        if not wait and not PDFIUM_LOCK.acquire(blocking=False):
            return -1
        try:
            tp, geo = self._get_textpage(i)
            if tp is None:
                return -1
            R, x0, y0, pw, ph = geo
            px, py = _page_from_disp(R, pw, ph, x, y_top)
            with PDFIUM_LOCK:
                try:
                    idx = tp.get_index(x0 + px, y0 + py, tol, tol)
                except Exception:
                    return -1
            return idx if idx is not None and idx >= 0 else -1
        finally:
            if not wait:
                PDFIUM_LOCK.release()

    def text_range(self, i: int, a: int, b: int):
        """Chu + khung highlight cua khoang ky tu [a, b] (hien thi, tren-trai).

        Tra ve (text, rects). a/b la chi so ky tu bat ky thu tu.
        """
        tp, geo = self._get_textpage(i)
        if tp is None:
            return ("", [])
        idx, cnt = min(a, b), abs(b - a) + 1
        with PDFIUM_LOCK:
            try:
                text = tp.get_text_range(idx, cnt) or ""
            except Exception:
                text = ""
            rects = []
            try:
                n_r = tp.count_rects(idx, cnt)
                for k in range(n_r):
                    l, bm, r, t = tp.get_rect(k)
                    rects.append(_disp_rect_from_page(geo, l, bm, r, t))
            except Exception:
                pass
        return (text, rects)

    def word_at(self, i: int, idx: int) -> tuple[int, int]:
        """Mo rong chi so ky tu thanh 1 tu (cho nhay dup chon tu)."""
        full = self.extract_text(i)
        if not full or idx >= len(full):
            return (idx, idx)
        if full[idx].isspace():
            return (idx, idx)
        a = idx
        while a > 0 and not full[a - 1].isspace():
            a -= 1
        b = idx
        while b + 1 < len(full) and not full[b + 1].isspace():
            b += 1
        return (a, b)

    def search_page(self, i: int, term: str) -> list[tuple[float, float, float, float]]:
        """Tim `term` tren trang i, tra ve list rect (x, y_top, w, h) theo point,
        goc toa do TREN-TRAI (de ve highlight) — ho tro ca trang xoay."""
        ref = self.pages[i]
        rects: list[tuple[float, float, float, float]] = []
        with PDFIUM_LOCK:
            page = ref.source.doc[ref.index]
            try:
                geo = _page_geometry(page, ref.rotation)
                tp = page.get_textpage()
                try:
                    searcher = tp.search(term, match_case=False)
                    while True:
                        found = searcher.get_next()
                        if found is None:
                            break
                        idx, count = found
                        n_r = tp.count_rects(idx, count)
                        for k in range(n_r):
                            l, b, r, t = tp.get_rect(k)
                            rects.append(_disp_rect_from_page(geo, l, b, r, t))
                finally:
                    tp.close()
            finally:
                page.close()
        return rects

    # ---------- Chinh sua doi tuong GOC trong file ----------
    def native_objects(self, i: int) -> list[NativeObj]:
        """Liet ke doi tuong goc cap 1 tren trang (toa do hien thi).

        Ho tro ca trang xoay (/Rotate hoac xoay them) nho anh xa toa do.
        """
        ref = self.pages[i]
        raw: list[tuple] = []   # (obj_index, type, bounds|None, text)
        geo = None
        need_fallback = False
        with PDFIUM_LOCK:
            page = ref.source.doc[ref.index]
            try:
                geo = _page_geometry(page, ref.rotation)
                tp = None
                for k, obj in enumerate(page.get_objects(max_depth=1)):
                    try:
                        bounds = obj.get_bounds()
                    except Exception:
                        bounds = None
                    text = ""
                    if bounds is not None and \
                            obj.type == pdfium_c.FPDF_PAGEOBJ_TEXT:
                        l, b, r, t = bounds
                        if r - l >= 0.5 and t - b >= 0.5:
                            if tp is None:
                                tp = page.get_textpage()
                            try:
                                text = tp.get_text_bounded(
                                    left=l, bottom=b, right=r, top=t) or ""
                            except Exception:
                                text = ""
                    if bounds is None and \
                            obj.type == pdfium_c.FPDF_PAGEOBJ_PATH:
                        need_fallback = True
                    raw.append((k, obj.type, bounds, text))
                if tp is not None:
                    tp.close()
            finally:
                page.close()
        # pdfium khong tra duoc vi tri net ve -> tinh khung bao tu content stream
        fb = self._path_bboxes_fallback(ref) if need_fallback else {}
        _R, _x0, _y0, pw, ph = geo
        result: list[NativeObj] = []
        for k, otype, bounds, text in raw:
            if bounds is None:
                if otype == pdfium_c.FPDF_PAGEOBJ_PATH and k in fb:
                    l, b, r, t = fb[k]
                else:
                    continue
            else:
                l, b, r, t = bounds
            if r - l < 0.5 or t - b < 0.5:
                continue
            # Anh/hinh phu gan het trang = nen -> khong cho chon truc tiep
            is_bg = (otype != pdfium_c.FPDF_PAGEOBJ_TEXT
                     and (r - l) >= pw * 0.85 and (t - b) >= ph * 0.85)
            dx, dy, dw, dh = _disp_rect_from_page(geo, l, b, r, t)
            result.append(NativeObj(obj_index=k, type=otype,
                                    x=dx, y=dy, w=dw, h=dh, text=text,
                                    background=is_bg))
        return result

    def text_cluster(self, i: int, seeds: list[NativeObj]) -> list[NativeObj]:
        """Gom cac MANH CHU chong/sat nhau cung 1 dong voi `seeds` (file xuat
        loi hay tach 1 dong thanh nhieu manh de len nhau). Keo cum nay se dich
        ca dong, khong bi xe. Chi gom CHU sat theo chieu doc (cung dong)."""
        objs = [o for o in self.native_objects(i)
                if o.type == pdfium_c.FPDF_PAGEOBJ_TEXT]
        by_idx = {o.obj_index: o for o in objs}
        chosen = {o.obj_index for o in seeds if o.obj_index in by_idx}
        if not chosen:
            return list(seeds)

        def connected(a, b) -> bool:
            # Chong/sat theo phuong NGANG va cung dong (y giao nhau nhieu)
            gx = 2.0
            x_ok = not (a.x > b.x + b.w + gx or b.x > a.x + a.w + gx)
            iy = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
            y_ok = iy >= 0.5 * min(a.h, b.h)   # cung dong
            return x_ok and y_ok

        changed = True
        while changed:
            changed = False
            for o in objs:
                if o.obj_index in chosen:
                    continue
                if any(connected(o, by_idx[c]) for c in list(chosen)):
                    chosen.add(o.obj_index)
                    changed = True
        return [o for o in objs if o.obj_index in chosen]

    def _path_bboxes_fallback(self, ref: PageRef) -> dict:
        """Khung bao (l,b,r,t) khong gian trang cho cac doi tuong VE, tinh tu
        content stream. Dung khi pdfium get_bounds bao loi voi net ve (mot so
        file khien app khong chon/xoa duoc net ve). Tra ve {obj_index: bbox}.
        """
        key = (ref.source.effective_path, ref.index)
        cached = self._pathbbox_cache.get(key)
        if cached is not None:
            return cached
        from . import surgery
        result: dict[int, tuple] = {}
        try:
            with pikepdf.open(ref.source.effective_path,
                              password=ref.source.effective_password or "") as pdf:
                page = pdf.pages[ref.index]
                instructions = list(pikepdf.parse_content_stream(page))
            slots = surgery.parse_slots(instructions)
            types, _rot = self._pdfium_types_and_rot(ref)
            # Chi tin khi so luong slot khop danh sach doi tuong pdfium
            # (dam bao obj_index == chi so slot).
            if len(slots) == len(types):
                boxes = surgery.slot_bboxes(instructions)
                for k, (s, bb) in enumerate(zip(slots, boxes)):
                    if s.kind == "path" and bb is not None:
                        result[k] = bb
        except Exception:
            result = {}
        self._pathbbox_cache[key] = result
        return result

    def hit_native(self, i: int, x: float, y: float) -> NativeObj | None:
        """Tim doi tuong goc nho nhat chua diem (x, y), BO QUA anh nen."""
        try:
            objs = self.native_objects(i)
        except FriendlyError:
            raise
        candidates = [o for o in objs if not o.background
                      and o.x - 2 <= x <= o.x + o.w + 2
                      and o.y - 2 <= y <= o.y + o.h + 2]
        if not candidates:
            return None
        return min(candidates, key=lambda o: o.w * o.h)

    def natives_in_region(self, i: int, rx: float, ry: float, rw: float,
                          rh: float) -> list[NativeObj]:
        """Doi tuong goc nam trong vung quet (>=50% dien tich), bo qua nen.

        UU TIEN CHU: neu vung quet co chu thi chi tra ve cac doi tuong chu
        (o co nen to mau se khong bi keo theo — muon chon nen thi bam
        truc tiep vao no). Vung khong co chu thi tra ve hinh/anh nhu thuong.
        """
        try:
            objs = self.native_objects(i)
        except FriendlyError:
            return []
        picked = []
        for o in objs:
            if o.background:
                continue
            ix = max(o.x, rx)
            iy = max(o.y, ry)
            ix2 = min(o.x + o.w, rx + rw)
            iy2 = min(o.y + o.h, ry + rh)
            inter = max(0.0, ix2 - ix) * max(0.0, iy2 - iy)
            area = max(o.w * o.h, 0.01)
            if inter / area >= 0.5:
                picked.append(o)
        texts = [o for o in picked if o.type == pdfium_c.FPDF_PAGEOBJ_TEXT]
        if not texts:
            return picked
        # Keo theo net trang tri OM SAT chu (gach chan/gach ngang): net mong,
        # nam gon trong be ngang cua CUM chu cung dong (1 dong co the bi tach
        # thanh nhieu manh chu). Duong ke bang/nen dai vuot qua chu van chua ra.
        decorations = []
        for o in picked:
            if o.type == pdfium_c.FPDF_PAGEOBJ_TEXT or min(o.w, o.h) > 3.5:
                continue
            near = [t for t in texts
                    if t.y - 3.5 <= o.y <= t.y + t.h + 3.5]
            if not near:
                continue
            lo = min(t.x for t in near) - 4
            hi = max(t.x + t.w for t in near) + 6
            if o.x >= lo and o.x + o.w <= hi:
                decorations.append(o)
        return texts + decorations

    # ---------- Phau thuat content stream (KHONG dung gen_content) ----------
    # gen_content cua pdfium ghi lai ca trang va co the pha mau ICC / chu CJK.
    # Xoa & di chuyen dung core/surgery.py: chi sua dung lenh ve cua doi tuong
    # chon, ghi ra file tam roi chuyen SourceDoc sang file do. Hoan tac = tro
    # ve file truoc trong chuoi.

    def _pdfium_types_and_rot(self, ref: PageRef) -> tuple[list[int], int]:
        with PDFIUM_LOCK:
            page = ref.source.doc[ref.index]
            try:
                types = [o.type for o in page.get_objects(max_depth=1)]
                rot = (page.get_rotation() + ref.rotation) % 360
            finally:
                page.close()
        return types, rot

    def _adopt_edited_file(self, src: SourceDoc, tmp_pdf: str, desc: str,
                           extra_undo=None):
        """Chuyen nguon sang file da chinh sua + day 1 buoc hoan tac."""
        old = src.current_path
        with PDFIUM_LOCK:
            src.current_path = tmp_pdf
            src.reload()
        self._invalidate_tp_cache()
        src.native_modified = True
        self.modified = True

        def _undo():
            with PDFIUM_LOCK:
                src.current_path = old
                src.reload()
            self._invalidate_tp_cache()
            if extra_undo is not None:
                extra_undo()
        self.push_undo(desc, _undo)

    def _surgery(self, i: int, deletes: list[NativeObj],
                 moves: list[NativeObj],
                 disp_delta: tuple[float, float] = (0.0, 0.0)) -> str:
        """Phau thuat trang i, tra ve duong dan file tam (chua adopt)."""
        from . import surgery
        ref = self.pages[i]
        src = ref.source
        types, rot = self._pdfium_types_and_rot(ref)
        move_map = {}
        if moves:
            pdx, pdy = _pagedelta_from_dispdelta(rot, disp_delta[0],
                                                 disp_delta[1])
            move_map = {o.obj_index: (pdx, pdy) for o in moves}
        tmpdir = make_temp_dir()
        self._edit_tmpdirs.append(tmpdir)
        tmp_pdf = os.path.join(tmpdir, "chinh-sua.pdf")
        surgery.edit_page_content(
            src.effective_path, src.effective_password, ref.index, types,
            [o.obj_index for o in deletes], move_map, tmp_pdf)
        return tmp_pdf

    def delete_natives(self, i: int, objs: list[NativeObj]):
        """Xoa cac doi tuong goc khoi trang (hoan tac duoc bang Ctrl+Z)."""
        if not objs:
            return
        src = self.pages[i].source
        tmp = self._surgery(i, objs, [])
        n = len(objs)
        self._adopt_edited_file(
            src, tmp, f"xóa {n} đối tượng" if n > 1 else "xóa đối tượng")

    def delete_native(self, i: int, obj: NativeObj):
        self.delete_natives(i, [obj])

    def erase_region(self, i: int, rx: float, ry: float, rw: float,
                     rh: float) -> int:
        """Xoa SACH moi thu trong vung khoanh: net ve / chu / anh goc + ghi chu.

        Xoa dua tren TOA DO VE THAT trong content stream (khong phu thuoc
        pdfium get_bounds — co file pdfium bao sai toa do) nen luon xoa dung
        va het. Tat ca gom MOT buoc hoan tac. Tra ve so doi tuong da xoa.
        """
        from . import surgery
        ref = self.pages[i]

        def _covered(a) -> bool:
            x, y, w, h = a.bbox()
            ix = max(x, rx)
            iy = max(y, ry)
            ix2 = min(x + w, rx + rw)
            iy2 = min(y + h, ry + rh)
            inter = max(0.0, ix2 - ix) * max(0.0, iy2 - iy)
            return inter / max(w * h, 0.01) >= 0.5

        removed_annots = [a for a in ref.annots if _covered(a)]

        # Vung khoanh (hien thi) -> khung KHONG GIAN TRANG (goc duoi-trai)
        with PDFIUM_LOCK:
            page = ref.source.doc[ref.index]
            try:
                geo = _page_geometry(page, ref.rotation)
            finally:
                page.close()
        R, x0, y0, pw, ph = geo
        gpts = []
        for dx, dy in ((rx, ry), (rx + rw, ry), (rx, ry + rh),
                       (rx + rw, ry + rh)):
            gx, gy = _page_from_disp(R, pw, ph, dx, dy)
            gpts.append((gx + x0, gy + y0))
        xs = [p[0] for p in gpts]
        ys = [p[1] for p in gpts]
        region = (min(xs), min(ys), max(xs), max(ys))

        n = 0
        tmp = None
        src = ref.source
        try:
            tmpdir = make_temp_dir()
            self._edit_tmpdirs.append(tmpdir)
            tmp = os.path.join(tmpdir, "xoa-vung.pdf")
            n = surgery.erase_by_region(
                src.effective_path, src.effective_password, ref.index,
                region, tmp)
        except FriendlyError:
            n = 0
            tmp = None

        if n <= 0 and not removed_annots:
            return 0
        annots_before = list(ref.annots)
        ref.annots = [a for a in ref.annots if a not in removed_annots]

        def _restore_annots():
            ref.annots = annots_before

        if n > 0 and tmp:
            self._adopt_edited_file(src, tmp, "xóa vùng",
                                    extra_undo=_restore_annots)
        else:
            self.modified = True
            self.push_undo("xóa vùng", _restore_annots)
        return n + len(removed_annots)

    def move_natives(self, i: int, objs: list[NativeObj], dx: float, dy: float):
        """Di chuyen cac doi tuong goc theo do lech HIEN THI (point).

        Trang xoay: do lech duoc quy doi ve khong gian trang truoc khi dich.
        """
        if not objs:
            return
        src = self.pages[i].source
        tmp = self._surgery(i, [], objs, (dx, dy))
        n = len(objs)
        self._adopt_edited_file(
            src, tmp,
            f"di chuyển {n} đối tượng" if n > 1 else "di chuyển đối tượng")

    def move_native(self, i: int, obj: NativeObj, dx: float, dy: float):
        self.move_natives(i, [obj], dx, dy)

    def _page_object_texts(self, path: str, password: str,
                           page_index: int) -> list[str]:
        """Text cua tung doi tuong cap 1 (kiem chung sau khi sua chu)."""
        with PDFIUM_LOCK:
            d = pdfium.PdfDocument(path, password=password or None)
            try:
                page = d[page_index]
                try:
                    tp = None
                    out = []
                    for o in page.get_objects(max_depth=1):
                        if o.type != pdfium_c.FPDF_PAGEOBJ_TEXT:
                            out.append("")
                            continue
                        if tp is None:
                            tp = page.get_textpage()
                        try:
                            l, b, r, t = o.get_bounds()
                            out.append(tp.get_text_bounded(
                                left=l, bottom=b, right=r, top=t) or "")
                        except Exception:
                            out.append("")
                    if tp is not None:
                        tp.close()
                finally:
                    page.close()
            finally:
                d.close()
        return out

    def set_native_text(self, i: int, obj: NativeObj, new_text: str):
        """Sua noi dung 1 doi tuong chu (dung font co san trong file).

        Thuc hien tren BAN SAO roi kiem chung: chu moi phai dung, va MOI
        chu khac tren trang phai giu nguyen (chan loi pdfium pha chu CJK).
        Dat yeu cau moi ap dung; khong dat thi file dang mo khong doi.
        """
        if obj.type != pdfium_c.FPDF_PAGEOBJ_TEXT:
            raise FriendlyError("Chỉ sửa được nội dung của đối tượng chữ.")
        ref = self.pages[i]
        src = ref.source
        eff, pw = src.effective_path, src.effective_password
        texts_old = self._page_object_texts(eff, pw, ref.index)

        tmpdir = make_temp_dir()
        self._edit_tmpdirs.append(tmpdir)
        tmp_pdf = os.path.join(tmpdir, "sua-chu.pdf")
        with PDFIUM_LOCK:
            d2 = pdfium.PdfDocument(eff, password=pw or None)
            try:
                pg = d2[ref.index]
                try:
                    objs = list(pg.get_objects(max_depth=1))
                    if obj.obj_index >= len(objs):
                        raise FriendlyError(
                            "Không tìm thấy đối tượng — trang đã thay đổi.")
                    buf = (new_text + "\x00").encode("utf-16-le")
                    arr = (ctypes.c_ubyte * len(buf)).from_buffer_copy(buf)
                    ok = pdfium_c.FPDFText_SetText(
                        objs[obj.obj_index].raw,
                        ctypes.cast(arr, ctypes.POINTER(ctypes.c_ushort)))
                    if not ok:
                        raise FriendlyError(
                            "Không sửa được chữ này (font nhúng trong file "
                            "không cho phép).\nSếp có thể xóa đối tượng rồi "
                            "dùng \"Thêm chữ\" để gõ nội dung mới.")
                    _safe_gen_content(pg)
                finally:
                    pg.close()
                d2.save(tmp_pdf)
            finally:
                d2.close()

        def norm(s: str) -> str:
            return "".join((s or "").split())

        texts_new = self._page_object_texts(tmp_pdf, "", ref.index)
        if len(texts_new) != len(texts_old):
            raise FriendlyError(
                "Không thể sửa chữ trực tiếp trên trang này (cấu trúc trang "
                "thay đổi khi ghi lại), nên đã hủy để bảo toàn nội dung.\n"
                "Cách xử lý: xóa dòng chữ này rồi dùng \"Thêm chữ\".")
        for k, (a, b) in enumerate(zip(texts_old, texts_new)):
            if k == obj.obj_index:
                if norm(b) != norm(new_text):
                    raise FriendlyError(
                        "Font nhúng trong file thiếu ký tự cho nội dung mới "
                        "(thường gặp khi sửa dấu tiếng Việt trên font rút "
                        "gọn), nên đã hủy để tránh chữ hiển thị sai.\n\n"
                        "Cách xử lý: chọn đối tượng chữ này → nhấn Delete để "
                        "xóa, rồi dùng \"Thêm chữ\" gõ nội dung mới.")
            elif norm(a) != norm(b):
                raise FriendlyError(
                    "Việc ghi lại trang này làm sai lệch chữ khác trên trang "
                    "(file dùng font mã hóa đặc biệt), nên đã hủy để bảo toàn "
                    "nội dung.\n\nCách xử lý: xóa dòng chữ này rồi dùng "
                    "\"Thêm chữ\" gõ nội dung mới.")
        self._adopt_edited_file(src, tmp_pdf, "sửa chữ")

    # ---------- Thao tac trang (trong bo nho) ----------
    def rotate_pages(self, indices: list[int], angle: int):
        refs = [self.pages[i] for i in indices]
        for r in refs:
            r.rotation = (r.rotation + angle) % 360
        self.modified = True
        self._invalidate_tp_cache()

        def _undo():
            for r in refs:
                r.rotation = (r.rotation - angle) % 360
        self.push_undo("xoay trang", _undo)

    def delete_pages(self, indices: list[int]):
        if len(indices) >= len(self.pages):
            raise FriendlyError("Không thể xóa tất cả các trang — tài liệu phải còn ít nhất 1 trang.")
        self._snapshot_pages_undo(
            f"xóa {len(indices)} trang" if len(indices) > 1 else "xóa trang")
        keep = [p for k, p in enumerate(self.pages) if k not in set(indices)]
        self.pages = keep
        self.modified = True
        self._invalidate_tp_cache()

    def reorder(self, new_order: list[int]):
        self._snapshot_pages_undo("sắp xếp trang")
        self.pages = [self.pages[i] for i in new_order]
        self.modified = True
        self._invalidate_tp_cache()

    def _find_source(self, path: str, password: str) -> SourceDoc | None:
        """Tim SourceDoc dang mo trung file (de dung lai khi dan/chen)."""
        path = os.path.abspath(path)
        for s in [self.main_source] + self.extra_sources:
            if os.path.abspath(s.path) == path:
                return s
        return None

    def insert_from_pdf(self, path: str, at: int, indices: list[int] | None = None,
                        password: str = ""):
        """Chen cac trang tu PDF khac vao vi tri `at` (0-based)."""
        src = self._find_source(path, password)
        if src is None:
            src = SourceDoc(path, password)
            _ = len(src.doc)  # mo ngay de bat loi
            self.extra_sources.append(src)
        n = len(src.doc)
        if indices is None:
            indices = list(range(n))
        refs = [PageRef(src, i) for i in indices]
        self._snapshot_pages_undo(f"chèn {len(refs)} trang")
        at = max(0, min(at, len(self.pages)))
        self.pages[at:at] = refs
        self.modified = True
        self._invalidate_tp_cache()
        return len(refs)

    def copy_page_data(self, indices: list[int]) -> list[dict]:
        """Du lieu copy trang (dung cho clipboard trang trong ung dung)."""
        import copy as _copy
        items = []
        for i in indices:
            ref = self.pages[i]
            items.append({
                "path": ref.source.path,
                "password": ref.source.password,
                "index": ref.index,
                "rotation": ref.rotation,
                "annots": _copy.deepcopy(ref.annots),
            })
        return items

    def paste_pages(self, items: list[dict], at: int) -> int:
        """Dan cac trang tu clipboard trang vao vi tri `at`."""
        import copy as _copy
        refs = []
        for it in items:
            src = self._find_source(it["path"], it.get("password", ""))
            if src is None:
                src = SourceDoc(it["path"], it.get("password", ""))
                _ = len(src.doc)
                self.extra_sources.append(src)
            refs.append(PageRef(src, it["index"], it.get("rotation", 0),
                                annots=_copy.deepcopy(it.get("annots", []))))
        self._snapshot_pages_undo(f"dán {len(refs)} trang")
        at = max(0, min(at, len(self.pages)))
        self.pages[at:at] = refs
        self.modified = True
        self._invalidate_tp_cache()
        return len(refs)

    # ---------- Luu ----------
    def _open_pike_sources(self, picks) -> tuple[dict[str, pikepdf.Pdf], list[str]]:
        """Mo cac file nguon bang pikepdf.

        Nguon da chinh sua doi tuong goc dung file tam hien hanh
        (effective_path) de ket qua luu mang theo cac chinh sua do.
        """
        opened: dict[str, pikepdf.Pdf] = {}
        for ref in picks:
            key = ref.source.path
            if key in opened:
                continue
            opened[key] = pikepdf.open(
                ref.source.effective_path,
                password=ref.source.effective_password or "")
        return opened, []

    def save_as(self, dest_path: str, indices: list[int] | None = None,
                progress=None, cancel=None, overwrite: bool = False) -> str:
        """Xuat tai lieu (hoac tap con trang) ra file MOI qua thu muc tam.

        overwrite=True chi dung cho "Luu" nhanh vao file app da tao truoc do.
        """
        picks = self.pages if indices is None else [self.pages[i] for i in indices]
        opened, tmpdirs = self._open_pike_sources(picks)
        try:
            out = pikepdf.new()
            total = len(picks)
            for k, ref in enumerate(picks):
                if cancel is not None and cancel.is_set():
                    raise FriendlyError("Đã hủy thao tác.")
                src = opened[ref.source.path]
                out.pages.append(src.pages[ref.index])
                if ref.rotation:
                    out.pages[-1].rotate(ref.rotation, relative=True)
                if progress:
                    progress(k + 1, total, f"Đang ghi trang {k + 1}/{total}")

            page_annots = {k: ref.annots for k, ref in enumerate(picks)
                           if ref.annots}

            def _write(tmp):
                if not page_annots:
                    out.save(tmp)
                    return
                # Luu tam roi nuong ghi chu vao ket qua
                from .annotations import burn_annotations
                step1 = tmp + ".truoc-ghichu.pdf"
                out.save(step1)
                try:
                    burn_annotations(step1, tmp, page_annots,
                                     progress=progress, cancel=cancel)
                finally:
                    try:
                        os.remove(step1)
                    except OSError:
                        pass

            final = save_via_temp(_write, dest_path, overwrite=overwrite)
            out.close()
            return final
        finally:
            for p in opened.values():
                try:
                    p.close()
                except Exception:
                    pass
            import shutil
            for d in tmpdirs:
                shutil.rmtree(d, ignore_errors=True)

    def close(self):
        self._invalidate_tp_cache()
        self.undo_stack.clear()
        self.main_source.close()
        for s in self.extra_sources:
            s.close()
        # Don cac file tam cua chuoi chinh sua (sau khi da dong doc)
        import shutil
        for d in self._edit_tmpdirs:
            shutil.rmtree(d, ignore_errors=True)
        self._edit_tmpdirs.clear()

    @property
    def display_name(self) -> str:
        return os.path.basename(self.path)
