"""Cau hinh nguoi dung - luu file JSON tai %APPDATA%/HPConsPDF/config.json."""
import json
import os

_DEFAULTS = {
    "out_dir": "",                # thu muc xuat mac dinh ("" = cung thu muc file goc)
    "last_open_dir": "",
    "ocr_langs": ["vie", "eng"],
    "ocr_dpi": 300,
    "tesseract_path": "",         # de trong = tu dong tim
    "number": {
        "position": "bottom-center",
        "font": "Arial",
        "size": 11,
        "format": "Trang {n}/{total}",
        "start": 1,
        "margin_mm": 10,
    },
    "watermark_text": "TÀI LIỆU ĐẤU THẦU – HP CONS",
    "recent_files": [],
    "last_printer": "",           # may in chon lan cuoi (nho cho lan in sau)
    "auto_check_update": True,    # tu kiem tra cap nhat khi khoi dong
    "skip_update_version": "",    # phien ban nguoi dung chon "bo qua"
}


def config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "HPConsPDF")
    os.makedirs(d, exist_ok=True)
    return d


def _config_file() -> str:
    return os.path.join(config_dir(), "config.json")


class Config:
    def __init__(self):
        self._data = dict(_DEFAULTS)
        self.load()

    def load(self):
        try:
            with open(_config_file(), "r", encoding="utf-8") as f:
                stored = json.load(f)
            for k, v in stored.items():
                if k == "number" and isinstance(v, dict):
                    merged = dict(_DEFAULTS["number"])
                    merged.update(v)
                    self._data["number"] = merged
                else:
                    self._data[k] = v
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            with open(_config_file(), "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def get(self, key, default=None):
        return self._data.get(key, default if default is not None else _DEFAULTS.get(key))

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def add_recent(self, path: str):
        rec = [p for p in self._data.get("recent_files", []) if p != path]
        rec.insert(0, path)
        self._data["recent_files"] = rec[:10]
        self.save()


# Singleton dung chung toan app
config = Config()
