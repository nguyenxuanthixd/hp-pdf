"""HP Cons PDF — diem khoi chay ung dung.

App chay MOT PHIEN DUY NHAT (single-instance): neu da co cua so dang chay,
file mo tu ngoai (double-click Explorer / keo len icon taskbar / dong lenh)
duoc chuyen vao cua so do -> mo THEM TAB, khong bung cua so moi.
"""
import getpass
import os
import sys

from PyQt6.QtCore import QByteArray
from PyQt6.QtGui import QIcon
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication

from hpcons_pdf import APP_NAME, ORG_NAME
from hpcons_pdf.resources import icon_path
from hpcons_pdf.ui.main_window import MainWindow
from hpcons_pdf.ui.theme import STYLESHEET

try:
    SERVER_NAME = "HPConsPDF_" + getpass.getuser()
except Exception:
    SERVER_NAME = "HPConsPDF"


def _pdf_args(argv) -> list[str]:
    return [os.path.abspath(a) for a in argv[1:]
            if a.lower().endswith(".pdf") and os.path.exists(a)]


def _send_to_running(paths: list[str]) -> bool:
    """Neu da co phien dang chay: gui danh sach file roi tra ve True."""
    sock = QLocalSocket()
    sock.connectToServer(SERVER_NAME)
    if not sock.waitForConnected(400):
        return False
    payload = "\n".join(paths).encode("utf-8")
    sock.write(QByteArray(payload))
    sock.flush()
    sock.waitForBytesWritten(2000)
    sock.disconnectFromServer()
    if sock.state() != QLocalSocket.LocalSocketState.UnconnectedState:
        sock.waitForDisconnected(1000)
    return True


def _open_in_running_window(paths: list[str]):
    """Mo cac file vao cua so chinh dang chay (them tab), dua len truoc."""
    wins = [w for w in MainWindow._instances if w.isVisible()] \
        or MainWindow._instances
    if not wins:
        return
    win = wins[0]
    win.showNormal()          # neu dang thu nho thi bung lai
    win.raise_()
    win.activateWindow()
    for p in paths:
        win.open_path(p)


def main():
    paths = _pdf_args(sys.argv)

    # Neu da co phien chay -> chuyen file sang do roi thoat (khong mo cua so moi)
    probe = QApplication(sys.argv)  # can QApplication de dung QLocalSocket
    try:
        if _send_to_running(paths):
            return
    except Exception:
        pass
    # Chi co the co 1 QApplication; dung lai cai vua tao
    app = probe
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(QIcon(icon_path()))

    # Lang nghe cac phien sau gui file toi
    QLocalServer.removeServer(SERVER_NAME)  # don server cu neu app tung crash
    server = QLocalServer()
    server.listen(SERVER_NAME)

    def on_connection():
        conn = server.nextPendingConnection()
        if conn is None:
            return
        if conn.waitForReadyRead(2000):
            data = bytes(conn.readAll().data()).decode("utf-8", "ignore")
            new_paths = [p for p in data.split("\n") if p.strip()]
        else:
            new_paths = []
        conn.disconnectFromServer()
        _open_in_running_window(new_paths)

    server.newConnection.connect(on_connection)

    win = MainWindow()
    win.show()
    for p in paths:
        win.open_path(p)

    code = app.exec()
    server.close()
    sys.exit(code)


if __name__ == "__main__":
    main()
