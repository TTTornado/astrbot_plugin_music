from pathlib import Path
from typing import ClassVar
from urllib.parse import urlencode

from astrbot.api import logger

from ..model import Platform, Song
from .base import BaseMusicPlayer


class XunhuisiMusic(BaseMusicPlayer):
    """Search and resolve QQ Music tracks through the Xunhuisi API."""

    platform: ClassVar[Platform] = Platform(
        name="xunhuisi",
        display_name="巡回寺Q音",
    )
    supported_audio_qualities: ClassVar[tuple[str, ...]] = (
        "standard",
        "high",
        "lossless",
    )
    API_URL = "https://api.xunhuisi.store/API/QQMusic/Song.php"

    async def fetch_songs(
        self, keyword: str, limit: int, extra: str | None = None
    ) -> list[Song]:
        """Search QQ Music through the Xunhuisi API.

        Args:
            keyword: Song or artist search text.
            limit: Maximum number of results to return.
            extra: Unused platform-specific command context.

        Returns:
            Matching QQ Music tracks with stable song MIDs.
        """
        del extra
        keyword = keyword.strip()
        if not keyword or limit <= 0:
            return []

        limit = min(limit, 30)
        try:
            result = await self._request(
                f"{self.API_URL}?"
                + urlencode({"name": keyword, "list": limit, "type": "json"})
            )
        except Exception as exc:
            logger.warning(f"Xunhuisi QQ Music search failed: {exc}")
            return []

        items = result.get("data") if isinstance(result, dict) else None
        if (
            not isinstance(result, dict)
            or result.get("code") != 200
            or not isinstance(items, list)
        ):
            logger.warning("Xunhuisi QQ Music returned an invalid search response")
            return []

        songs = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            song_mid = str(item.get("mid") or "").strip()
            if not song_mid:
                continue
            songs.append(
                Song(
                    id=song_mid,
                    source=self.platform.name,
                    card_type="qq",
                    name=item.get("name"),
                    artists=item.get("singer"),
                    cover_url=item.get("cover"),
                    page_url=f"https://y.qq.com/n/ryqq/songDetail/{song_mid}",
                )
            )
        return songs

    async def fetch_extra(self, song: Song) -> Song:
        """Resolve a temporary playback URL and lyrics by QQ Music MID.

        Args:
            song: Song returned by the Xunhuisi search endpoint.

        Returns:
            The song populated with playback and presentation metadata.
        """
        if song.audio_url and song.lyrics:
            return song

        quality = self.platform_cfg.quality or "high"
        if quality not in self.supported_audio_qualities:
            logger.warning(
                f"Unsupported Xunhuisi QQ Music quality {quality!r}; using high"
            )
            quality = "high"
        try:
            result = await self._request(
                f"{self.API_URL}?"
                + urlencode({"id": song.id, "type": "json", "quality": quality})
            )
        except Exception as exc:
            logger.warning(f"Xunhuisi QQ Music resolution failed: {exc}")
            return song

        audio_url = result.get("music_url") if isinstance(result, dict) else None
        if (
            not isinstance(result, dict)
            or result.get("code") != 200
            or not isinstance(audio_url, str)
            or not audio_url.startswith(("http://", "https://"))
        ):
            logger.warning(
                f"Xunhuisi QQ Music could not resolve song {song.id}: "
                f"{result.get('msg') if isinstance(result, dict) else 'invalid response'}"
            )
            return song

        song.audio_url = audio_url
        song.name = result.get("title") or song.name
        song.artists = result.get("singer") or song.artists
        song.cover_url = result.get("cover") or song.cover_url
        song.page_url = result.get("link") or song.page_url
        song.lyrics = result.get("lyric") or song.lyrics
        song.quality = result.get("quality") or song.quality
        return song

    async def download_audio(
        self, song: Song, quality: str | None = None
    ) -> Path | None:
        """Download the requested Xunhuisi QQ Music audio quality.

        Args:
            song: Song whose audio should be downloaded.
            quality: One of standard, high, or lossless.

        Returns:
            Path to the downloaded audio file, or None if resolution fails.
        """
        requested_quality = quality or self.platform_cfg.quality or "high"
        if requested_quality not in self.supported_audio_qualities:
            logger.warning(
                "Unsupported Xunhuisi QQ Music quality "
                f"{requested_quality!r}; using high"
            )
            requested_quality = "high"

        configured_quality = self.platform_cfg.quality or "high"
        if not song.audio_url or requested_quality != configured_quality:
            try:
                result = await self._request(
                    f"{self.API_URL}?"
                    + urlencode(
                        {
                            "id": song.id,
                            "type": "json",
                            "quality": requested_quality,
                        }
                    )
                )
            except Exception as exc:
                logger.warning(f"Xunhuisi QQ Music resolution failed: {exc}")
                return None
            audio_url = result.get("music_url") if isinstance(result, dict) else None
            if (
                not isinstance(result, dict)
                or result.get("code") != 200
                or not isinstance(audio_url, str)
                or not audio_url.startswith(("http://", "https://"))
            ):
                logger.warning(
                    f"Xunhuisi QQ Music could not resolve song {song.id} "
                    f"at {requested_quality} quality"
                )
                return None
            song.audio_url = audio_url
            song.quality = result.get("quality") or song.quality

        file_path = await super().download_audio(song, requested_quality)
        if (
            file_path
            and requested_quality == "lossless"
            and "flac" in (song.quality or "").casefold()
            and file_path.suffix != ".flac"
        ):
            flac_path = file_path.with_suffix(".flac")
            file_path.replace(flac_path)
            return flac_path
        return file_path

    async def fetch_comments(self, song: Song) -> Song:
        """Return the song because this API does not expose comments.

        Args:
            song: Xunhuisi QQ Music song.

        Returns:
            The unchanged song.
        """
        return song

    async def fetch_lyrics(self, song: Song) -> Song:
        """Resolve lyrics together with the playback metadata.

        Args:
            song: Xunhuisi QQ Music song.

        Returns:
            The song with lyrics when the API provides them.
        """
        if song.lyrics:
            return song
        return await self.fetch_extra(song)
