"""Duong dan tai nguyen (logo, icon) - tuong thich PyInstaller onefile."""
import os
import sys


def resource_path(name: str) -> str:
    """Tra ve duong dan tuyet doi toi file tai nguyen.

    Khi dong goi PyInstaller onefile, tai nguyen nam trong sys._MEIPASS.
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, name)
    # Thu muc goc du an (cha cua package hpcons_pdf)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, name)


def logo_path() -> str:
    return resource_path("logo.png")


def icon_path() -> str:
    p = resource_path("logo.ico")
    return p if os.path.exists(p) else logo_path()
