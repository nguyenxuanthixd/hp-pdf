# -*- coding: utf-8 -*-
"""Tao file PDF mau cho test. Chay: python tests/fixtures.py"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WORK = os.path.join(tempfile.gettempdir(), "hpcons_smoke")
os.makedirs(WORK, exist_ok=True)

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def ensure_font():
    try:
        pdfmetrics.getFont("ArialT")
    except Exception:
        pdfmetrics.registerFont(TTFont("ArialT", r"C:\Windows\Fonts\arial.ttf"))


def make_all():
    ensure_font()
    sample1 = os.path.join(WORK, "hồ sơ thầu 布局.pdf")
    c = canvas.Canvas(sample1, pagesize=(595, 842))
    for i in range(6):
        c.setFont("ArialT", 20)
        c.drawString(60, 780, f"HỒ SƠ ĐẤU THẦU — Trang gốc {i+1}")
        c.setFont("ArialT", 12)
        c.drawString(60, 740, "Công ty xây dựng HP Cons — tài liệu kỹ thuật")
        c.rect(50, 60, 495, 700)
        c.showPage()
    c.save()

    sample2 = os.path.join(WORK, "phụ lục.pdf")
    c = canvas.Canvas(sample2, pagesize=(595, 842))
    for i in range(3):
        c.setFont("ArialT", 18)
        c.drawString(60, 780, f"PHỤ LỤC {i+1}")
        c.showPage()
    c.save()
    return WORK


if __name__ == "__main__":
    make_all()
    print("fixtures OK:", os.listdir(WORK))
