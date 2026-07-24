"""Chinh sua noi dung trang bang "phau thuat" content stream (pikepdf).

Ly do ton tai: FPDFPage_GenerateContent cua pdfium ghi lai TOAN BO trang va
co nhieu loi (mat mau colorspace ICC, hong chu CJK voi font ma hoa dac biet).
Module nay chi go / di chuyen dung cac lenh ve cua doi tuong duoc chon,
moi byte khac cua trang giu nguyen — khong the pha noi dung xung quanh.

Quy tac anh xa "slot" (khop voi thu tu doi tuong pdfium liet ke):
- Moi lenh hien chu (Tj / TJ / ' / ") trong BT..ET  -> 1 doi tuong CHU
- Chuoi lenh dung path + 1 lenh to/ve (f, S, B...)   -> 1 doi tuong HINH
  (path ket thuc bang `n` khong tao doi tuong — thuong la clip)
- Do (XObject: anh hoac form)                        -> 1 doi tuong
- Anh noi dong BI..EI                                -> 1 doi tuong ANH
- sh                                                 -> 1 doi tuong TO MAU
Truoc khi ap dung, thu tu/loai slot duoc DOI CHIEU voi danh sach doi tuong
pdfium; lech la tu choi (an toan hon la sua sai cho).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pikepdf

from ..utils.errors import FriendlyError

PAINT_OPS = {"f", "F", "f*", "B", "B*", "b", "b*", "S", "s"}
PATH_CONSTRUCT = {"m", "l", "c", "v", "y", "re", "h"}
SHOW_OPS = {"Tj", "TJ", "'", '"'}

# FPDF_PAGEOBJ_*: 1=text 2=path 3=image 4=shading 5=form
_KIND_TO_PDFIUM = {"text": (1,), "path": (2,), "xobj": (3, 5),
                   "image": (3,), "shading": (4,)}


@dataclass
class Slot:
    kind: str                 # 'text' | 'path' | 'xobj' | 'image' | 'shading'
    span: tuple[int, int]     # [dau, cuoi] chi so lenh (bao gom 2 dau)
    show_index: int = -1      # lenh hien chu (voi text)
    block: tuple = ()         # (bt_index, et_index, so_show_trong_block)
    has_clip: bool = False    # nhom path co W/W* (dung lam clip)


def parse_slots(instructions) -> list[Slot]:
    """Phan tich danh sach lenh thanh cac slot doi tuong theo thu tu ve."""
    slots: list[Slot] = []
    in_text = False
    bt_index = -1
    block_slots: list[Slot] = []
    path_start = -1
    path_has_clip = False

    for idx, inst in enumerate(instructions):
        if isinstance(inst, pikepdf.ContentStreamInlineImage):
            slots.append(Slot(kind="image", span=(idx, idx)))
            continue
        op = str(inst.operator)
        if op == "BT":
            in_text = True
            bt_index = idx
            block_slots = []
        elif op == "ET":
            in_text = False
            for s in block_slots:
                s.block = (bt_index, idx, len(block_slots))
        elif op in SHOW_OPS and in_text:
            s = Slot(kind="text", span=(idx, idx), show_index=idx)
            block_slots.append(s)
            slots.append(s)
        elif op in PATH_CONSTRUCT:
            if path_start < 0:
                path_start = idx
        elif op in ("W", "W*"):
            path_has_clip = True
        elif op in PAINT_OPS:
            start = path_start if path_start >= 0 else idx
            slots.append(Slot(kind="path", span=(start, idx),
                              has_clip=path_has_clip))
            path_start = -1
            path_has_clip = False
        elif op == "n":
            path_start = -1
            path_has_clip = False
        elif op == "Do":
            slots.append(Slot(kind="xobj", span=(idx, idx)))
        elif op == "sh":
            slots.append(Slot(kind="shading", span=(idx, idx)))
    return slots


def _matmul(a, b):
    """Nhan 2 ma tran PDF [a b c d e f] (a ap dung TRUOC b)."""
    a0, a1, a2, a3, a4, a5 = a
    b0, b1, b2, b3, b4, b5 = b
    return [a0 * b0 + a1 * b2, a0 * b1 + a1 * b3,
            a2 * b0 + a3 * b2, a2 * b1 + a3 * b3,
            a4 * b0 + a5 * b2 + b4, a4 * b1 + a5 * b3 + b5]


def _inv_local(M6, Dx, Dy):
    """Do lech DEVICE (Dx,Dy khong gian trang) -> do lech LOCAL de bu ma tran
    M (co the bi lat/xoay). Neu ma tran suy bien thi tra ve nguyen (Dx,Dy)."""
    a, b, c, d = M6[0], M6[1], M6[2], M6[3]
    det = a * d - b * c
    if abs(det) < 1e-9:
        return (Dx, Dy)
    ldx = (Dx * d - Dy * c) / det
    ldy = (-Dx * b + Dy * a) / det
    return (ldx, ldy)


def _snapshots(instructions):
    """Ghi lai CTM va text-matrix (Tlm) DANG HIEU LUC truoc moi lenh — de tinh
    dung huong dich cho tung doi tuong (ho tro trang co he toa do bi lat)."""
    ctm_at = []
    tm_at = []
    ctm = [1, 0, 0, 1, 0, 0]
    stack = []
    tm = [1, 0, 0, 1, 0, 0]
    tlm = [1, 0, 0, 1, 0, 0]
    leading = 0.0
    for inst in instructions:
        ctm_at.append(list(ctm))
        tm_at.append(list(tm))
        if isinstance(inst, pikepdf.ContentStreamInlineImage):
            continue
        op = str(inst.operator)
        o = inst.operands
        try:
            if op == "q":
                stack.append(list(ctm))
            elif op == "Q":
                ctm = stack.pop() if stack else [1, 0, 0, 1, 0, 0]
            elif op == "cm":
                ctm = _matmul([float(v) for v in o], ctm)
            elif op == "BT":
                tm = [1, 0, 0, 1, 0, 0]
                tlm = [1, 0, 0, 1, 0, 0]
            elif op == "TL":
                leading = float(o[0])
            elif op == "Tm":
                tm = [float(v) for v in o]
                tlm = list(tm)
            elif op in ("Td", "TD"):
                if op == "TD":
                    leading = -float(o[1])
                tlm = _matmul([1, 0, 0, 1, float(o[0]), float(o[1])], tlm)
                tm = list(tlm)
            elif op == "T*":
                tlm = _matmul([1, 0, 0, 1, 0, -leading], tlm)
                tm = list(tlm)
        except Exception:
            pass
    return ctm_at, tm_at


def slot_bboxes(instructions):
    """Khung bao (l,b,r,t) trong KHONG GIAN TRANG cho tung slot, song song
    voi parse_slots (cung thu tu, cung do dai). Chi tinh cho slot PATH
    (dung khi pdfium khong tra duoc vi tri doi tuong ve); slot khac = None.

    Dung de dinh vi doi tuong ve tren nhung file ma pdfium get_bounds/get_pos
    bao loi -> app van chon & xoa duoc.
    """
    boxes = []
    ctm = [1, 0, 0, 1, 0, 0]
    stack = []
    in_text = False
    pts = []  # diem (da bien doi CTM) cua path dang dung

    def tf(x, y):
        return (ctm[0] * x + ctm[2] * y + ctm[4],
                ctm[1] * x + ctm[3] * y + ctm[5])

    def flush_path():
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    for inst in instructions:
        if isinstance(inst, pikepdf.ContentStreamInlineImage):
            boxes.append(None)
            continue
        op = str(inst.operator)
        o = inst.operands
        try:
            if op == "BT":
                in_text = True
            elif op == "ET":
                in_text = False
            elif op == "q":
                stack.append(list(ctm))
            elif op == "Q":
                ctm = stack.pop() if stack else [1, 0, 0, 1, 0, 0]
            elif op == "cm":
                ctm = _matmul([float(v) for v in o], ctm)
            elif op in SHOW_OPS and in_text:
                boxes.append(None)          # slot chu
            elif op in PATH_CONSTRUCT:
                if op in ("m", "l"):
                    pts.append(tf(float(o[0]), float(o[1])))
                elif op == "c":
                    pts.append(tf(float(o[0]), float(o[1])))
                    pts.append(tf(float(o[2]), float(o[3])))
                    pts.append(tf(float(o[4]), float(o[5])))
                elif op in ("v", "y"):
                    pts.append(tf(float(o[0]), float(o[1])))
                    pts.append(tf(float(o[2]), float(o[3])))
                elif op == "re":
                    x, y, w, h = [float(v) for v in o]
                    pts.append(tf(x, y))
                    pts.append(tf(x + w, y))
                    pts.append(tf(x, y + h))
                    pts.append(tf(x + w, y + h))
                # 'h' (dong path) khong them diem
            elif op in PAINT_OPS:
                boxes.append(flush_path())  # slot path
                pts = []
            elif op == "n":
                pts = []                    # clip/no-op: khong tao slot
            elif op == "Do":
                boxes.append(None)          # slot xobj
            elif op == "sh":
                boxes.append(None)          # slot to mau
        except Exception:
            # Lenh la -> neu la paint van phai giu dong bo so luong slot
            if op in PAINT_OPS:
                boxes.append(None)
                pts = []
    return boxes


def verify_slots(slots: list[Slot], pdfium_types: list[int]):
    """Doi chieu slot voi danh sach loai doi tuong tu pdfium."""
    if len(slots) != len(pdfium_types):
        raise FriendlyError(
            "Cấu trúc trang này phức tạp hơn dự kiến nên chưa chỉnh sửa "
            "an toàn được.\nSếp có thể dùng \"Che trắng\" để che nội dung "
            "thay vì xóa/di chuyển.")
    for s, t in zip(slots, pdfium_types):
        if t not in _KIND_TO_PDFIUM[s.kind]:
            raise FriendlyError(
                "Cấu trúc trang này phức tạp hơn dự kiến nên chưa chỉnh sửa "
                "an toàn được.\nSếp có thể dùng \"Che trắng\" để che nội dung "
                "thay vì xóa/di chuyển.")


def _op(operands, operator):
    return pikepdf.ContentStreamInstruction(
        operands, pikepdf.Operator(operator))


def _neutralize_show(inst):
    """Thay lenh hien chu bang lenh giu nguyen trang thai dong chu.

    Tj/TJ: bo han. ': xuong dong (T*). ": dat gian cach roi xuong dong.
    Tra ve danh sach lenh thay the.
    """
    op = str(inst.operator)
    if op == "'":
        return [_op([], "T*")]
    if op == '"':
        aw, ac = inst.operands[0], inst.operands[1]
        return [_op([aw], "Tw"), _op([ac], "Tc"), _op([], "T*")]
    return []


def _nearest_clip_ops(instructions, target_idx: int) -> list[int]:
    """Chi so cac lenh W/W* (clip) DANG HIEU LUC bao quanh lenh `target_idx`.

    Nhieu file (xuat tu Excel) ve chu/hinh trong tung O bang va CLIP theo
    khung o (q ... khung ... W* n ... noi_dung ... Q). Khi DI CHUYEN noi dung
    ra khoi o, phan nam ngoai khung clip se bi CAT -> chu "mat dan". De doi
    tuong hien du sau khi keo, ta bo clip cua O chua no (bien W/W* -> path
    binh thuong roi `n` loai bo, khong con gioi han ve).

    Tra ve clip cua scope q...Q GAN NHAT co clip (bo qua clip o muc nen
    trang — scope goc — de khong lo noi dung ngoai trang).
    """
    def _clip_only(wi: int) -> bool:
        # Clip THUAN neu lenh to/ve ket thuc path sau W/W* la `n` (khong to,
        # khong ve). Neu la f/S/B... thi bo `W` se lam HIEN o to -> khong dung.
        for j in range(wi + 1, len(instructions)):
            nx = instructions[j]
            if isinstance(nx, pikepdf.ContentStreamInlineImage):
                continue
            nop = str(nx.operator)
            if nop == "n":
                return True
            if nop in PAINT_OPS:
                return False
            if nop in ("W", "W*"):
                continue
            # gap lenh khac (BT, cm, ...) truoc khi ket thuc path -> khong ro
            return False
        return False

    scopes: list[list[int]] = []
    for idx in range(min(target_idx, len(instructions))):
        ins = instructions[idx]
        if isinstance(ins, pikepdf.ContentStreamInlineImage):
            continue
        op = str(ins.operator)
        if op == "q":
            scopes.append([])
        elif op == "Q":
            if scopes:
                scopes.pop()
        elif op in ("W", "W*"):
            if scopes and _clip_only(idx):   # bo qua clip nen + clip kem to/ve
                scopes[-1].append(idx)
    for sc in reversed(scopes):
        if sc:
            return list(sc)
    return []


def apply_edits(instructions, slots: list[Slot], deletes: list[int],
                moves: dict[int, tuple[float, float]]):
    """Tao danh sach lenh moi: xoa cac slot `deletes`, dich cac slot `moves`.

    moves: {slot_index: (pdx, pdy)} — do lech theo KHONG GIAN TRANG (y len).
    Tra ve danh sach lenh moi.
    """
    delete_set = set(deletes)
    # Lenh chen truoc/sau tung vi tri + lenh bi xoa/thay the
    insert_before: dict[int, list] = {}
    insert_after: dict[int, list] = {}
    remove: set[int] = set()
    replace: dict[int, list] = {}

    for si in delete_set:
        s = slots[si]
        a, b = s.span
        if s.kind == "text":
            inst = instructions[s.show_index]
            rep = _neutralize_show(inst)
            if rep:
                replace[s.show_index] = rep
            else:
                remove.add(s.show_index)
        elif s.kind == "path" and s.has_clip:
            # Giu path + W (clip cho noi dung sau), chi bo net ve: paint -> n
            replace[b] = [_op([], "n")]
        else:
            for k in range(a, b + 1):
                remove.add(k)

    # (pdx,pdy) la do lech theo KHONG GIAN TRANG. Quy doi ve LOCAL theo ma
    # tran tai cho de dung huong ngay ca khi trang bi lat (y am).
    ctm_at, tm_at = (_snapshots(instructions) if moves else ([], []))
    for si, (pdx, pdy) in moves.items():
        if si in delete_set:
            continue
        s = slots[si]
        # Bo clip cua O bang chua doi tuong -> keo ra ngoai o van hien du chu
        # (khong bi khung o cat mat). Xem _nearest_clip_ops.
        anchor = (s.block[0] if (s.kind == "text" and s.block
                                 and s.block[0] >= 0) else s.span[0])
        for ci in _nearest_clip_ops(instructions, anchor):
            remove.add(ci)
        if s.kind == "text":
            bt, et, n_shows = s.block if s.block else (-1, -1, 99)
            if n_shows == 1 and bt >= 0:
                # Ca khoi BT..ET chi co 1 lenh chu -> boc q cm ... Q quanh khoi
                ldx, ldy = _inv_local(ctm_at[bt], pdx, pdy)
                cm = _op([1, 0, 0, 1, ldx, ldy], "cm")
                insert_before.setdefault(bt, []).extend([_op([], "q"), cm])
                insert_after.setdefault(et, []).append(_op([], "Q"))
            else:
                # Nhieu lenh chu chung khoi: dich bang cap Td doi xung (do lech
                # tinh theo Tlm*CTM tai lenh hien chu)
                si_i = s.show_index
                mtx = _matmul(tm_at[si_i], ctm_at[si_i])
                tdx, tdy = _inv_local(mtx, pdx, pdy)
                insert_before.setdefault(si_i, []).append(
                    _op([tdx, tdy], "Td"))
                insert_after.setdefault(si_i, []).append(
                    _op([-tdx, -tdy], "Td"))
        else:
            a, b = s.span
            ldx, ldy = _inv_local(ctm_at[a], pdx, pdy)
            cm = _op([1, 0, 0, 1, ldx, ldy], "cm")
            insert_before.setdefault(a, []).extend([_op([], "q"), cm])
            insert_after.setdefault(b, []).append(_op([], "Q"))

    out = []
    for idx, inst in enumerate(instructions):
        if idx in insert_before:
            out.extend(insert_before[idx])
        if idx in replace:
            out.extend(replace[idx])
        elif idx not in remove:
            out.append(inst)
        if idx in insert_after:
            out.extend(insert_after[idx])
    return out


def erase_by_region(src_path: str, password: str, page_index: int,
                    region: tuple, dest_path: str) -> int:
    """Xoa SACH moi net ve/chu/anh nam trong `region` (KHONG GIAN TRANG:
    l,b,r,t, goc duoi-trai) bang cach doc TOA DO VE THAT tu content stream.

    Khong phu thuoc pdfium get_bounds (co file pdfium bao sai toa do) -> luon
    xoa dung cho nguoi dung khoanh. Ghi ket qua ra dest_path. Tra ve so doi
    tuong da xoa.
    """
    rl, rb, rr, rt = region

    def inside(px, py):
        return rl <= px <= rr and rb <= py <= rt

    with pikepdf.open(src_path, password=password or "") as pdf:
        page = pdf.pages[page_index]
        try:
            instructions = list(pikepdf.parse_content_stream(page))
        except Exception:
            raise FriendlyError(
                "Không đọc được nội dung trang để xóa.") from None
        out = []
        ctm = [1, 0, 0, 1, 0, 0]
        stack = []
        in_text = False
        tm = [1, 0, 0, 1, 0, 0]
        tlm = [1, 0, 0, 1, 0, 0]
        leading = 0.0
        path_ops = []
        path_pts = []
        path_has_clip = False
        removed = 0

        def tf(x, y):
            return (ctm[0] * x + ctm[2] * y + ctm[4],
                    ctm[1] * x + ctm[3] * y + ctm[5])

        def add_pts(op, o):
            try:
                if op in ("m", "l"):
                    path_pts.append(tf(float(o[0]), float(o[1])))
                elif op == "c":
                    for k in (0, 2, 4):
                        path_pts.append(tf(float(o[k]), float(o[k + 1])))
                elif op in ("v", "y"):
                    path_pts.append(tf(float(o[0]), float(o[1])))
                    path_pts.append(tf(float(o[2]), float(o[3])))
                elif op == "re":
                    x, y, w, h = [float(v) for v in o]
                    path_pts.extend([tf(x, y), tf(x + w, y),
                                     tf(x, y + h), tf(x + w, y + h)])
            except Exception:
                pass

        for inst in instructions:
            if isinstance(inst, pikepdf.ContentStreamInlineImage):
                out.append(inst)
                continue
            op = str(inst.operator)
            o = inst.operands
            if op in PATH_CONSTRUCT:
                path_ops.append(inst)
                add_pts(op, o)
                continue
            if op in ("W", "W*"):
                path_ops.append(inst)
                path_has_clip = True
                continue
            if op in PAINT_OPS:
                drop = False
                if path_pts:
                    xs = [p[0] for p in path_pts]
                    ys = [p[1] for p in path_pts]
                    bl, bb, br, bt = min(xs), min(ys), max(xs), max(ys)
                    ix = max(bl, rl)
                    iy = max(bb, rb)
                    ix2 = min(br, rr)
                    iy2 = min(bt, rt)
                    inter = max(0.0, ix2 - ix) * max(0.0, iy2 - iy)
                    area = max((br - bl) * (bt - bb), 0.01)
                    drop = inter / area >= 0.6
                if drop:
                    removed += 1
                    if path_has_clip:
                        out.extend(path_ops)
                        out.append(_op([], "n"))  # giu clip, bo net ve
                    # else: bo han path_ops + lenh to/ve
                else:
                    out.extend(path_ops)
                    out.append(inst)
                path_ops = []
                path_pts = []
                path_has_clip = False
                continue
            if op == "n":
                out.extend(path_ops)
                out.append(inst)
                path_ops = []
                path_pts = []
                path_has_clip = False
                continue
            # --- trang thai do hoa / van ban ---
            if op == "q":
                stack.append(list(ctm))
            elif op == "Q":
                ctm = stack.pop() if stack else [1, 0, 0, 1, 0, 0]
            elif op == "cm":
                ctm = _matmul([float(v) for v in o], ctm)
            elif op == "BT":
                in_text = True
                tm = [1, 0, 0, 1, 0, 0]
                tlm = [1, 0, 0, 1, 0, 0]
            elif op == "ET":
                in_text = False
            elif op == "TL":
                leading = float(o[0])
            elif op == "Tm":
                tm = [float(v) for v in o]
                tlm = list(tm)
            elif op in ("Td", "TD"):
                if op == "TD":
                    leading = -float(o[1])
                tlm = _matmul([1, 0, 0, 1, float(o[0]), float(o[1])], tlm)
                tm = list(tlm)
            elif op == "T*":
                tlm = _matmul([1, 0, 0, 1, 0, -leading], tlm)
                tm = list(tlm)
            if op in SHOW_OPS and in_text:
                if op in ("'", '"'):   # xuong dong truoc khi hien
                    tlm = _matmul([1, 0, 0, 1, 0, -leading], tlm)
                    tm = list(tlm)
                m = _matmul(tm, ctm)
                if inside(m[4], m[5]):
                    removed += 1
                    out.extend(_neutralize_show(inst))
                else:
                    out.append(inst)
                continue
            if op == "Do":
                cx, cy = tf(0.5, 0.5)
                if inside(cx, cy):
                    removed += 1
                    continue
                out.append(inst)
                continue
            out.append(inst)

        data = pikepdf.unparse_content_stream(out)
        page.Contents = pdf.make_indirect(pikepdf.Stream(pdf, data))
        pdf.save(dest_path)
    return removed


def edit_page_content(src_path: str, password: str, page_index: int,
                      pdfium_types: list[int], deletes: list[int],
                      moves: dict[int, tuple[float, float]],
                      dest_path: str):
    """Doc file, phau thuat content stream cua 1 trang, ghi ra dest_path."""
    with pikepdf.open(src_path, password=password or "") as pdf:
        page = pdf.pages[page_index]
        try:
            instructions = list(pikepdf.parse_content_stream(page))
        except Exception:
            raise FriendlyError(
                "Không đọc được nội dung trang để chỉnh sửa.") from None
        slots = parse_slots(instructions)
        verify_slots(slots, pdfium_types)
        new_instructions = apply_edits(instructions, slots, deletes, moves)
        data = pikepdf.unparse_content_stream(new_instructions)
        page.Contents = pdf.make_indirect(pikepdf.Stream(pdf, data))
        pdf.save(dest_path)
