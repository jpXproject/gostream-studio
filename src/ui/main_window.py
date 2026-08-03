# src/ui/main_window.py
# GoStream - Main Window (ringan, khusus live streaming)
# Developed by jpXCode

import os, json
from datetime import datetime
from PySide6.QtWidgets import *
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QPixmap, QImage
import win32gui

from ..theme_manager import THEMES, get_theme_style
from ..stream_engine import (
    StreamEngine, PLATFORMS, list_monitors, list_windows, list_webcams, list_dshow_audio,
)
from ..chat_reader import ChatReader
from ..ui.widgets import RegionOverlay, TimerLabel


class DeviceScanner(QThread):
    done = Signal(object)

    def __init__(self, ffmpeg):
        super().__init__()
        self.ffmpeg = ffmpeg

    def run(self):
        try:
            data = {
                "windows": list_windows(),
                "webcams": list_webcams(self.ffmpeg),
                "audio": list_dshow_audio(self.ffmpeg),
                "monitors": list_monitors(),
            }
        except Exception:
            data = {}
        self.done.emit(data)


class SourceDialog(QDialog):
    """Dialog tambah/edit source scene (teks, gambar, kotak, webcam, chat)."""
    TYPES = ["Teks", "Gambar", "Kotak", "Webcam", "Chat"]
    COLORS = {"Putih": [255, 255, 255], "Kuning": [0, 215, 255],
              "Hijau": [80, 220, 100], "Merah": [60, 60, 230],
              "Cyan": [255, 200, 60], "Oranye": [0, 140, 255]}

    def __init__(self, parent=None, src=None):
        super().__init__(parent)
        self.setWindowTitle("Source Scene")
        self.setMinimumWidth(340)
        self.src = dict(src or {})
        form = QFormLayout(self)
        self.type_combo = QComboBox()
        self.type_combo.addItems(self.TYPES)
        form.addRow("Tipe:", self.type_combo)
        self.x_spin = QSpinBox(); self.x_spin.setRange(0, 100); self.x_spin.setSuffix(" %")
        self.y_spin = QSpinBox(); self.y_spin.setRange(0, 100); self.y_spin.setSuffix(" %")
        form.addRow("Posisi X:", self.x_spin)
        form.addRow("Posisi Y:", self.y_spin)
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("teks overlay (mis. LIVE @jpXCode)")
        form.addRow("Teks:", self.text_edit)
        self.size_spin = QSpinBox(); self.size_spin.setRange(40, 300)
        self.size_spin.setSuffix(" %"); self.size_spin.setValue(100)
        form.addRow("Ukuran:", self.size_spin)
        self.thick_spin = QSpinBox(); self.thick_spin.setRange(1, 6); self.thick_spin.setValue(2)
        form.addRow("Tebal:", self.thick_spin)
        self.color_combo = QComboBox(); self.color_combo.addItems(list(self.COLORS.keys()))
        form.addRow("Warna:", self.color_combo)
        self.box_chk = QCheckBox("Latar belakang gelap")
        form.addRow("", self.box_chk)
        self.path_edit = QLineEdit(); self.path_edit.setReadOnly(True)
        btn_browse = QPushButton("Pilih...")
        btn_browse.clicked.connect(self._browse)
        prow = QHBoxLayout(); prow.addWidget(self.path_edit, 1); prow.addWidget(btn_browse)
        form.addRow("File:", prow)
        self.w_spin = QSpinBox(); self.w_spin.setRange(1, 100)
        self.w_spin.setSuffix(" %"); self.w_spin.setValue(25)
        self.h_spin = QSpinBox(); self.h_spin.setRange(1, 100)
        self.h_spin.setSuffix(" %"); self.h_spin.setValue(25)
        form.addRow("Lebar:", self.w_spin)
        form.addRow("Tinggi:", self.h_spin)
        self.opacity_spin = QDoubleSpinBox(); self.opacity_spin.setRange(0.1, 1.0)
        self.opacity_spin.setSingleStep(0.05); self.opacity_spin.setValue(1.0)
        form.addRow("Opacity:", self.opacity_spin)
        btns = QHBoxLayout()
        ok = QPushButton("Simpan"); ok.clicked.connect(self.accept)
        cn = QPushButton("Batal"); cn.clicked.connect(self.reject)
        btns.addStretch(); btns.addWidget(ok); btns.addWidget(cn)
        form.addRow(btns)
        self.type_combo.currentIndexChanged.connect(self._update_visibility)
        self._load_values()
        self._update_visibility()

    def _browse(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Pilih Gambar", "", "Gambar (*.png *.jpg *.jpeg *.webp *.bmp)")
        if f:
            self.path_edit.setText(f)

    def _load_values(self):
        s = self.src
        m = {"text": "Teks", "image": "Gambar", "box": "Kotak",
             "webcam": "Webcam", "chat": "Chat"}
        ti = max(0, self.TYPES.index(m.get(s.get("type"), "Teks")))
        self.type_combo.setCurrentIndex(ti)
        self.x_spin.setValue(int(s.get("x", 5)))
        self.y_spin.setValue(int(s.get("y", 5)))
        self.text_edit.setText(str(s.get("text", "")))
        self.size_spin.setValue(int(float(s.get("size", 1.0)) * 100))
        self.thick_spin.setValue(int(s.get("thickness", 2)))
        color = list(s.get("color", [255, 255, 255]))
        ci = next((i for i, (k, v) in enumerate(self.COLORS.items()) if list(v) == color), 0)
        self.color_combo.setCurrentIndex(max(0, ci))
        self.box_chk.setChecked(bool(s.get("box", False)))
        self.path_edit.setText(str(s.get("path", "")))
        self.w_spin.setValue(int(s.get("width", 25)))
        self.h_spin.setValue(int(s.get("height", 25)))
        self.opacity_spin.setValue(float(s.get("opacity", 1.0)))

    def _update_visibility(self):
        t = self.type_combo.currentText()
        rows = [self.text_edit, self.size_spin, self.thick_spin, self.color_combo,
                self.box_chk, self.path_edit, self.w_spin, self.h_spin, self.opacity_spin]
        for w in rows:
            w.setVisible(False)
        if t == "Teks":
            for w in (self.text_edit, self.size_spin, self.thick_spin, self.color_combo, self.box_chk):
                w.setVisible(True)
        elif t == "Gambar":
            for w in (self.path_edit, self.w_spin, self.h_spin, self.opacity_spin):
                w.setVisible(True)
        elif t == "Kotak":
            for w in (self.w_spin, self.h_spin, self.color_combo, self.opacity_spin):
                w.setVisible(True)
        elif t == "Webcam":
            for w in (self.w_spin, self.h_spin):
                w.setVisible(True)
        elif t == "Chat":
            for w in (self.size_spin, self.w_spin):
                w.setVisible(True)

    def result_src(self):
        t = self.type_combo.currentText()
        m = {"Teks": "text", "Gambar": "image", "Kotak": "box",
             "Webcam": "webcam", "Chat": "chat"}
        out = {"type": m[t], "x": self.x_spin.value(), "y": self.y_spin.value()}
        if t == "Teks":
            out.update({"text": self.text_edit.text(),
                        "size": self.size_spin.value() / 100.0,
                        "thickness": self.thick_spin.value(),
                        "color": self.COLORS[self.color_combo.currentText()],
                        "box": self.box_chk.isChecked()})
        elif t == "Gambar":
            out.update({"path": self.path_edit.text(), "width": self.w_spin.value(),
                        "height": self.h_spin.value(), "opacity": self.opacity_spin.value()})
        elif t == "Kotak":
            out.update({"w": self.w_spin.value(), "h": self.h_spin.value(),
                        "color": self.COLORS[self.color_combo.currentText()],
                        "opacity": self.opacity_spin.value()})
        elif t == "Webcam":
            out.update({"width": self.w_spin.value(), "height": self.h_spin.value()})
        elif t == "Chat":
            out.update({"width": self.w_spin.value(), "size": self.size_spin.value() / 100.0})
        return out


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📡 GoStream — Live Streaming Ringan | by jpXCode")
        self.setMinimumSize(1150, 720)

        self.config_path = os.path.join(os.path.dirname(__file__), "../../config/settings.json")
        self.settings = self.load_settings()

        self.engine = StreamEngine()
        self.region = None
        self._region_overlay = None
        self.is_capturing = False
        self.chat = None

        self.setup_ui()
        self.apply_theme(self.settings.get("theme", "1. Dracula"))
        self.restore_settings_ui()
        # auto-simpan key & server tiap berubah (tidak perlu ketik ulang)
        self.key_edit.textChanged.connect(self._save_key_setting)
        self.server_edit.textChanged.connect(self._save_server_setting)

        self.scanner = DeviceScanner(self.engine.ffmpeg)
        self.scanner.done.connect(self.on_devices_ready)
        self.scanner.start()

        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self.update_preview)
        self.preview_timer.setInterval(33)
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.setInterval(500)

        if self.engine.ffmpeg:
            self.log("✅ ffmpeg ditemukan — GoStream siap")
        else:
            self.log("⚠️ ffmpeg TIDAK ditemukan — siaran tidak bisa berjalan", "warn")

    # ==================================================================
    # Log (kecil - ke status + console)
    # ==================================================================
    def log(self, msg, level="info"):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        self.status_label.setText(msg)

    # ==================================================================
    # Settings
    # ==================================================================
    def load_settings(self):
        default = {
            "theme": "1. Dracula", "platform": "YouTube", "server": PLATFORMS["YouTube"],
            "key": "", "fps": 30, "bitrate": 2500, "resolution": "1280x720",
            "mic": None, "sys": None, "watermark": "",
            "chat_platform": "TikTok", "chat_room": "", "chat_overlay": False,
            "monitor": 1, "auto_hide": True,
            "ratio": "Landscape 16:9", "fit_mode": "fit",
            "scenes": [{"name": "Scene 1", "sources": []}], "active_scene": 0,
        }
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in default.items():
                    data.setdefault(k, v)
                return data
        except Exception:
            pass
        return default

    def save_settings(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _save_key_setting(self, text):
        self.settings["key"] = text
        self.save_settings()

    def _save_server_setting(self, text):
        self.settings["server"] = text
        self.save_settings()

    # ==================================================================
    # UI
    # ==================================================================
    def setup_ui(self):
        # Central: preview + stats
        self.preview = QLabel("📡 GoStream\n\nPilih sumber & isi stream key, lalu MULAI SIARAN")
        self.preview.setObjectName("preview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(520, 320)

        stats_bar = QHBoxLayout()
        self.fps_value = QLabel("0 FPS"); self.fps_value.setObjectName("stat_badge")
        self.size_value = QLabel("0x0"); self.size_value.setObjectName("stat_badge")
        self.bit_value = QLabel("0 kbps"); self.bit_value.setObjectName("stat_badge")
        self.drop_value = QLabel("0 dropped"); self.drop_value.setObjectName("stat_badge")
        self.timer_label = TimerLabel(); self.timer_label.setObjectName("timer_badge")
        for w in (self.fps_value, self.size_value, self.bit_value, self.drop_value):
            stats_bar.addWidget(w)
        stats_bar.addStretch()
        stats_bar.addWidget(self.timer_label)

        central = QWidget()
        v = QVBoxLayout(central)
        v.setContentsMargins(8, 8, 8, 8)
        v.addWidget(self.preview, 1)
        v.addLayout(stats_bar)
        self.setCentralWidget(central)

        # ---------- Dock kanan: Siaran / Sumber / Audio / Overlay ----------
        dock = QDockWidget("🎛️ Kontrol", self)
        dock.setObjectName("dock_control")
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_stream_tab(), "📡 Siaran")
        self.tabs.addTab(self._build_source_tab(), "📷 Sumber")
        self.tabs.addTab(self._build_audio_tab(), "🎤 Audio")
        self.tabs.addTab(self._build_overlay_tab(), "✨ Overlay")
        self.tabs.addTab(self._build_scene_tab(), "🎬 Scene")
        dock.setWidget(self.tabs)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

        # ---------- Dock bawah: Chat ----------
        chat_dock = QDockWidget("💬 Chat Live", self)
        chat_dock.setObjectName("dock_chat")
        cw = QWidget()
        cl = QVBoxLayout(cw)
        cl.setContentsMargins(6, 6, 6, 6)
        row = QHBoxLayout()
        row.addWidget(QLabel("Platform:"))
        self.chat_plat_combo = QComboBox()
        self.chat_plat_combo.addItems(["TikTok", "YouTube"])
        row.addWidget(self.chat_plat_combo)
        row.addWidget(QLabel("Room:"))
        self.chat_room_edit = QLineEdit()
        self.chat_room_edit.setPlaceholderText("TikTok: username · YouTube: video ID")
        row.addWidget(self.chat_room_edit, 1)
        self.btn_chat = QPushButton("🔌 Hubungkan")
        self.btn_chat.clicked.connect(self.toggle_chat)
        row.addWidget(self.btn_chat)
        self.chk_chat_overlay = QCheckBox("Tampilkan di preview")
        self.chk_chat_overlay.toggled.connect(self.on_chat_overlay)
        row.addWidget(self.chk_chat_overlay)
        cl.addLayout(row)
        self.chat_list = QListWidget()
        cl.addWidget(self.chat_list, 1)
        chat_dock.setWidget(cw)
        self.addDockWidget(Qt.BottomDockWidgetArea, chat_dock)

        # status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Siap")
        self.status_bar.addWidget(self.status_label)

    # ---------- Tab Siaran ----------
    def _build_stream_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        g = QGroupBox("🌐 Platform & Key")
        gl = QVBoxLayout()
        pr = QHBoxLayout()
        pr.addWidget(QLabel("Platform:"))
        self.plat_combo = QComboBox()
        self.plat_combo.addItems(list(PLATFORMS.keys()))
        self.plat_combo.currentTextChanged.connect(self.on_platform_changed)
        pr.addWidget(self.plat_combo, 1)
        gl.addLayout(pr)
        gl.addWidget(QLabel("Server (RTMP):"))
        self.server_edit = QLineEdit(self.settings.get("server", PLATFORMS["YouTube"]))
        gl.addWidget(self.server_edit)
        gl.addWidget(QLabel("Stream Key:"))
        key_row = QHBoxLayout()
        self.key_edit = QLineEdit(self.settings.get("key", ""))
        self.key_edit.setEchoMode(QLineEdit.Password)
        key_row.addWidget(self.key_edit, 1)
        btn_eye = QPushButton("👁")
        btn_eye.setMaximumWidth(36)
        btn_eye.setToolTip("Tampilkan/sembunyikan key")
        btn_eye.clicked.connect(self.toggle_key_visible)
        key_row.addWidget(btn_eye)
        gl.addLayout(key_row)
        g.setLayout(gl)
        lay.addWidget(g)

        q = QGroupBox("⚙️ Kualitas")
        ql = QVBoxLayout()
        rr = QHBoxLayout()
        rr.addWidget(QLabel("Rasio:"))
        self.ratio_combo = QComboBox()
        self.ratio_combo.addItems(list(self.RES_OPTIONS.keys()))
        self.ratio_combo.currentIndexChanged.connect(self.on_ratio_changed)
        rr.addWidget(self.ratio_combo, 1)
        ql.addLayout(rr)
        rr2 = QHBoxLayout()
        rr2.addWidget(QLabel("Resolusi:"))
        self.res_combo = QComboBox()
        rr2.addWidget(self.res_combo, 1)
        ql.addLayout(rr2)
        fitr = QHBoxLayout()
        fitr.addWidget(QLabel("Fit:"))
        self.fit_combo = QComboBox()
        self.fit_combo.addItems(["Fit (letterbox)", "Crop (isi layar)", "Stretch (distorsi)"])
        self.fit_combo.currentIndexChanged.connect(self.on_fit_changed)
        fitr.addWidget(self.fit_combo, 1)
        ql.addLayout(fitr)
        fr = QHBoxLayout()
        fr.addWidget(QLabel("FPS:"))
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["24", "30", "60"])
        self.fps_combo.setCurrentText(str(self.settings.get("fps", 30)))
        fr.addWidget(self.fps_combo)
        fr.addStretch()
        ql.addLayout(fr)
        br = QHBoxLayout()
        br.addWidget(QLabel("Bitrate:"))
        self.bitrate_slider = QSlider(Qt.Horizontal)
        self.bitrate_slider.setRange(500, 8000)
        self.bitrate_slider.setValue(int(self.settings.get("bitrate", 2500)))
        br.addWidget(self.bitrate_slider, 1)
        self.bitrate_label = QLabel(f"{self.bitrate_slider.value()} kbps")
        self.bitrate_slider.valueChanged.connect(
            lambda v: self.bitrate_label.setText(f"{v} kbps"))
        br.addWidget(self.bitrate_label)
        ql.addLayout(br)
        ql.addWidget(QLabel("💡 YouTube: 720p30 ≈ 2500 kbps · TikTok: 720p30 ≈ 3000 kbps"))
        q.setLayout(ql)
        lay.addWidget(q)

        self.btn_start = QPushButton("🔴 MULAI SIARAN")
        self.btn_start.setObjectName("btn_record")
        self.btn_start.setMinimumHeight(46)
        self.btn_start.clicked.connect(self.on_start_stop)
        lay.addWidget(self.btn_start)
        self.chk_autohide = QCheckBox("🕶 Sembunyikan window saat siaran")
        self.chk_autohide.setChecked(self.settings.get("auto_hide", True))
        lay.addWidget(self.chk_autohide)
        lay.addStretch()
        return w

    # ---------- Tab Sumber ----------
    def _build_source_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        g = QGroupBox("📷 Sumber")
        gl = QVBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Fullscreen", "Window", "Region", "Webcam"])
        self.mode_combo.currentTextChanged.connect(self.apply_source)
        gl.addWidget(self.mode_combo)

        mr = QHBoxLayout()
        mr.addWidget(QLabel("Monitor:"))
        self.monitor_combo = QComboBox()
        self.monitor_combo.currentIndexChanged.connect(self.apply_source)
        mr.addWidget(self.monitor_combo, 1)
        gl.addLayout(mr)

        wr = QHBoxLayout()
        wr.addWidget(QLabel("Jendela:"))
        self.win_combo = QComboBox()
        self.win_combo.currentIndexChanged.connect(self.apply_source)
        wr.addWidget(self.win_combo, 1)
        gl.addLayout(wr)
        self.chk_client = QCheckBox("Crop client area")
        self.chk_client.toggled.connect(self.apply_source)
        gl.addWidget(self.chk_client)

        cr = QHBoxLayout()
        cr.addWidget(QLabel("Kamera:"))
        self.cam_combo = QComboBox()
        self.cam_combo.currentIndexChanged.connect(self.apply_source)
        cr.addWidget(self.cam_combo, 1)
        gl.addLayout(cr)

        reg_row = QHBoxLayout()
        btn_region = QPushButton("📍 Pilih Area")
        btn_region.clicked.connect(self.pick_region)
        reg_row.addWidget(btn_region)
        self.region_label = QLabel("Belum dipilih")
        self.region_label.setObjectName("stat_badge")
        reg_row.addWidget(self.region_label, 1)
        gl.addLayout(reg_row)

        self.btn_capture = QPushButton("👁 Mulai Preview")
        self.btn_capture.clicked.connect(self.toggle_capture)
        gl.addWidget(self.btn_capture)
        g.setLayout(gl)
        lay.addWidget(g)
        lay.addStretch()
        return w

    # ---------- Tab Audio ----------
    def _build_audio_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        g = QGroupBox("🎤 Audio (DirectShow)")
        gl = QVBoxLayout()
        gl.addWidget(QLabel("Microphone:"))
        self.mic_combo = QComboBox()
        gl.addWidget(self.mic_combo)
        gl.addWidget(QLabel("System sound / loopback:"))
        self.sys_combo = QComboBox()
        gl.addWidget(self.sys_combo)
        g.setLayout(gl)
        lay.addWidget(g)
        lay.addWidget(QLabel(
            "ℹ️ System sound butuh perangkat loopback (Stereo Mix / Voicemeeter Out).\n"
            "Kalau kosong, siaran berjalan tanpa audio."))
        lay.addStretch()
        return w

    # ---------- Tab Overlay ----------
    def _build_overlay_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        g = QGroupBox("✨ Overlay")
        gl = QVBoxLayout()
        gl.addWidget(QLabel("Watermark (pojok kanan bawah):"))
        self.wm_edit = QLineEdit(self.settings.get("watermark", ""))
        self.wm_edit.setPlaceholderText("mis. @jpXCode · go.stream/anda")
        self.wm_edit.textChanged.connect(self.on_watermark)
        gl.addWidget(self.wm_edit)
        g.setLayout(gl)
        lay.addWidget(g)
        lay.addWidget(QLabel("Chat overlay diatur di panel Chat Live (tampilkan di preview)."))
        lay.addStretch()
        return w

    # ==================================================================
    # Handlers
    # ==================================================================
    def on_platform_changed(self, name):
        self.server_edit.setText(PLATFORMS.get(name, ""))
        self.settings["platform"] = name
        self.settings["server"] = self.server_edit.text()
        self.save_settings()
        if name == "TikTok":
            self.log("🎵 TikTok: salin Server URL & Stream Key dari "
                     "livecenter.tiktok.com/producer (URL berubah tiap sesi)")
        elif name in ("Facebook", "Instagram"):
            self.log("⚠️ " + name + ": bila gagal sambung, matikan dulu "
                     "Cloudflare WARP (RTMPS bisa terblokir)")

    def toggle_key_visible(self):
        self.key_edit.setEchoMode(QLineEdit.Normal if self.key_edit.echoMode() == QLineEdit.Password
                                  else QLineEdit.Password)

    def on_watermark(self, *a):
        self.engine.watermark_text = self.wm_edit.text()
        self.settings["watermark"] = self.engine.watermark_text
        self.save_settings()

    def on_chat_overlay(self, *a):
        self.engine.chat_overlay = self.chk_chat_overlay.isChecked()
        self.settings["chat_overlay"] = self.engine.chat_overlay
        self.save_settings()

    def pick_region(self):
        # simpan referensi di self supaya object tidak di-GC saat user memilih area
        self._region_overlay = RegionOverlay()
        self._region_overlay.region_selected.connect(self.on_region)
        self._region_overlay.showFullScreen()

    def on_region(self, x, y, w, h):
        self.region = (x, y, w, h)
        self.engine.region = (x, y, w, h)
        self.region_label.setText(f"Region: {w}x{h}")
        self.mode_combo.setCurrentText("Region")
        self._region_overlay = None   # overlay menutup sendiri; lepas referensi

    def apply_source(self, *a):
        mode = self.mode_combo.currentText()
        self.win_combo.setEnabled(mode == "Window")
        self.chk_client.setEnabled(mode == "Window")
        self.cam_combo.setEnabled(mode == "Webcam")
        self.engine.kind = {"Fullscreen": "full", "Window": "window",
                            "Region": "region", "Webcam": "webcam"}[mode]
        self.engine.monitor_index = self.monitor_combo.currentData() or 1
        self.engine.hwnd = self.win_combo.currentData()
        self.engine.client_area = self.chk_client.isChecked()
        self.engine.region = self.region if mode == "Region" else None
        self.engine.set_webcam(self.cam_combo.currentData() if mode == "Webcam" else None)

    def toggle_capture(self):
        if self.is_capturing:
            self.engine.stop_capture()
            self.is_capturing = False
            self.preview_timer.stop()
            self.stats_timer.stop()
            self.btn_capture.setText("👁 Mulai Preview")
            self.preview.setText("📡 Preview dihentikan")
        else:
            self.apply_source()
            self.engine.fps = int(self.fps_combo.currentText())
            self.engine.start_capture()
            self.is_capturing = True
            self.preview_timer.start()
            self.stats_timer.start()
            self.preview.setText("")
            self.btn_capture.setText("✋ Stop Preview")
            self.log("👁 Preview aktif")

    def on_start_stop(self):
        if self.engine.streaming:
            self.engine.stop_stream()
            self.btn_start.setText("🔴 MULAI SIARAN")
            self.timer_label.setSeconds(0)
            if self.isMinimized():
                self.showNormal()
            return
        if not self.is_capturing:
            self.toggle_capture()
        self.apply_source()
        rtmp = self.server_edit.text().strip().rstrip("/")
        key = self.key_edit.text().strip()
        if not rtmp or not key:
            QMessageBox.warning(self, "Stream Key",
                                "Isi Server RTMP & Stream Key dari platform Anda.")
            return
        url = f"{rtmp}/{key}" if not rtmp.endswith(key) else rtmp

        self.engine.fps = int(self.fps_combo.currentText())
        self.engine.bitrate_k = self.bitrate_slider.value()
        self.engine.crf = 24
        res = self.res_combo.currentText().split(" ")[0]
        rw, rh = map(int, res.split("x"))
        self.engine.output_size = (rw, rh)
        self.engine.fit_mode = ["fit", "crop", "stretch"][self.fit_combo.currentIndex()]
        self.engine.set_scene_sources(self._active_scene_sources())

        mic = self.mic_combo.currentData()
        sysd = self.sys_combo.currentData()
        ok = self.engine.start_stream(url, mic_name=mic, sys_name=sysd)
        if not ok:
            QMessageBox.critical(self, "Gagal", "Tidak bisa memulai ffmpeg.")
            return
        self.btn_start.setText("⏹ STOP SIARAN")
        self.settings["key"] = key
        self.settings["server"] = self.server_edit.text()
        self.save_settings()
        # sembunyikan window sendiri supaya tidak ikut terekam (GDI capture)
        if self.chk_autohide.isChecked():
            self.showMinimized()
            self.log("🕶 Window diminimalkan selama siaran — "
                     "pulihkan dari taskbar untuk STOP")

    # ==================================================================
    # Devices
    # ==================================================================
    def on_devices_ready(self, data):
        monitors = data.get("monitors") or []
        self.monitor_combo.blockSignals(True)
        self.monitor_combo.clear()
        if len(monitors) > 1:
            for i in range(1, len(monitors)):
                m = monitors[i]
                self.monitor_combo.addItem(f"Monitor {i} ({m['width']}x{m['height']})", i)
        else:
            self.monitor_combo.addItem("Monitor utama", 1)
        self.monitor_combo.setCurrentIndex(max(0, self.settings.get("monitor", 1) - 1))
        self.monitor_combo.blockSignals(False)

        wins = data.get("windows") or {}
        self.win_combo.blockSignals(True)
        self.win_combo.clear()
        if wins:
            items = sorted(
                ((hwnd, f"[{os.path.basename(w['exe'] or '?')}] {w['title']}")
                 for hwnd, w in wins.items()), key=lambda x: x[1].lower())
            for hwnd, text in items:
                self.win_combo.addItem(text, hwnd)
        else:
            self.win_combo.addItem("Tidak ada jendela", None)
        self.win_combo.blockSignals(False)

        cams = data.get("webcams") or []
        self.cam_combo.blockSignals(True)
        self.cam_combo.clear()
        for c in cams:
            self.cam_combo.addItem(c, c)
        if not cams:
            self.cam_combo.addItem("Tidak ada kamera", None)
        self.cam_combo.blockSignals(False)

        audio = data.get("audio") or []
        self.mic_combo.blockSignals(True)
        self.mic_combo.clear()
        self.mic_combo.addItem("— Tanpa mic —", None)
        for name in audio:
            self.mic_combo.addItem(f"🎤 {name}", name)
        self.mic_combo.blockSignals(False)
        self.sys_combo.blockSignals(True)
        self.sys_combo.clear()
        self.sys_combo.addItem("— Tanpa system —", None)
        for name in audio:
            self.sys_combo.addItem(f"🔊 {name}", name)
        self.sys_combo.blockSignals(False)
        # restore
        m = self.settings.get("mic")
        if m:
            idx = self.mic_combo.findData(m)
            if idx >= 0:
                self.mic_combo.setCurrentIndex(idx)
        s = self.settings.get("sys")
        if s:
            idx = self.sys_combo.findData(s)
            if idx >= 0:
                self.sys_combo.setCurrentIndex(idx)
        self.log(f"✅ Perangkat siap: {len(wins)} window, {len(cams)} kamera, {len(audio)} audio")

    # ==================================================================
    # Chat
    # ==================================================================
    def toggle_chat(self):
        if self.chat is not None and self.chat.isRunning():
            self.chat.stop()
            self.chat = None
            self.btn_chat.setText("🔌 Hubungkan")
            self.log("Chat diputus")
            return
        room = self.chat_room_edit.text().strip()
        if not room:
            QMessageBox.information(self, "Chat", "Isi room dulu.\n"
                                   "TikTok = username (tanpa @) · YouTube = ID video.")
            return
        plat = self.chat_plat_combo.currentText()
        self.settings["chat_platform"] = plat
        self.settings["chat_room"] = room
        self.save_settings()
        self.chat = ChatReader(plat, room)
        self.chat.message.connect(self.on_chat_message)
        self.chat.status.connect(self.log)
        self.chat.error.connect(lambda e: self.log(e, "warn"))
        self.chat.start()
        self.btn_chat.setText("⏹ Putus")
        self.log(f"⏳ Menghubungkan chat {plat}…")

    def on_chat_message(self, line):
        self.chat_list.addItem(line)
        self.chat_list.scrollToBottom()
        while self.chat_list.count() > 500:
            self.chat_list.takeItem(0)
        if self.engine.chat_overlay:
            self.engine.update_chat(line)

    # ==================================================================
    # Timers
    # ==================================================================
    def update_preview(self):
        if not self.is_capturing:
            return
        frame = self.engine.get_preview_frame()
        if frame is None:
            return
        h, w = frame.shape[:2]
        try:
            qimg = QImage(frame.data, w, h, 3 * w, QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(qimg).scaled(
                self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.preview.setPixmap(pix)
        except Exception:
            pass

    def update_stats(self):
        st = self.engine.stats()
        w, h = st["size"]
        self.fps_value.setText(f'{st["fps"]:.0f} FPS')
        self.size_value.setText(f"{w}x{h}")
        self.bit_value.setText(f"{st['bitrate']} kbps")
        self.drop_value.setText(f"{st['dropped']} dropped")
        self.timer_label.setSeconds(st["elapsed"])
        # sinkron tombol kalau ffmpeg mati sendiri (streaming=False tapi tombol masih STOP)
        if not st["streaming"] and self.btn_start.text().startswith("⏹"):
            self.btn_start.setText("🔴 MULAI SIARAN")
            self.timer_label.setSeconds(0)
            self.showNormal()
            self.log("⚠️ Siaran terputus — ffmpeg berhenti", "warn")

    # ==================================================================
    RES_OPTIONS = {
        "Landscape 16:9": ["1920x1080 (HD)", "1280x720 (SD)", "854x480 (480p)"],
        "Portrait 9:16": ["1080x1920 (HD)", "720x1280 (SD)", "540x960 (480p)"],
        "Square 1:1": ["1080x1080 (1:1)", "720x720 (1:1)"],
    }

    def _populate_res(self, ratio):
        self.res_combo.blockSignals(True)
        self.res_combo.clear()
        self.res_combo.addItems(self.RES_OPTIONS.get(ratio, self.RES_OPTIONS["Landscape 16:9"]))
        self.res_combo.setCurrentIndex(0)
        self.res_combo.blockSignals(False)

    def on_ratio_changed(self, idx):
        ratio = self.ratio_combo.currentText()
        self._populate_res(ratio)
        self.settings["ratio"] = ratio
        self.settings["resolution"] = self.res_combo.currentText().split(" ")[0]
        self.save_settings()

    def on_fit_changed(self, idx):
        self.engine.fit_mode = ["fit", "crop", "stretch"][max(0, min(idx, 2))]
        self.settings["fit_mode"] = self.engine.fit_mode
        self.save_settings()

    # ---------- Scene & Source ----------
    def _scenes(self):
        if not isinstance(self.settings.get("scenes"), list) or not self.settings["scenes"]:
            self.settings["scenes"] = [{"name": "Scene 1", "sources": []}]
        return self.settings["scenes"]

    def _active_scene(self):
        scenes = self._scenes()
        idx = min(int(self.settings.get("active_scene", 0)), len(scenes) - 1)
        return scenes[max(0, idx)]

    def _active_scene_sources(self):
        sc = self._active_scene()
        return list(sc.get("sources", []) or [])

    def _refresh_scene_list(self):
        self.scene_list.blockSignals(True)
        self.scene_list.clear()
        for sc in self._scenes():
            self.scene_list.addItem(sc.get("name", "Scene"))
        idx = min(int(self.settings.get("active_scene", 0)), self.scene_list.count() - 1)
        self.scene_list.setCurrentRow(max(0, idx))
        self.scene_list.blockSignals(False)
        self._refresh_source_list()

    def _refresh_source_list(self):
        self.src_list.blockSignals(True)
        self.src_list.clear()
        for s in self._active_scene_sources():
            self.src_list.addItem(self._src_label(s))
        self.src_list.blockSignals(False)

    def _src_label(self, s):
        t = s.get("type", "text")
        names = {"text": "📝 Teks", "image": "🖼️ Gambar", "box": "⬛ Kotak",
                 "webcam": "🎥 Webcam", "chat": "💬 Chat"}
        extra = s.get("text", "") if t == "text" else (s.get("path", "") if t == "image" else "")
        return f"{names.get(t, t)} — {extra}" if extra else names.get(t, t)

    def _apply_active_scene(self):
        self.engine.set_scene_sources(self._active_scene_sources())
        self.save_settings()

    def on_scene_selected(self, row):
        if row < 0:
            return
        self.settings["active_scene"] = row
        self._refresh_source_list()
        self._apply_active_scene()

    def add_scene(self):
        name, ok = QInputDialog.getText(self, "Scene Baru", "Nama scene:")
        if not ok or not name.strip():
            return
        self._scenes().append({"name": name.strip(), "sources": []})
        self.settings["active_scene"] = len(self._scenes()) - 1
        self._refresh_scene_list()
        self._apply_active_scene()

    def del_scene(self):
        row = self.scene_list.currentRow()
        scenes = self._scenes()
        if row < 0 or len(scenes) <= 1:
            self.log("⚠️ Minimal 1 scene", "warn")
            return
        scenes.pop(row)
        self.settings["active_scene"] = max(0, row - 1)
        self._refresh_scene_list()
        self._apply_active_scene()

    def add_source(self):
        dlg = SourceDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self._active_scene()["sources"].append(dlg.result_src())
            self._refresh_source_list()
            self._apply_active_scene()
            self.log("➕ Source ditambahkan")

    def edit_source(self):
        row = self.src_list.currentRow()
        sc = self._active_scene()
        if row < 0 or not sc:
            return
        dlg = SourceDialog(self, sc["sources"][row])
        if dlg.exec() == QDialog.Accepted:
            sc["sources"][row] = dlg.result_src()
            self._refresh_source_list()
            self._apply_active_scene()
            self.log("✏️ Source diedit")

    def del_source(self):
        row = self.src_list.currentRow()
        sc = self._active_scene()
        if row < 0 or not sc:
            return
        sc["sources"].pop(row)
        self._refresh_source_list()
        self._apply_active_scene()
        self.log("🗑️ Source dihapus")

    def _build_scene_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        g = QGroupBox("🎬 Scene")
        gl = QVBoxLayout()
        self.scene_list = QListWidget()
        self.scene_list.currentRowChanged.connect(self.on_scene_selected)
        gl.addWidget(self.scene_list, 1)
        brow = QHBoxLayout()
        b1 = QPushButton("➕ Scene"); b1.clicked.connect(self.add_scene)
        b2 = QPushButton("🗑️ Hapus"); b2.clicked.connect(self.del_scene)
        brow.addWidget(b1); brow.addWidget(b2)
        gl.addLayout(brow)
        g.setLayout(gl)
        lay.addWidget(g, 1)
        g2 = QGroupBox("🧩 Source")
        g2l = QVBoxLayout()
        self.src_list = QListWidget()
        self.src_list.itemDoubleClicked.connect(lambda _: self.edit_source())
        g2l.addWidget(self.src_list, 1)
        srow = QHBoxLayout()
        a = QPushButton("➕ Source"); a.clicked.connect(self.add_source)
        e = QPushButton("✏️ Edit"); e.clicked.connect(self.edit_source)
        d = QPushButton("🗑️ Hapus"); d.clicked.connect(self.del_source)
        srow.addWidget(a); srow.addWidget(e); srow.addWidget(d)
        g2l.addLayout(srow)
        g2.setLayout(g2l)
        lay.addWidget(g2, 1)
        lay.addWidget(QLabel("💡 Source tampil langsung di preview & siaran. Posisi dalam % layar."))
        lay.addWidget(QLabel("🎥 Source Webcam memakai kamera utama dari tab Sumber. Jika belum di-set, fallback ke monitor."))
        return w

    def restore_settings_ui(self):
        plat = self.settings.get("platform", "YouTube")
        if plat in PLATFORMS:
            self.plat_combo.setCurrentText(plat)
        self.server_edit.setText(self.settings.get("server", PLATFORMS["YouTube"]))
        self.key_edit.setText(self.settings.get("key", ""))
        self.bitrate_slider.setValue(int(self.settings.get("bitrate", 2500)))
        ratio = self.settings.get("ratio", "Landscape 16:9")
        ridx = self.ratio_combo.findText(ratio)
        self.ratio_combo.setCurrentIndex(max(0, ridx))
        self._populate_res(self.ratio_combo.currentText())
        res = self.settings.get("resolution", "1280x720")
        for i in range(self.res_combo.count()):
            if self.res_combo.itemText(i).startswith(res):
                self.res_combo.setCurrentIndex(i)
                break
        fit = self.settings.get("fit_mode", "fit")
        self.fit_combo.setCurrentIndex({"fit": 0, "crop": 1, "stretch": 2}.get(fit, 0))
        self.chat_plat_combo.setCurrentText(self.settings.get("chat_platform", "TikTok"))
        self.chat_room_edit.setText(self.settings.get("chat_room", ""))
        self.chk_chat_overlay.setChecked(self.settings.get("chat_overlay", False))
        self.wm_edit.setText(self.settings.get("watermark", ""))
        self._refresh_scene_list()
        self._apply_active_scene()

    def apply_theme(self, name):
        self.setStyleSheet(get_theme_style(name))

    def closeEvent(self, event):
        try:
            if self._region_overlay is not None:
                self._region_overlay.close()
        except Exception:
            pass
        try:
            if self.chat is not None and self.chat.isRunning():
                self.chat.stop()
        except Exception:
            pass
        try:
            self.engine.shutdown()
        except Exception:
            pass
        self.save_settings()
        super().closeEvent(event)
