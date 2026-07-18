"""Kiem tra & tai ban cap nhat tu GitHub Releases (chi dung thu vien chuan).

App chay OFFLINE van binh thuong: moi loi mang deu duoc bat, khong chan.
Repo phai la PUBLIC de tai asset khong can token.
"""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass

from .. import APP_VERSION
from ..utils.errors import FriendlyError

# ====== Repo GitHub (public) chua ban phat hanh ======
GITHUB_OWNER = "nguyenxuanthixd"    # tai khoan GitHub
GITHUB_REPO = "hp-pdf"              # ten repository (public)
# =====================================================

API_LATEST = (f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
              "/releases/latest")
_UA = "HPConsPDF-Updater"
_CHECK_TIMEOUT = 8
_DL_TIMEOUT = 60


@dataclass
class UpdateInfo:
    version: str          # vd "1.0.2"
    url: str              # link tai installer .exe
    notes: str            # ghi chu phat hanh
    size: int             # byte
    asset_name: str       # ten file installer


def _parse_version(s: str) -> tuple[int, int, int]:
    s = (s or "").lstrip("vV").strip()
    out = []
    for part in s.split(".")[:3]:
        digits = ""
        for ch in part:
            if ch.isdigit():
                digits += ch
            else:
                break
        out.append(int(digits) if digits else 0)
    while len(out) < 3:
        out.append(0)
    return (out[0], out[1], out[2])


def is_newer(latest: str, current: str) -> bool:
    return _parse_version(latest) > _parse_version(current)


def _open(url: str, timeout: int):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "User-Agent": _UA})
    ctx = ssl.create_default_context()
    return urllib.request.urlopen(req, timeout=timeout, context=ctx)


def check_latest(progress=None, cancel=None) -> UpdateInfo | None:
    """Tra ve UpdateInfo neu co ban MOI HON dang dung; None neu da moi nhat.

    Nem FriendlyError khi loi mang (de UI quyet dinh im lang hay bao)."""
    try:
        with _open(API_LATEST, _CHECK_TIMEOUT) as r:
            data = json.load(r)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as e:
        raise FriendlyError(
            "Không kết nối được để kiểm tra cập nhật.\n"
            "Hãy kiểm tra kết nối mạng rồi thử lại.") from e

    tag = data.get("tag_name", "")
    if not tag or not is_newer(tag, APP_VERSION):
        return None
    asset = next((a for a in data.get("assets", [])
                  if a.get("name", "").lower().endswith(".exe")), None)
    if asset is None:
        return None
    return UpdateInfo(
        version=tag.lstrip("vV"),
        url=asset["browser_download_url"],
        notes=(data.get("body") or "").strip(),
        size=int(asset.get("size", 0)),
        asset_name=asset["name"])


def download(info: UpdateInfo, dest_path: str, progress=None, cancel=None) -> str:
    """Tai installer ve dest_path. progress(cur, total, msg); cancel=Event."""
    try:
        req = urllib.request.Request(info.url, headers={"User-Agent": _UA})
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=_DL_TIMEOUT, context=ctx) as r:
            total = int(r.headers.get("Content-Length", info.size or 0))
            got = 0
            tmp = dest_path + ".part"
            with open(tmp, "wb") as f:
                while True:
                    if cancel is not None and cancel.is_set():
                        raise FriendlyError("Đã hủy tải cập nhật.")
                    chunk = r.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    if progress:
                        mb = got / 1048576
                        tot_mb = total / 1048576 if total else 0
                        progress(got, total or got,
                                 f"Đang tải bản cập nhật {mb:.1f}"
                                 + (f"/{tot_mb:.1f} MB" if total else " MB"))
        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.replace(tmp, dest_path)
        return dest_path
    except FriendlyError:
        raise
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise FriendlyError(
            "Tải bản cập nhật thất bại.\n"
            "Hãy kiểm tra mạng và thử lại sau.") from e
