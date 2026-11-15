from typing import ClassVar

from astrbot.api import logger

from ..config import PluginConfig
from ..model import Platform, Song
from .base import BaseMusicPlayer


class TXQQMusic(BaseMusicPlayer):
    """Search and resolve tracks through the TXQQ music aggregator."""

    platform: ClassVar[Platform] = Platform(
        name="txqq",
        display_name="TXQQ",
    )
    BASE_URL = "https://music.txqq.pro/"
    SUPPORTED_SUB_SOURCES: ClassVar[frozenset[str]] = frozenset(
        {
            "netease",
            "qq",
            "kugou",
            "kuwo",
            "baidu",
            "1ting",
            "migu",
            "lizhi",
            "qingting",
            "ximalaya",
            "5singyc",
            "5singfc",
            "kg",
        }
    )
    CARD_TYPES: ClassVar[dict[str, str]] = {
        "qq": "qq",
        "netease": "163",
        "kugou": "kugou",
        "kuwo": "kuwo",
        "migu": "migu",
    }
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:146.0) "
            "Gecko/20100101 Firefox/146.0"
        ),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://music.txqq.pro",
        "Referer": "https://music.txqq.pro/",
    }

    def __init__(self, config: PluginConfig):
        super().__init__(config)
        configured_source = (self.platform_cfg.default_sub_source or "qq").strip()
        if configured_source not in self.SUPPORTED_SUB_SOURCES:
            logger.warning(
                f"Unsupported TXQQ default sub-source {configured_source!r}; using qq"
            )
            configured_source = "qq"
        self.search_platform = configured_source

    async def fetch_songs(
        self,
        keyword: str,
        limit: int = 5,
        extra: str | None = None,
    ) -> list[Song]:
        """Fetch playable tracks from a TXQQ sub-source.

        A URL is resolved automatically. Prefix a platform song ID with ``id:``
        to use TXQQ's ID lookup; ``kg`` input is treated as an ID by default.

        Args:
            keyword: Song search text, source URL, or an ``id:``-prefixed song ID.
            limit: Maximum number of playable results to return.
            extra: TXQQ sub-source identifier supplied by the trigger route.

        Returns:
            Normalized playable songs returned by TXQQ.
        """
        query = keyword.strip()
        if not query or limit <= 0:
            return []

        platform_type = (extra or self.search_platform).strip().lower()
        filter_type = "name"
        if query.startswith(("http://", "https://")):
            filter_type = "url"
            platform_type = "_"
        elif query.casefold().startswith("id:"):
            filter_type = "id"
            query = query[3:].strip()
        elif platform_type == "kg":
            filter_type = "id"

        if not query:
            return []
        if filter_type != "url" and platform_type not in self.SUPPORTED_SUB_SOURCES:
            logger.warning(f"Unsupported TXQQ sub-source: {platform_type!r}")
            return []

        songs: list[Song] = []
        seen: set[tuple[str, str]] = set()
        page = 1
        max_pages = 1 if filter_type != "name" else max(1, (limit + 9) // 10 + 1)
        while page <= max_pages and len(songs) < limit:
            try:
                result = await self._request(
                    url=self.BASE_URL,
                    method="POST",
                    data={
                        "input": query,
                        "filter": filter_type,
                        "type": platform_type,
                        "page": page,
                    },
                    headers=self.HEADERS,
                )
            except Exception as exc:
                logger.warning(f"TXQQ request failed: {exc}")
                break

            if not isinstance(result, dict):
                logger.warning("TXQQ returned a non-JSON response")
                break
            if result.get("code") != 200:
                error = result.get("error") or f"business code {result.get('code')}"
                if page == 1 and result.get("code") != 404:
                    logger.warning(f"TXQQ {filter_type} request failed: {error}")
                else:
                    logger.debug(f"TXQQ returned no more results: {error}")
                break

            data = result.get("data")
            if not isinstance(data, list) or not data:
                if data not in (None, "", []):
                    logger.warning("TXQQ returned an invalid data payload")
                break

            added = 0
            for item in data:
                if not isinstance(item, dict):
                    continue
                song_id = str(item.get("songid") or "").strip()
                source = str(item.get("type") or platform_type).strip().lower()
                audio_url = item.get("url")
                if not song_id or not isinstance(audio_url, str) or not audio_url:
                    continue
                identity = (source, song_id)
                if identity in seen:
                    continue
                seen.add(identity)
                songs.append(
                    Song(
                        id=song_id,
                        source=source,
                        card_type=self.CARD_TYPES.get(source),
                        name=item.get("title"),
                        artists=item.get("author"),
                        page_url=item.get("link"),
                        audio_url=audio_url,
                        cover_url=item.get("pic"),
                        lyrics=item.get("lrc") or "",
                    )
                )
                added += 1
                if len(songs) >= limit:
                    break

            if filter_type != "name" or added == 0:
                break
            page += 1

        return songs

    async def fetch_extra(self, song: Song) -> Song:
        """Resolve a fresh temporary audio URL by the source song ID.

        Args:
            song: TXQQ song whose playback metadata may be missing or expired.

        Returns:
            The song updated with freshly resolved TXQQ metadata when available.
        """
        if song.audio_url or not song.id:
            return song

        source = (song.source or self.search_platform).strip().lower()
        resolved = await self.fetch_songs(f"id:{song.id}", limit=1, extra=source)
        if not resolved:
            return song

        match = resolved[0]
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
        """Return the song because TXQQ does not expose normalized comments.

        Args:
            song: TXQQ song returned by search.

        Returns:
            The unchanged song.
        """
        return song

    async def fetch_lyrics(self, song: Song) -> Song:
        """Return the song because TXQQ search already includes lyrics.

        Args:
            song: TXQQ song returned by search.

        Returns:
            The unchanged song.
        """
        return song
