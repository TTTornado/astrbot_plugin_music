import asyncio
import io
import json
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from PIL import Image

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
if str(PLUGIN_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT.parent))

PACKAGE_NAME = PLUGIN_ROOT.name
if PACKAGE_NAME not in sys.modules:
    pkg = types.ModuleType(PACKAGE_NAME)
    pkg.__path__ = [str(PLUGIN_ROOT)]
    sys.modules[PACKAGE_NAME] = pkg

from astrbot_plugin_music.core.ark_card import ArkCard  # noqa: E402
from astrbot_plugin_music.core.lyrics_renderer import (  # noqa: E402
    LyricsRenderer,
    LyricsTheme,
)
from astrbot_plugin_music.core.model import Platform, Song  # noqa: E402
from astrbot_plugin_music.core.music_service import MusicService  # noqa: E402
from astrbot_plugin_music.core.platform import BaseMusicPlayer  # noqa: E402
from astrbot_plugin_music.core.platform.qqmusic.qqmusic import QQMusic  # noqa: E402
from astrbot_plugin_music.core.sender import (  # noqa: E402
    _MAX_SELECTION_ENTRIES,
    _SELECTION_TTL_SECONDS,
    MusicSender,
)
from astrbot_plugin_music.core.song_renderer import (  # noqa: E402
    CardRenderer,
    CardTheme,
)


def _make_config(temp_dir: Path, db_path: Path | None = None) -> SimpleNamespace:
    font_path = PLUGIN_ROOT / "fonts" / "simhei.ttf"
    qq_cfg = SimpleNamespace(
        enable=True,
        priority=1,
        trigger_words=["QQ点歌"],
        uin="10001",
        cookies="",
        proxy="",
        quality="standard",
    )
    netease_cfg = SimpleNamespace(
        enable=True,
        priority=2,
        trigger_words=["网易点歌"],
        cookies="",
        proxy="",
        enc_sec_key="",
        enc_params="",
    )
    players = SimpleNamespace(
        qqmusic=qq_cfg,
        netease=netease_cfg,
        enabled_platforms=lambda: ["qqmusic", "netease"],
        platforms=lambda: ["qqmusic", "netease"],
    )
    return SimpleNamespace(
        font_path=font_path,
        temp_dir=temp_dir,
        db_path=db_path or (temp_dir / "music.db"),
        search_config=SimpleNamespace(
            song_limit=5,
            select_modes=["image"],
            cards_per_row=3,
            timeout=10,
            recall_select=False,
        ),
        send_config=SimpleNamespace(
            send_modes=["native_card", "text"],
            onebot_direct_audio=True,
            ark_key="",
            record_unsupported=[],
            file_unsupported=[],
            enable_comments=False,
            enable_lyrics=False,
            return_play_song_result=True,
        ),
        real_select_modes=["image"],
        real_send_modes=["native_card", "text"],
        players=players,
    )


class _DummyResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        body: bytes = b"",
        headers: dict[str, str] | None = None,
        url: str = "https://example.com/final",
    ):
        self.status = status
        self._body = body
        self.headers = headers or {}
        self.url = url
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            return self._body
        return self._body[:n]

    async def text(self) -> str:
        return self._body.decode("utf-8", "ignore")

    async def json(self, content_type=None):
        return json.loads(self._body.decode("utf-8"))

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    async def iter_chunked(self, chunk_size: int):
        for offset in range(0, len(self._body), chunk_size):
            yield self._body[offset : offset + chunk_size]


class TestFontAndRenderers(unittest.TestCase):
    def test_lyrics_renderer_lazy_font_and_gradient(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_config(Path(tmp))
            with patch(
                "astrbot_plugin_music.core.lyrics_renderer.LyricsTheme.load_font",
                wraps=LyricsTheme().load_font,
            ) as spy_load:
                renderer = LyricsRenderer(cfg)
                self.assertEqual(spy_load.call_count, 0)
                self.assertFalse(hasattr(renderer, "font"))

                jpeg = renderer.draw_lyrics("[00:12.34]晴天\n[00:15.00]周杰伦\n")
                self.assertEqual(spy_load.call_count, 1)

                img = Image.open(io.BytesIO(jpeg))
                self.assertEqual(img.format, "JPEG")
                self.assertGreaterEqual(img.width, LyricsTheme.image_width)
                self.assertGreater(img.height, 100)
                top_px = img.getpixel((0, 0))
                self.assertGreater(top_px[0], 240)
                self.assertGreater(top_px[1], 240)

                empty_jpeg = renderer.draw_lyrics("")
                self.assertEqual(Image.open(io.BytesIO(empty_jpeg)).format, "JPEG")

    def test_card_renderer_lazy_font_single_load_and_clean_title(self):
        self.assertEqual(
            CardRenderer._clean_title("<b>晴天</b> &amp; 周杰伦 (A < B)"),
            "晴天 & 周杰伦 (A < B)",
        )
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_config(Path(tmp))
            with patch(
                "astrbot_plugin_music.core.song_renderer.CardTheme.load_font",
                wraps=CardTheme().load_font,
            ) as spy_load:
                renderer = CardRenderer(cfg)
                self.assertEqual(spy_load.call_count, 0)
                self.assertFalse(hasattr(renderer, "font"))

                songs = [
                    Song(
                        id=str(i),
                        name=f"<b>Song {i}</b> &amp; Test",
                        artists=f"Artist {i}",
                        duration=185000,
                        cover_url=f"https://example.com/{i}.jpg",
                    )
                    for i in range(5)
                ]
                cover = Image.new("RGB", (220, 220), (120, 150, 180))
                cover_map = {s.cover_url: cover for s in songs}
                jpeg = asyncio.run(renderer.render_song_list_image(songs, cover_map))

                self.assertEqual(spy_load.call_count, 1)
                img = Image.open(io.BytesIO(jpeg))
                self.assertEqual(img.format, "JPEG")
                expected_w = 3 * CardTheme.card_width + 4 * CardTheme.margin
                expected_h = 2 * (CardTheme.card_height + 2 * CardTheme.margin)
                self.assertEqual(img.size, (expected_w, expected_h))


class TestServiceSenderAndNetworking(unittest.IsolatedAsyncioTestCase):
    async def test_shared_http_session_and_stale_temp_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin_temp = root / "astrbot_plugin_music"
            plugin_temp.mkdir()
            other_file = root / "other_plugin.tmp"
            other_file.write_bytes(b"keep")
            stale_file = plugin_temp / "stale.mp3"
            stale_file.write_bytes(b"old")
            fresh_file = plugin_temp / "fresh.mp3"
            fresh_file.write_bytes(b"new")
            stale_mtime = time.time() - 7200
            os.utime(stale_file, (stale_mtime, stale_mtime))
            os.utime(other_file, (stale_mtime, stale_mtime))

            cfg = _make_config(plugin_temp, db_path=root / "music.db")
            service = MusicService(cfg)
            await service.initialize()

            self.assertFalse(stale_file.exists())
            self.assertTrue(fresh_file.exists())
            self.assertTrue(other_file.exists())
            self.assertIsNone(service._http_session)

            # All players and ArkCard share one lazy session with DummyCookieJar
            sender = MusicSender(
                cfg,
                SimpleNamespace(platform_manager=SimpleNamespace(get_insts=lambda: [])),
                LyricsRenderer(cfg),
                CardRenderer(cfg),
                service,
            )
            shared_session = service.players[0]._get_session()
            self.assertIs(service.players[1]._get_session(), shared_session)
            self.assertIs(sender.ark_card._get_session(), shared_session)
            self.assertIsInstance(shared_session.cookie_jar, aiohttp.DummyCookieJar)

            await sender.close()
            self.assertFalse(shared_session.closed)
            await service.close()
            self.assertTrue(shared_session.closed)

    async def test_search_songs_times_out_hung_source_and_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_config(Path(tmp), db_path=Path(tmp) / "music.db")
            cfg.search_config.timeout = 1
            service = MusicService(cfg)

            class _SlowPlayer:
                platform = Platform(name="slow", display_name="Slow")
                platform_cfg = SimpleNamespace(priority=1)

                async def fetch_songs(self, keyword, limit, extra=None):
                    await asyncio.sleep(5)
                    return []

                async def close(self):
                    pass

            class _FastPlayer:
                platform = Platform(name="fast", display_name="Fast")
                platform_cfg = SimpleNamespace(priority=2)

                async def fetch_songs(self, keyword, limit, extra=None):
                    return [Song(id="1", name="晴天", artists="周杰伦")]

                async def close(self):
                    pass

            service.players = [_SlowPlayer(), _FastPlayer()]
            result = await service.search_songs("晴天", fallback=True)
            self.assertIsNotNone(result.player)
            self.assertEqual(result.player.platform.name, "fast")
            self.assertEqual(result.attempted_sources, ["Slow", "Fast"])

    async def test_selection_image_skips_fetch_extra_when_cover_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_config(Path(tmp))
            sender = MusicSender(
                cfg,
                SimpleNamespace(platform_manager=SimpleNamespace(get_insts=lambda: [])),
                LyricsRenderer(cfg),
                CardRenderer(cfg),
                MagicMock(),
            )

            cover_buf = io.BytesIO()
            Image.new("RGB", (500, 500), (10, 20, 30)).save(cover_buf, format="PNG")
            cover_bytes = cover_buf.getvalue()
            fetched_ids = []

            class _FakePlayer:
                platform = SimpleNamespace(name="fake", display_name="Fake")

                async def fetch_extra(self, song: Song) -> Song:
                    fetched_ids.append(song.id)
                    song.cover_url = f"https://example.com/cover_{song.id}.png"
                    return song

                async def download_cover(self, url: str) -> bytes:
                    return cover_bytes

            songs = [
                Song(
                    id="1",
                    name="HasCover",
                    artists="A",
                    cover_url="https://example.com/1.png",
                ),
                Song(id="2", name="MissingCover", artists="B", cover_url=None),
            ]
            event = SimpleNamespace(
                unified_msg_origin="group:1",
                get_sender_id=lambda: "u1",
                send=AsyncMock(),
            )
            await sender._send_song_selection_image(event, songs, _FakePlayer())
            self.assertEqual(fetched_ids, ["2"])
            event.send.assert_awaited_once()
            await sender.close()

    async def test_selection_context_ttl_and_cap_pruning(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_config(Path(tmp))
            sender = MusicSender(
                cfg,
                SimpleNamespace(platform_manager=SimpleNamespace(get_insts=lambda: [])),
                LyricsRenderer(cfg),
                CardRenderer(cfg),
                MagicMock(),
            )
            now = time.monotonic()
            sender._selection_contexts["expired"] = {
                "created_at": now - _SELECTION_TTL_SECONDS - 5,
                "handled": False,
            }
            sender._selection_context_ids["g:old"] = "expired"
            for i in range(_MAX_SELECTION_ENTRIES + 10):
                sender._selection_contexts[f"ctx-{i}"] = {
                    "created_at": now,
                    "handled": False,
                }
                sender._selection_context_ids[f"g:{i}"] = f"ctx-{i}"

            sender._prune_selection_state(now)
            self.assertNotIn("expired", sender._selection_contexts)
            self.assertNotIn("g:old", sender._selection_context_ids)
            self.assertLessEqual(len(sender._selection_contexts), _MAX_SELECTION_ENTRIES)
            await sender.close()

    async def test_qqmusic_reuses_aiohttp_and_shared_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _make_config(Path(tmp))
            player = QQMusic(cfg)
            session = player._get_session()
            self.assertEqual(session.timeout.total, 30)
            self.assertIsInstance(session.cookie_jar, aiohttp.DummyCookieJar)

            fake_session = MagicMock()
            fake_session.closed = False
            fake_session.get = MagicMock(
                side_effect=[
                    _DummyResponse(
                        body=json.dumps(
                            {
                                "hot_comment": {
                                    "commentlist": [
                                        {
                                            "rootcommentcontent": "好听",
                                            "nick": "user",
                                            "praisenum": 12,
                                        }
                                    ]
                                }
                            }
                        ).encode("utf-8")
                    ),
                    _DummyResponse(
                        status=206,
                        body=b"ID3\x03\x00" + b"\x00" * 27,
                        headers={"Content-Type": "audio/mpeg"},
                    ),
                    _DummyResponse(body=b"audio-bytes-here"),
                ]
            )
            fake_session.close = AsyncMock()
            player.session = fake_session
            player._owns_session = False

            song = Song(id="123", note="001mid", audio_url="https://example.com/a.mp3")
            await player.fetch_comments(song)
            self.assertEqual(song.comments[0]["content"], "好听")

            self.assertTrue(await player._probe_audio_url("https://example.com/a.mp3"))
            downloaded = await player.download_audio(song, quality="standard")
            self.assertIsNotNone(downloaded)
            self.assertEqual(downloaded.read_bytes(), b"audio-bytes-here")
            await session.close()

    async def test_review_fixes_timeout_and_cancellation(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp) / "music_tmp"
            cfg = _make_config(temp_dir)
            cfg.search_config.timeout = 7

            # 1. cleanup_stale_temp_files handles OSError gracefully
            with patch.object(Path, "iterdir", side_effect=PermissionError("denied")):
                temp_dir.mkdir(exist_ok=True)
                self.assertEqual(BaseMusicPlayer.cleanup_stale_temp_files(temp_dir), 0)

            # 2. _download_to_temp removes partial file on CancelledError
            player = QQMusic(cfg)

            class _CancelStreamResponse(_DummyResponse):
                async def iter_chunked(self, chunk_size: int):
                    yield b"partial"
                    raise asyncio.CancelledError()

            cancel_session = MagicMock()
            cancel_session.closed = False
            cancel_session.get = MagicMock(return_value=_CancelStreamResponse())
            player.session = cancel_session
            with self.assertRaises(asyncio.CancelledError):
                await player._download_to_temp("https://example.com/cancel.mp3")
            self.assertEqual(list(temp_dir.iterdir()), [])

            # 3. ArkCard passes explicit timeout even with shared session_factory
            shared_session = MagicMock()
            shared_session.get = MagicMock(
                side_effect=[
                    _DummyResponse(url="https://example.com/cover.jpg"),
                    _DummyResponse(
                        body=json.dumps(
                            {
                                "code": 200,
                                "data": {
                                    "app": "a",
                                    "meta": {},
                                    "prompt": "p",
                                    "view": "v",
                                },
                            }
                        ).encode("utf-8")
                    ),
                ]
            )
            ark = ArkCard(cfg, session_factory=lambda: shared_session)
            ark_song = Song(
                id="1",
                card_type="qq",
                name="S",
                artists="A",
                audio_url="https://example.com/a.mp3",
                cover_url="https://example.com/c.jpg",
            )
            fake_player = SimpleNamespace(platform_cfg=SimpleNamespace(proxy=""))
            res = await ark.fetch(fake_player, ark_song)
            self.assertIsNotNone(res)
            for call in shared_session.get.call_args_list:
                self.assertEqual(call.kwargs["timeout"].total, 7)


if __name__ == "__main__":
    unittest.main()
