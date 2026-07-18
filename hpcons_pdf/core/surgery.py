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

    for si, (pdx, pdy) in moves.items():
        if si in delete_set:
            continue
        s = slots[si]
        cm = _op([1, 0, 0, 1, pdx, pdy], "cm")
        if s.kind == "text":
            bt, et, n_shows = s.block if s.block else (-1, -1, 99)
            if n_shows == 1 and bt >= 0:
                # Ca khoi BT..ET chi co 1 lenh chu -> boc q cm ... Q quanh khoi
                insert_before.setdefault(bt, []).extend([_op([], "q"), cm])
                insert_after.setdefault(et, []).append(_op([], "Q"))
            else:
                # Nhieu lenh chu chung khoi: dich bang cap Td doi xung
                insert_before.setdefault(s.show_index, []).append(
                    _op([pdx, pdy], "Td"))
                insert_after.setdefault(s.show_index, []).append(
                    _op([-pdx, -pdy], "Td"))
        else:
            a, b = s.span
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
