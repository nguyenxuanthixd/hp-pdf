# -*- coding: utf-8 -*-
"""Test single-instance: phien thu 2 gui duong dan file sang phien dang chay,
phien dang chay mo file vao cua so hien co (them tab), khong bung cua so moi.
Chay: python tests/test_single_instance.py
"""
import os
import sys
import faulthandler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
faulthandler.dump_traceback_later(60, exit=True)

from fixtures import make_all  # noqa: E402

WORK = make_all()
s1 = os.path.join(WORK, "hồ sơ thầu 布局.pdf")
s2 = os.path.join(WORK, "phụ lục.pdf")

from PyQt6.QtCore import QByteArray, QTimer  # noqa: E402
from PyQt6.QtNetwork import QLocalServer, QLocalSocket  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from hpcons_pdf.ui.main_window import MainWindow  # noqa: E402

app = QApplication(sys.argv)
errors = []
SRV = "HPConsPDF_test_" + str(os.getpid())


def run():
    try:
        # ---- Phien "dang chay": mo cua so + lang nghe server ----
        win = MainWindow()
        win.show()
        win.open_path(s1)
        assert win.tabs.count() == 1
        first_win_id = id(win)

        QLocalServer.removeServer(SRV)
        server = QLocalServer()
        assert server.listen(SRV)
        received = {}

        def on_conn():
            conn = server.nextPendingConnection()
            if conn.waitForReadyRead(2000):
                data = bytes(conn.readAll().data()).decode("utf-8")
                paths = [p for p in data.split("\n") if p.strip()]
            else:
                paths = []
            conn.disconnectFromServer()
            received["paths"] = paths
            # mo vao cua so dang co (them tab), khong tao cua so moi
            wins = [w for w in MainWindow._instances if w.isVisible()]
            w = wins[0]
            for p in paths:
                w.open_path(p)

        server.newConnection.connect(on_conn)

        # ---- Phien "thu 2": ket noi + gui path s2 ----
        sock = QLocalSocket()
        sock.connectToServer(SRV)
        assert sock.waitForConnected(1000), "phai ket noi duoc server"
        sock.write(QByteArray(s2.encode("utf-8")))
        sock.flush()
        sock.waitForBytesWritten(2000)
        sock.disconnectFromServer()

        # cho server xu ly
        for _ in range(30):
            app.processEvents()
            if received.get("paths"):
                break
            import time
            time.sleep(0.05)

        assert received.get("paths") == [s2], received
        # cung cua so, gio co 2 tab; KHONG co cua so moi
        assert len(MainWindow._instances) == 1, len(MainWindow._instances)
        assert win.tabs.count() == 2, win.tabs.count()
        assert id(MainWindow._instances[0]) == first_win_id

        server.close()
        print("SINGLE INSTANCE SMOKE: OK")
    except Exception as e:
        import traceback
        traceback.print_exc()
        errors.append(e)
        print(f"SINGLE INSTANCE SMOKE: FAIL {e!r}")
    finally:
        for w in list(MainWindow._instances):
            for i in range(w.tabs.count()):
                t = w.tabs.widget(i)
                if hasattr(t, "model"):
                    t.model.modified = False
            try:
                w.render_thread.stop()
            except Exception:
                pass
        QLocalServer.removeServer(SRV)
        app.quit()


QTimer.singleShot(300, run)
app.exec()
sys.exit(1 if errors else 0)
