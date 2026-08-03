# src/stream_engine.py
# GoStream - engine live streaming ringan (Python + ffmpeg RTMP)
# Developed by jpXCode
#
# Pipeline:
#   capture (mss, di thread) -> overlay (watermark, chat ticker) -> rawvideo pipe
#   -> ffmpeg libx264 + aac -> RTMP/FLV ke platform (YouTube/Facebook/TikTok/IG)
#   audio ditangkap langsung oleh ffmpeg via DirectShow (nama device)

import os, sys, time, threading, subprocess, queue
from collections import deque

if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
import mss
import win32gui, win32con, win32process
import cv2
import psutil

os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREATE_NO_WINDOW = 0x08000000

# Preset ingest URL per platform (server RTMP)
PLATFORMS = {
    "YouTube": "rtmp://a.rtmp.youtube.com/live2",
    "Facebook": "rtmps://live-api-s.facebook.com:443/rtmp/",
    # TikTok: Server URL dinamis per-sesi dari livecenter.tiktok.com/producer
    # (domain statis livepush.tiktok.com sudah tidak dipakai lagi)
    "TikTok": "",
    "Instagram": "rtmp://live-upload.instagram.com:443/rtmp/",
}

SKIP_CLASSES = {
    "Progman", "WorkerW", "Shell_TrayWnd", "SysListView32",
    "Windows.UI.Core.CoreWindow", "Button", "ToolbarWindow32",
    "DV2ControlHost", "ForegroundStaging", "XamlExplorerHostIslandWindow",
}


def find_ffmpeg():
    candidates = [os.path.join(BASE_DIR, "bin", "ffmpeg.exe")]
    for p in os.environ.get("PATH", "").split(os.pathsep):
        if p:
            candidates.append(os.path.join(p, "ffmpeg.exe"))
    seen = set()
    for c in candidates:
        c = os.path.abspath(c)
        if c in seen or not os.path.exists(c):
            continue
        seen.add(c)
        try:
            r = subprocess.run([c, "-version"], capture_output=True, timeout=8)
            if r.returncode == 0 and b"ffmpeg version" in (r.stdout or b"")[:200]:
                return c
        except Exception:
            continue
    return None


def list_monitors():
    try:
        with mss.mss() as sct:
            return list(sct.monitors)
    except Exception:
        return []


def list_windows():
    out = {}
    own_pid = os.getpid()
    def cb(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return True
            cls = win32gui.GetClassName(hwnd)
            if cls in SKIP_CLASSES:
                return True
            ex = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if ex & win32con.WS_EX_TOOLWINDOW:
                return True
            if win32gui.GetWindow(hwnd, win32con.GW_OWNER):
                return True
            pid = win32process.GetWindowThreadProcessId(hwnd)[1]
            if pid == own_pid:
                return True
            try:
                exe = psutil.Process(pid).exe()
            except Exception:
                exe = None
            # anti self-capture: jangan tampilkan window GoStream sendiri
            if "gostream" in (title + " " + (exe or "")).lower():
                return True
            out[hwnd] = {"title": title, "exe": exe}
        except Exception:
            pass
        return True
    try:
        win32gui.EnumWindows(cb, None)
    except Exception:
        pass
    return out


def list_webcams(ffmpeg_path):
    devices = []
    if ffmpeg_path:
        try:
            r = subprocess.run(
                [ffmpeg_path, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                capture_output=True, text=True, timeout=25, creationflags=CREATE_NO_WINDOW)
            out = (r.stderr or "") + (r.stdout or "")
            for line in out.splitlines():
                if "(video)" in line and '"' in line:
                    name = line.split('"')[1]
                    if name not in devices:
                        devices.append(name)
        except Exception:
            pass
    if not devices:
        for i in range(5):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                devices.append(f"Camera {i}")
                cap.release()
    return devices


def list_dshow_audio(ffmpeg_path):
    """Nama device audio DirectShow (input/mic & loopback)."""
    inputs = []
    if ffmpeg_path:
        try:
            r = subprocess.run(
                [ffmpeg_path, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                capture_output=True, text=True, timeout=25, creationflags=CREATE_NO_WINDOW)
            out = (r.stderr or "") + (r.stdout or "")
            for line in out.splitlines():
                # baris device: [in#0 ...] "Nama Device" (audio)
                if "(audio)" in line and '"' in line:
                    name = line.split('"')[1]
                    if name not in inputs:
                        inputs.append(name)
        except Exception:
            pass
    return inputs


class StreamEngine:
    def __init__(self):
        self.ffmpeg = find_ffmpeg()
        self.sct = mss.mss()
        self._thread_sct = None
        self.monitors = list_monitors()
        self.monitor_index = 1

        # source
        self.kind = "full"           # full, window, region, webcam
        self.hwnd = None
        self.client_area = False
        self.region = None
        self.webcam_name = None

        # overlay
        self.watermark_text = ""
        self.chat_overlay = False
        self.chat_lines = deque(maxlen=3)

        # kualitas
        self.fps = 30
        self.bitrate_k = 2500
        self.crf = 24
        self.output_size = None   # (w, h) resolusi siaran, None = asli
        self.fit_mode = "fit"     # stretch | fit (letterbox) | crop (isi layar)
        self.scene_sources = []   # daftar source scene aktif (dict)
        self._img_cache = {}      # cache gambar overlay (path,size -> array)

        self._webcam_cap = None
        self._preview_frame = None
        self._stop_event = threading.Event()
        self._preview_thread = None
        self._pipe = None
        self._pipe_lock = threading.Lock()
        self._ffmpeg_errf = None
        self._frame_q = queue.Queue(maxsize=8)   # bounded: buang frame lama saat penuh
        self._writer_thread = None

        self.streaming = False
        self.started_at = 0.0
        self.frames = 0
        self.dropped = 0
        self._fps_actual = 0.0
        self._bytes = 0
        self._rtmp_url = ""
        self.log_callback = None

    # ------------------------------------------------------------------
    def _log(self, msg):
        try:
            if self.log_callback:
                self.log_callback(msg)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Webcam
    # ------------------------------------------------------------------
    def set_webcam(self, name):
        if self._webcam_cap is not None:
            try:
                self._webcam_cap.release()
            except Exception:
                pass
            self._webcam_cap = None
        if not name:
            return
        try:
            cap = cv2.VideoCapture(name, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(name)
            if cap.isOpened():
                self._webcam_cap = cap
        except Exception:
            self._webcam_cap = None

    def _read_webcam(self):
        if self._webcam_cap is None:
            return None
        try:
            ret, f = self._webcam_cap.read()
            if ret:
                return f
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------
    def start_capture(self):
        if self._preview_thread and self._preview_thread.is_alive():
            return
        self._stop_event.clear()
        self._preview_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._preview_thread.start()
        if self._writer_thread is None or not self._writer_thread.is_alive():
            self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
            self._writer_thread.start()

    def stop_capture(self):
        self._stop_event.set()
        if self._preview_thread:
            self._preview_thread.join(timeout=5)
            self._preview_thread = None
        if self._writer_thread:
            self._writer_thread.join(timeout=5)
            self._writer_thread = None
        if self._thread_sct is not None:
            try:
                self._thread_sct.close()
            except Exception:
                pass
            self._thread_sct = None
        self._close_webcam()

    def _capture_loop(self):
        self._thread_sct = mss.mss()
        target_iv = 1.0 / self.fps
        prev = time.time()
        while not self._stop_event.is_set():
            t0 = time.time()
            frame = self._grab_frame()
            if frame is None:
                time.sleep(0.005)
                continue
            self._apply_overlays(frame)
            self._preview_frame = frame

            now = time.time()
            iv = now - prev
            prev = now
            self._fps_actual = 1.0 / iv if iv > 0 else 0.0

            if self.streaming:
                # kirim ke writer thread via bounded queue (capture tak pernah blokir)
                if self._frame_q.full():
                    try:
                        self._frame_q.get_nowait()
                        self._frame_q.task_done()
                        self.dropped += 1
                    except queue.Empty:
                        pass
                try:
                    self._frame_q.put_nowait(frame.tobytes())
                except queue.Full:
                    self.dropped += 1

            dt = time.time() - t0
            wait = target_iv - dt
            if wait > 0:
                time.sleep(wait)

    def _writer_loop(self):
        """Tulis frame dari queue ke pipe ffmpeg di thread terpisah.
        Capture thread tidak pernah terblokir oleh pipe — penting karena
        dshow audio bisa butuh 5-10 detik untuk buka device. Queue bounded:
        frame lama dibuang (benar untuk live streaming)."""
        while not self._stop_event.is_set():
            try:
                data = self._frame_q.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                pipe = self._pipe
                if pipe is not None and pipe.stdin and not pipe.stdin.closed:
                    with self._pipe_lock:
                        pipe.stdin.write(data)
                    self.frames += 1
                    self._bytes += len(data)
                else:
                    self.dropped += 1
            except Exception:
                self.dropped += 1
                try:
                    if pipe is not None and pipe.poll() is not None:
                        self._log("⚠️ ffmpeg berhenti — siaran terputus")
                        self.streaming = False
                except Exception:
                    pass
            finally:
                try:
                    self._frame_q.task_done()
                except Exception:
                    pass

    def get_preview_frame(self):
        f = self._preview_frame
        if f is None:
            return None
        try:
            return f.copy()
        except Exception:
            return None

    def _grab_monitor(self, idx):
        try:
            sct = self._thread_sct or self.sct
            if idx >= len(sct.monitors):
                idx = 1
            shot = sct.grab(sct.monitors[idx])
            return np.ascontiguousarray(np.array(shot)[:, :, :3])
        except Exception:
            return None

    def _grab_window(self):
        if not self.hwnd:
            return self._grab_monitor(self.monitor_index)
        try:
            if self.client_area:
                rect = win32gui.GetClientRect(self.hwnd)
                left, top = win32gui.ClientToScreen(self.hwnd, (0, 0))
                w, h = rect[2], rect[3]
            else:
                left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
                w, h = right - left, bottom - top
            if w <= 0 or h <= 0:
                return None
            sct = self._thread_sct or self.sct
            shot = sct.grab({"left": left, "top": top, "width": w, "height": h, "mon": 0})
            return np.ascontiguousarray(np.array(shot)[:, :, :3])
        except Exception:
            return None

    def _grab_frame(self):
        try:
            if self.kind == "window":
                return self._grab_window()
            if self.kind == "region" and self.region:
                x, y, w, h = self.region
                sct = self._thread_sct or self.sct
                shot = sct.grab({"left": x, "top": y, "width": w, "height": h, "mon": 0})
                return np.ascontiguousarray(np.array(shot)[:, :, :3])
            if self.kind == "webcam":
                f = self._read_webcam()
                if f is not None:
                    return np.ascontiguousarray(f)
                return self._grab_monitor(self.monitor_index)
            return self._grab_monitor(self.monitor_index)
        except Exception:
            return self._grab_monitor(self.monitor_index)

    # ------------------------------------------------------------------
    # Overlay
    # ------------------------------------------------------------------
    def _apply_overlays(self, frame):
        # legacy (tab Overlay): watermark & chat ticker
        if self.watermark_text:
            self._draw_watermark(frame)
        if self.chat_overlay and self.chat_lines:
            self._draw_chat(frame)
        # scene sources (tab Scene): teks, gambar, kotak, webcam, chat
        for src in list(self.scene_sources or []):
            try:
                self._draw_scene_source(frame, src)
            except Exception:
                pass

    def set_scene_sources(self, sources):
        """Terapkan daftar source scene aktif ke engine (live)."""
        self.scene_sources = list(sources or [])
        self._img_cache = {}   # ganti referensi (atomic) — aman dari race thread capture

    def _draw_scene_source(self, frame, src):
        t = src.get("type", "text")
        if t == "text":
            self._draw_src_text(frame, src)
        elif t == "image":
            self._draw_src_image(frame, src)
        elif t == "box":
            self._draw_src_box(frame, src)
        elif t == "webcam":
            self._draw_src_webcam(frame, src)
        elif t == "chat":
            self._draw_src_chat(frame, src)

    def _draw_src_box(self, frame, src):
        h, w = frame.shape[:2]
        x = int(src.get("x", 0) * w / 100)
        y = int(src.get("y", 0) * h / 100)
        bw = max(1, int(src.get("w", 50) * w / 100))
        bh = max(1, int(src.get("h", 20) * h / 100))
        color = tuple(src.get("color", [40, 40, 40]))
        opacity = float(src.get("opacity", 0.55))
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(w, x + bw), min(h, y + bh)
        if x2 <= x1 or y2 <= y1:
            return
        overlay = frame.copy()
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
        cv2.addWeighted(overlay, opacity, frame, 1 - opacity, 0, frame)

    def _draw_src_text(self, frame, src):
        h, w = frame.shape[:2]
        text = str(src.get("text", ""))
        if not text:
            return
        scale = max(0.4, min(2.0, float(src.get("size", 1.0)) * (w / 1400.0)))
        color = tuple(src.get("color", [255, 255, 255]))
        thick = int(src.get("thickness", 2))
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
        x = int(src.get("x", 0) * w / 100)
        y = min(h - 8, max(th + 8, int(src.get("y", 0) * h / 100)))
        if src.get("box"):
            overlay = frame.copy()
            cv2.rectangle(overlay, (max(0, x - 8), max(0, y - th - 10)),
                          (min(w, x + tw + 8), min(h, y + 10)), (15, 15, 15), -1)
            cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
        cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color,
                    thick, cv2.LINE_AA)

    def _draw_src_image(self, frame, src):
        path = src.get("path", "")
        if not path or not os.path.exists(path):
            return
        h, w = frame.shape[:2]
        key = (path, int(src.get("width", 20)), int(src.get("height", 20)))
        img = self._img_cache.get(key, None)
        if img is None:
            img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if img is None:
                self._img_cache[key] = False
                return
            dw = max(1, int(src.get("width", 20) * w / 100))
            dh = max(1, int(src.get("height", 20) * h / 100))
            img = cv2.resize(img, (dw, dh), interpolation=cv2.INTER_AREA)
            self._img_cache[key] = img
        if img is False:
            return
        x = int(src.get("x", 0) * w / 100)
        y = int(src.get("y", 0) * h / 100)
        opacity = float(src.get("opacity", 1.0))
        ih, iw = img.shape[:2]
        if img.shape[2] == 4:
            bgr = img[:, :, :3]
            alpha = (img[:, :, 3].astype(np.float32) / 255.0) * opacity
        else:
            bgr = img
            alpha = np.full((ih, iw), opacity, np.float32)
        roi = frame[max(0, y):y + ih, max(0, x):x + iw]
        if roi.shape[0] == ih and roi.shape[1] == iw:
            a = alpha[..., None]
            frame[max(0, y):y + ih, max(0, x):x + iw] = (
                (roi.astype(np.float32) * (1 - a) + bgr.astype(np.float32) * a)
            ).astype(np.uint8)

    def _draw_src_webcam(self, frame, src):
        cam = self._read_webcam()
        if cam is None:
            return
        h, w = frame.shape[:2]
        dw = max(1, int(src.get("width", 25) * w / 100))
        dh = max(1, int(src.get("height", 25) * h / 100))
        cam = cv2.resize(cam, (dw, dh), interpolation=cv2.INTER_AREA)
        x = int(src.get("x", 70) * w / 100)
        y = int(src.get("y", 70) * h / 100)
        ih, iw = cam.shape[:2]
        roi = frame[max(0, y):y + ih, max(0, x):x + iw]
        if roi.shape[0] == ih and roi.shape[1] == iw:
            frame[max(0, y):y + ih, max(0, x):x + iw] = cam

    def _draw_src_chat(self, frame, src):
        if not self.chat_lines:
            return
        h, w = frame.shape[:2]
        x = int(src.get("x", 2) * w / 100)
        y = int(src.get("y", 0) * h / 100)
        bw = int(src.get("width", 96) * w / 100)
        lines = list(self.chat_lines)[-3:]
        scale = max(0.4, float(src.get("size", 0.6)) * (w / 1400.0))
        bh = min(h, int(len(lines) * 26) + 12)
        overlay = frame.copy()
        cv2.rectangle(overlay, (x, y), (min(w, x + bw), min(h, y + bh)), (12, 12, 18), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
        ty = y + 22
        for line in lines:
            cv2.putText(frame, str(line)[:70], (x + 10, ty),
                        cv2.FONT_HERSHEY_SIMPLEX, scale, (140, 220, 255), 1, cv2.LINE_AA)
            ty += 26

    def _draw_watermark(self, frame):
        try:
            h, w = frame.shape[:2]
            scale = max(0.6, min(1.2, w / 1400))
            (tw, th), _ = cv2.getTextSize(self.watermark_text, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
            x, y = w - tw - 14, h - 12
            overlay = frame.copy()
            cv2.rectangle(overlay, (x - 8, y - th - 10), (x + tw + 8, y + 10), (20, 20, 20), -1)
            cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)
            cv2.putText(frame, self.watermark_text, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                        scale, (255, 255, 255), 2, cv2.LINE_AA)
        except Exception:
            pass

    def _draw_chat(self, frame):
        try:
            h, w = frame.shape[:2]
            bar_h = min(140, int(h * 0.16))
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, h - bar_h), (w, h), (12, 12, 18), -1)
            cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
            y = h - bar_h + 22
            for line in list(self.chat_lines):
                cv2.putText(frame, line[:90], (14, y), cv2.FONT_HERSHEY_SIMPLEX,
                            0.62, (140, 220, 255), 1, cv2.LINE_AA)
                y += 26
        except Exception:
            pass

    def update_chat(self, line):
        self.chat_lines.append(line)

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------
    @property
    def current_size(self):
        f = self._preview_frame
        if f is None:
            return (1280, 720)
        return (f.shape[1], f.shape[0])

    @property
    def elapsed(self):
        return (time.time() - self.started_at) if self.streaming else 0.0

    @property
    def bitrate_kbps(self):
        # bitrate ter-encode tidak bisa diukur dari sisi raw pipe;
        # tampilkan target yang dikonfigurasi pengguna (jujur & berguna)
        return self.bitrate_k if self.streaming else 0

    def start_stream(self, rtmp_url, mic_name=None, sys_name=None):
        if self.streaming or not self.ffmpeg:
            return False
        # fps efektif = kemampuan capture aktual (durasi stream tetap nyata).
        # Disimpan di variabel LOKAL supaya self.fps (target user) tidak berubah.
        stream_fps = self.fps
        if self._fps_actual > 1:
            stream_fps = max(5, min(self.fps, int(round(self._fps_actual))))
        w, h = self.current_size
        gop = stream_fps * 2
        cmd = [
            self.ffmpeg, "-y", "-hide_banner", "-loglevel", "warning",
            # timestamp video ikut wallclock supaya sinkron dgn audio dshow
            # (tanpa ini frame video bisa dibuang muxer FLV saat dshow lambat buka)
            "-use_wallclock_as_timestamps", "1",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(stream_fps),
            "-i", "pipe:0",
        ]
        # audio: 0, 1, atau 2 input dshow (mic & system) digabung via amix
        audio_inputs = []
        if mic_name:
            audio_inputs.append(mic_name)
        if sys_name and sys_name not in audio_inputs:
            audio_inputs.append(sys_name)
        if len(audio_inputs) == 1:
            cmd += ["-f", "dshow", "-i", f"audio={audio_inputs[0]}"]
        elif len(audio_inputs) == 2:
            cmd += ["-f", "dshow", "-i", f"audio={audio_inputs[0]}",
                    "-f", "dshow", "-i", f"audio={audio_inputs[1]}"]
        # filter graph: scale video (jika output_size) + amix audio (jika 2 input)
        filter_parts = []
        maps = []
        if self.output_size:
            w2, h2 = self.output_size
            fit = getattr(self, "fit_mode", "fit")
            if fit == "stretch":
                vf = f"[0:v]scale={w2}:{h2}[v]"
            elif fit == "crop":
                vf = (f"[0:v]scale={w2}:{h2}:force_original_aspect_ratio=increase,"
                      f"crop={w2}:{h2}[v]")
            else:  # fit (letterbox)
                vf = (f"[0:v]scale={w2}:{h2}:force_original_aspect_ratio=decrease,"
                      f"pad={w2}:{h2}:(ow-iw)/2:(oh-ih)/2:color=black[v]")
            filter_parts.append(vf)
            maps += ["-map", "[v]"]
        else:
            maps += ["-map", "0:v"]
        if len(audio_inputs) == 2:
            filter_parts.append(
                "[1:a][2:a]amix=inputs=2:duration=longest:dropout_transition=2[a]")
            maps += ["-map", "[a]"]
        elif len(audio_inputs) == 1:
            maps += ["-map", "1:a"]
        if filter_parts:
            cmd += ["-filter_complex", ";".join(filter_parts)]
        cmd += maps
        if len(audio_inputs) == 0:
            cmd += ["-an"]
        else:
            # encoder audio eksplisit (AAC 128k stereo) utk FLV
            cmd += ["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]
        cmd += [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(self.crf),
            "-maxrate", f"{self.bitrate_k}k", "-bufsize", f"{self.bitrate_k * 2}k",
            "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0",
            "-pix_fmt", "yuv420p",
            "-f", "flv", rtmp_url,
        ]
        self._log("▶️ ffmpeg: " + " ".join(cmd[:14]) + " ...")
        # pastikan writer thread hidup (aman walau dipanggil tanpa start_capture)
        if self._writer_thread is None or not self._writer_thread.is_alive():
            self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
            self._writer_thread.start()
        # stderr ffmpeg ke file log utk diagnosis (tidak dibuang)
        self._ffmpeg_log = os.path.join(os.path.expanduser("~"), ".gostream", "ffmpeg.log")
        try:
            os.makedirs(os.path.dirname(self._ffmpeg_log), exist_ok=True)
        except Exception:
            pass
        try:
            errf = open(self._ffmpeg_log, "ab")
            self._ffmpeg_errf = errf
            self._pipe = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=errf, creationflags=CREATE_NO_WINDOW)
        except Exception as e:
            self._log(f"❌ Gagal mulai ffmpeg: {e}")
            self._pipe = None
            try:
                if self._ffmpeg_errf is not None:
                    self._ffmpeg_errf.close()
                    self._ffmpeg_errf = None
            except Exception:
                pass
            return False
        self.streaming = True
        self.started_at = time.time()
        self.frames = 0
        self.dropped = 0
        self._bytes = 0
        self._rtmp_url = rtmp_url
        self._log(f"🔴 Siaran dimulai → {rtmp_url}")
        return True

    def stop_stream(self):
        if not self.streaming:
            return
        self.streaming = False
        pipe = self._pipe
        self._pipe = None
        if pipe is not None:
            try:
                if pipe.stdin and not pipe.stdin.closed:
                    # tutup tanpa lock: writer thread mungkin sedang blokir menulis
                    try:
                        pipe.stdin.close()  # EOF bersih utk rawvideo
                    except Exception:
                        pass
                try:
                    pipe.wait(timeout=5)
                except Exception:
                    pipe.terminate()
                    try:
                        pipe.wait(timeout=3)
                    except Exception:
                        pipe.kill()
            except Exception:
                try:
                    pipe.kill()
                except Exception:
                    pass
        try:
            self._frame_q.queue.clear()
        except Exception:
            pass
        try:
            if self._ffmpeg_errf is not None:
                self._ffmpeg_errf.close()
                self._ffmpeg_errf = None
        except Exception:
            pass
        self._log("⏹ Siaran dihentikan")

    def capture_still(self):
        f = self.get_preview_frame()
        if f is None:
            f = self._grab_frame()
        if f is None:
            return None
        self._apply_overlays(f)
        return f

    def stats(self):
        return {
            "fps": self._fps_actual,
            "target_fps": self.fps,
            "frames": self.frames,
            "dropped": self.dropped,
            "elapsed": self.elapsed,
            "bitrate": self.bitrate_kbps,
            "streaming": self.streaming,
            "size": self.current_size,
        }

    def shutdown(self):
        try:
            self.stop_stream()
        except Exception:
            pass
        try:
            self.stop_capture()
        except Exception:
            pass
        try:
            self.sct.close()
        except Exception:
            pass
