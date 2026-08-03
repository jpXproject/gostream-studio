# src/chat_reader.py
# GoStream - pembaca chat live real-time (websocket)
# TikTok  : TikTokLive (protokol websocket internal TikTok, tanpa API key)
# YouTube : pytchat (protokol internal YouTube, tanpa API key)
# Facebook/Instagram: belum tersedia jalur publik yang stabil -> ditandai.
# Semua fail-open: kalau library/platform berubah, tidak menggagalkan app.

import time
from PySide6.QtCore import QThread, Signal


class ChatReader(QThread):
    message = Signal(str)          # baris chat mentah "User: teks"
    status = Signal(str)           # info koneksi
    error = Signal(str)

    def __init__(self, platform, room_id, parent=None):
        super().__init__(parent)
        self.platform = platform   # "TikTok", "YouTube"
        self.room_id = room_id     # username TikTok / video_id YouTube
        self._stop = False

    def stop(self):
        self._stop = True
        try:
            if hasattr(self, "_client") and self._client:
                self._client.stop()
        except Exception:
            pass
        self.wait(3000)

    def run(self):
        try:
            if self.platform == "TikTok":
                self._run_tiktok()
            elif self.platform == "YouTube":
                self._run_youtube()
        except Exception as e:
            self.error.emit(f"Chat gagal: {e}")

    # ------------------------------------------------------------------
    def _run_tiktok(self):
        try:
            from TikTokLive import TikTokLiveClient
            from TikTokLive.types.events import CommentEvent, GiftEvent, ConnectEvent
        except Exception as e:
            self.error.emit(f"TikTokLive tidak terpasang: {e}")
            return
        client = TikTokLiveClient(unique_id=self.room_id)
        self._client = client

        @client.on("connect")
        async def _on_connect(event: ConnectEvent):
            self.status.emit(f"✅ Terhubung ke chat TikTok @{self.room_id}")

        @client.on("comment")
        async def _on_comment(event: CommentEvent):
            user = getattr(event.user, "unique_id", "?")
            text = getattr(event, "comment", "")
            self.message.emit(f"💬 {user}: {text}")

        @client.on("gift")
        async def _on_gift(event: GiftEvent):
            user = getattr(event.user, "unique_id", "?")
            gift = getattr(event.gift, "info", None)
            name = getattr(gift, "name", "hadiah") if gift else "hadiah"
            count = getattr(event, "repeat_count", 1) or 1
            self.message.emit(f"🎁 {user}: kirim {name} x{count}")

        self.status.emit(f"⏳ Menghubungkan chat TikTok @{self.room_id}…")
        try:
            client.run()
        except Exception as e:
            if not self._stop:
                self.error.emit(f"TikTok chat: {e}")

    # ------------------------------------------------------------------
    def _run_youtube(self):
        try:
            import pytchat
        except Exception as e:
            self.error.emit(f"pytchat tidak terpasang: {e}")
            return
        self.status.emit(f"⏳ Membaca chat YouTube (video {self.room_id})…")
        try:
            chat = pytchat.create(video_id=self.room_id)
            if not chat.is_alive():
                self.error.emit("YouTube chat: video tidak live / ID salah.")
                return
            self.status.emit("✅ Terhubung ke chat YouTube")
            while not self._stop and chat.is_alive():
                for c in chat.get().sync_items():
                    author = getattr(c, "author", {}).get("name", "?") \
                        if isinstance(getattr(c, "author", None), dict) else getattr(c, "author", "?")
                    text = getattr(c, "message", "")
                    self.message.emit(f"💬 {author}: {text}")
                time.sleep(1)
        except Exception as e:
            if not self._stop:
                self.error.emit(f"YouTube chat: {e}")
