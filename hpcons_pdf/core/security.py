"""Bao mat: dat/go mat khau mo file, dat quyen (cam in / cam copy / cam sua)."""
from __future__ import annotations

import pikepdf

from ..utils.errors import FriendlyError
from ..utils.fileutils import save_via_temp


def encrypt_pdf(src_path: str, dest_path: str, *, user_password: str = "",
                owner_password: str = "", allow_print: bool = True,
                allow_copy: bool = True, allow_modify: bool = True,
                current_password: str = "") -> str:
    """Dat mat khau / quyen cho PDF -> file moi (ma hoa AES-256)."""
    if not user_password and not owner_password:
        raise FriendlyError("Vui lòng nhập ít nhất một mật khẩu (mở file hoặc chủ sở hữu).")
    if not owner_password:
        owner_password = user_password
    perms = pikepdf.Permissions(
        print_lowres=allow_print,
        print_highres=allow_print,
        extract=allow_copy,
        accessibility=True,
        modify_annotation=allow_modify,
        modify_assembly=allow_modify,
        modify_form=allow_modify,
        modify_other=allow_modify,
    )
    with pikepdf.open(src_path, password=current_password or "") as pdf:
        enc = pikepdf.Encryption(owner=owner_password, user=user_password,
                                 R=6, allow=perms)
        return save_via_temp(lambda t: pdf.save(t, encryption=enc), dest_path)


def decrypt_pdf(src_path: str, dest_path: str, *, password: str) -> str:
    """Go mat khau khoi PDF -> file moi khong ma hoa."""
    try:
        pdf = pikepdf.open(src_path, password=password or "")
    except pikepdf.PasswordError:
        raise FriendlyError("Mật khẩu không đúng. Vui lòng kiểm tra lại.") from None
    with pdf:
        return save_via_temp(lambda t: pdf.save(t, encryption=False), dest_path)


def is_encrypted(path: str) -> bool:
    try:
        with pikepdf.open(path):
            return False
    except pikepdf.PasswordError:
        return True
    except Exception:
        return False
