"""In noi dung cap nhat cua 1 phien ban tu CHANGELOG.md.

Dung trong GitHub Actions de dat lam noi dung Release (thay vi link github).
    python tools/changelog.py v1.0.9  > notes.txt
Neu khong tim thay muc -> in dong mac dinh (khong loi).
"""
import os
import sys


def section_for(version: str) -> str:
    ver = version.lstrip("vV").strip()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "CHANGELOG.md")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    out = []
    grabbing = False
    for ln in lines:
        s = ln.strip()
        if s.startswith("## "):
            head = s[3:].lstrip("vV").strip()
            if grabbing:
                break                 # sang muc phien ban khac -> dung
            grabbing = (head == ver)
            continue
        if grabbing:
            out.append(ln)
    return "\n".join(out).strip()


if __name__ == "__main__":
    v = sys.argv[1] if len(sys.argv) > 1 else ""
    text = section_for(v)
    if not text:
        text = f"Phiên bản {v.lstrip('vV')} — xem chi tiết trong ứng dụng."
    sys.stdout.write(text + "\n")
