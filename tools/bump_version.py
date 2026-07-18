# -*- coding: utf-8 -*-
"""Dong bo so phien ban vao ca 2 noi: hpcons_pdf/__init__.py va installer.iss.

Dung:  python tools/bump_version.py 1.0.2
       python tools/bump_version.py v1.0.2     (dau 'v' se duoc bo)
GitHub Actions goi voi ten tag; local co the goi trong release.bat.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INIT = os.path.join(ROOT, "hpcons_pdf", "__init__.py")
ISS = os.path.join(ROOT, "installer.iss")


def _norm(v: str) -> str:
    v = v.strip().lstrip("vV")
    if not re.fullmatch(r"\d+\.\d+\.\d+", v):
        raise SystemExit(f"Phien ban khong hop le: {v!r} (can dang x.y.z)")
    return v


def _replace(path, pattern, repl, label):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    new, n = re.subn(pattern, repl, text, count=1)
    if n != 1:
        raise SystemExit(f"Khong tim thay cho cap nhat version trong {label}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Dung: python tools/bump_version.py <x.y.z>")
    ver = _norm(sys.argv[1])
    _replace(INIT, r'APP_VERSION\s*=\s*"[^"]*"',
             f'APP_VERSION = "{ver}"', "__init__.py")
    _replace(ISS, r'#define AppVersion "[^"]*"',
             f'#define AppVersion "{ver}"', "installer.iss")
    print(f"Da dat version = {ver}")


if __name__ == "__main__":
    main()
