# GoStream Studio 🎬

App stream desktop berbasis **Python + PySide6**: kontrol siaran langsung, tangkap layar, overlay chat, watermark, dan multi-scene — dengan tema modern.

## Fitur

- 🖥️ **Tangkap layar real-time** (mss) — streaming ke RTMP/RTMPS (Facebook, YouTube, TikTok, dll)
- 💬 **Overlay chat** — komentar TikTok / YouTube tampil live di atas siaran
- 🎨 **Watermark & multi-scene** dengan rasio/fit mode
- 🌙 **Theme manager** (Dracula & lainnya)
- 🎛️ Konfigurasi lengkap: fps, bitrate, resolusi, mic, monitor

## Menjalankan

```bash
pip install -r requirements.txt
python main.py
```

## Konfigurasi

Config disimpan di `config/settings.json` (gitignored — berisi stream key). Salin dari template untuk pertama kali:

```bash
cp config/settings.example.json config/settings.json
# lalu edit: platform, server, key, bitrate, dll
```

---

> 🔒 `config/` di-ignore — stream key & token tidak pernah masuk repo.
