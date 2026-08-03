# src/app.py
# GoStream - Live Streaming Ringan
# Developed by jpXCode

import sys
import ctypes
from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow

# Windows 10 2004+: window dengan affinity ini TIDAK tampil di semua
# screen capture (GDI/DXGI) — jadi GoStream sendiri tidak ikut terekam.
WDA_EXCLUDEFROMCAPTURE = 0x00000011


def _hide_from_capture(hwnd):
    """Sembunyikan window GoStream dari capture layar (ala OBS)."""
    try:
        ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)
        return True
    except Exception:
        return False


def run_app():
    app = QApplication(sys.argv)
    app.setApplicationName("GoStream")
    app.setOrganizationName("jpXCode")

    window = MainWindow()
    window.show()
    # terapkan setelah window muncul (native handle harus sudah ada)
    hwnd = int(window.winId())
    if _hide_from_capture(hwnd):
        window.log("🕶 Window GoStream disembunyikan dari capture layar")
    sys.exit(app.exec())
