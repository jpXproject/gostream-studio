# src/ui/widgets.py
# GoStream - widgets khusus (region overlay, timer label)
# Developed by jpXCode

from PySide6.QtWidgets import QWidget, QLabel, QApplication
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QPainter, QPen, QColor


# ---------------------------------------------------------------------------
# Overlay pemilihan region (drag area)
# ---------------------------------------------------------------------------
class RegionOverlay(QWidget):
    region_selected = Signal(int, int, int, int)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setStyleSheet("background-color: rgba(0,0,0,80);")
        screen = QApplication.primaryScreen()
        self.setGeometry(screen.geometry())
        self.setMouseTracking(True)
        self.start_pos = None
        self.end_pos = None

    def mousePressEvent(self, event):
        self.start_pos = event.pos()
        self.end_pos = event.pos()
        self.update()

    def mouseMoveEvent(self, event):
        if self.start_pos is not None:
            self.end_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if self.start_pos and self.end_pos:
            rect = QRect(self.start_pos, self.end_pos).normalized()
            if rect.width() > 8 and rect.height() > 8:
                self.region_selected.emit(rect.x(), rect.y(), rect.width(), rect.height())
        self.close()

    def paintEvent(self, event):
        if not (self.start_pos and self.end_pos):
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRect(self.start_pos, self.end_pos).normalized()
        p.setPen(QPen(QColor(0, 180, 255), 2))
        p.drawRect(rect)
        # label ukuran
        p.setPen(QColor(255, 255, 255))
        p.drawText(rect.x() + 6, rect.y() - 10, f"{rect.width()} x {rect.height()}")


# ---------------------------------------------------------------------------
# Timer label HH:MM:SS
# ---------------------------------------------------------------------------
class TimerLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__("00:00:00", parent)
        self.setAlignment(Qt.AlignCenter)

    def setSeconds(self, s):
        s = max(0, int(s))
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        self.setText(f"{h:02d}:{m:02d}:{sec:02d}")
