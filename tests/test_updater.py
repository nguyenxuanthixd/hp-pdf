# -*- coding: utf-8 -*-
"""Test cap nhat: so sanh version, doc Release API (gia lap urlopen), tai file.
Chay: python tests/test_updater.py
"""
import io
import json
import os
import sys
import tempfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import hpcons_pdf
from hpcons_pdf.core import updater
from hpcons_pdf.utils.errors import FriendlyError

passed, failed = [], []


def check(name, fn):
    try:
        fn()
        passed.append(name)
        print(f"  OK   {name}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        failed.append((name, repr(e)))
        print(f"  FAIL {name}: {e!r}")


class FakeResp:
    def __init__(self, data: bytes, headers=None):
        self._d = data
        self.headers = headers or {}
        self._pos = 0

    def read(self, n=-1):
        if n is None or n < 0:
            chunk = self._d[self._pos:]
            self._pos = len(self._d)
        else:
            chunk = self._d[self._pos:self._pos + n]
            self._pos += n
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_release(tag, asset_name="HPConsPDF_Setup_9.9.9.exe",
                  body="Sua loi, them tinh nang."):
    return json.dumps({
        "tag_name": tag,
        "body": body,
        "assets": [
            {"name": "checksum.txt", "browser_download_url": "http://x/c.txt",
             "size": 10},
            {"name": asset_name,
             "browser_download_url": "http://x/" + asset_name, "size": 12345},
        ],
    }).encode("utf-8")


# ---- 1. So sanh version ----
def t_version():
    assert updater._parse_version("v1.2.3") == (1, 2, 3)
    assert updater._parse_version("1.0") == (1, 0, 0)
    assert updater.is_newer("1.0.1", "1.0.0")
    assert updater.is_newer("v2.0.0", "1.9.9")
    assert not updater.is_newer("1.0.0", "1.0.0")
    assert not updater.is_newer("0.9.0", "1.0.0")
check("so sanh so phien ban", t_version)


# ---- 2. check_latest: co ban moi hon ----
def t_check_newer():
    hpcons_pdf.APP_VERSION = "1.0.0"
    updater.APP_VERSION = "1.0.0"
    orig = urllib.request.urlopen
    urllib.request.urlopen = lambda *a, **k: FakeResp(_fake_release("v1.2.0"))
    try:
        info = updater.check_latest()
    finally:
        urllib.request.urlopen = orig
    assert info is not None
    assert info.version == "1.2.0", info.version
    assert info.asset_name.endswith(".exe")
    assert info.url.endswith(".exe")
    assert "tinh nang" in info.notes
    assert info.size == 12345
check("check_latest: phat hien ban moi + dung asset .exe", t_check_newer)


# ---- 3. check_latest: da moi nhat -> None ----
def t_check_uptodate():
    updater.APP_VERSION = "2.0.0"
    orig = urllib.request.urlopen
    urllib.request.urlopen = lambda *a, **k: FakeResp(_fake_release("v1.5.0"))
    try:
        assert updater.check_latest() is None
    finally:
        urllib.request.urlopen = orig
        updater.APP_VERSION = "1.0.0"
check("check_latest: dang dung ban moi nhat -> None", t_check_uptodate)


# ---- 4. Loi mang -> FriendlyError (de UI im lang khi tu dong) ----
def t_check_offline():
    import urllib.error
    orig = urllib.request.urlopen

    def boom(*a, **k):
        raise urllib.error.URLError("offline")
    urllib.request.urlopen = boom
    try:
        try:
            updater.check_latest()
            assert False, "phai nem FriendlyError"
        except FriendlyError:
            pass
    finally:
        urllib.request.urlopen = orig
check("offline -> FriendlyError (khong crash)", t_check_offline)


# ---- 5. download: ghi dung file + goi progress ----
def t_download():
    info = updater.UpdateInfo(version="1.2.0", url="http://x/setup.exe",
                              notes="", size=8, asset_name="setup.exe")
    payload = b"ABCDEFGH" * 10000  # 80000 bytes
    orig = urllib.request.urlopen
    urllib.request.urlopen = lambda *a, **k: FakeResp(
        payload, {"Content-Length": str(len(payload))})
    dest = os.path.join(tempfile.gettempdir(), "hpcons_upd_test.exe")
    if os.path.exists(dest):
        os.remove(dest)
    calls = []
    try:
        p = updater.download(info, dest, progress=lambda c, t, m: calls.append(c))
    finally:
        urllib.request.urlopen = orig
    assert os.path.getsize(p) == len(payload)
    assert calls and calls[-1] == len(payload)
    assert not os.path.exists(dest + ".part")  # da doi ten
    os.remove(dest)
check("download: ghi file + tien trinh", t_download)


# ---- 6. Version trong __init__ va installer.iss khop nhau ----
def t_version_sync():
    import re
    iss = open(os.path.join(ROOT, "installer.iss"), encoding="utf-8").read()
    m = re.search(r'#define AppVersion "([^"]+)"', iss)
    init = open(os.path.join(ROOT, "hpcons_pdf", "__init__.py"),
                encoding="utf-8").read()
    m2 = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', init)
    assert m and m2 and m.group(1) == m2.group(1), (m and m.group(1),
                                                    m2 and m2.group(1))
check("version __init__.py == installer.iss", t_version_sync)


print()
print(f"KET QUA: {len(passed)} OK, {len(failed)} FAIL")
sys.exit(1 if failed else 0)
