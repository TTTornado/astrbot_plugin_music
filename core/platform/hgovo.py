import hashlib
from typing import ClassVar
from urllib.parse import urlencode

from astrbot.api import logger

from ..config import PluginConfig
from ..model import Platform, Song
from .base import BaseMusicPlayer


class HgovoMusic(BaseMusicPlayer):
    """Search and resolve tracks through the Hgovo music aggregator."""

    platform: ClassVar[Platform] = Platform(
        name="hgovo",
        display_name="盒盖API",
    )
    API_URL = "https://api.hgovo.cn/API/hgdydg"
    SUPPORTED_SUB_SOURCES: ClassVar[frozenset[str]] = frozenset(
        {"qs", "kw", "zxl", "bd", "wy_vip", "qq", "wy_member"}
    )
    CARD_TYPES: ClassVar[dict[str, str]] = {
        "qs": "qq",
        "kw": "kuwo",
        "zxl": "qq",
        "bd": "qq",
        "wy_vip": "163",
        "qq": "qq",
        "wy_member": "163",
    }

    def __init__(self, config: PluginConfig):
        """Configure the Hgovo adapter and its default sub-source.

        Args:
            config: Shared music plugin configuration.
        """
        super().__init__(config)
        configured_source = (self.platform_cfg.default_sub_source or "qq").strip()
        if configured_source not in self.SUPPORTED_SUB_SOURCES:
            logger.warning(
                f"Unsupported Hgovo default sub-source {configured_source!r}; using qq"
            )
            configured_source = "qq"
        self.search_platform = configured_source

    async def fetch_songs(
        self,
        keyword: str,
        limit: int = 5,
        extra: str | None = None,
    ) -> list[Song]:
        """Fetch the single playable track returned by an Hgovo sub-source.

        Args:
            keyword: Song or artist search text.
            limit: Maximum number of results. Hgovo currently returns at most one.
            extra: Hgovo sub-source identifier supplied by the trigger route.

        Returns:
            A normalized playable track, or an empty list when lookup fails.
        """
        query = keyword.strip()
        if not query or limit <= 0:
            return []

        source = (extra or self.search_platform).strip().lower()
        if source not in self.SUPPORTED_SUB_SOURCES:
            logger.warning(f"Unsupported Hgovo sub-source: {source!r}")
            return []

        try:
            result = await self._request(
                f"{self.API_URL}?{urlencode({'type': source, 'msg': query})}"
            )
        except Exception as exc:
            logger.warning(f"Hgovo request failed: {exc}")
            return []

        if not isinstance(result, dict):
            logger.warning("Hgovo returned a non-JSON response")
            return []
        if str(result.get("code")) != "200":
            error = result.get("msg") or f"business code {result.get('code')}"
            logger.warning(f"Hgovo search failed: {error}")
            return []

        title = result.get("title")
        artist = result.get("singer")
        audio_url = result.get("music_url")
        if (
            not isinstance(title, str)
            or not title.strip()
            or not isinstance(audio_url, str)
            or not audio_url.startswith(("http://", "https://"))
        ):
            logger.warning("Hgovo returned an invalid track payload")
            return []

        title = title.strip()
        artist = artist.strip() if isinstance(artist, str) else ""
        identity = f"{source}\0{title}\0{artist}"
        song_id = hashlib.sha256(identity.encode()).hexdigest()[:24]
        cover_url = result.get("cover")
        page_url = result.get("link")
        return [
            Song(
                id=song_id,
                source=source,
                card_type=self.CARD_TYPES[source],
                name=title,
                artists=artist or None,
                cover_url=(
                    cover_url
                    if isinstance(cover_url, str)
                    and cover_url.startswith(("http://", "https://"))
                    else None
                ),
                page_url=(
                    page_url
                    if isinstance(page_url, str)
                    and page_url.startswith(("http://", "https://"))
                    else None
                ),
                audio_url=audio_url,
                lyrics=result.get("lyric")
                if isinstance(result.get("lyric"), str)
                else None,
            )
        ]

    async def fetch_extra(self, song: Song) -> Song:
        """Refresh playback metadata for a stored Hgovo track.

        Args:
            song: Hgovo track whose temporary media URL may be absent.

        Returns:
            The track populated with fresh metadata when the same result is found.
        """
        if song.audio_url or not song.name:
            return song

        query = " ".join(value for value in (song.name, song.artists) if value)
        source = (song.source or self.search_platform).strip().lower()
        matches = await self.fetch_songs(query, limit=1, extra=source)
        if not matches or matches[0].id != song.id:
            return song

        match = matches[0]
        song.source = match.source
        song.card_type = match.card_type
        song.name = match.name or song.name
        song.artists = match.artists or song.artists
        song.cover_url = match.cover_url or song.cover_url
        song.page_url = match.page_url or song.page_url
        song.audio_url = match.audio_url
        song.lyrics = match.lyrics or song.lyrics
        return song

    async def fetch_comments(self, song: Song) -> Song:
        """Return the track because Hgovo does not expose comments.

        Args:
            song: Hgovo track returned by search.

        Returns:
            The unchanged track.
        """
        return song

    async def fetch_lyrics(self, song: Song) -> Song:
        """Return lyrics included with the track or refresh stored metadata.

        Args:
            song: Hgovo track returned by search or loaded from storage.

        Returns:
            The track with lyrics when Hgovo provides them.
        """
        if song.lyrics:
            return song
        return await self.fetch_extra(song)
