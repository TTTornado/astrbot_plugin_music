import { bridge, songKey } from "./api.js";

export function createFullPlayer({
  elements,
  player,
  t,
  formatTime,
  renderCover,
  setButtonIcon,
  onShowQueue,
  onToggleFavorite,
}) {
  let lyrics = { key: "", lines: [], current: -1 };
  const lyricRequests = new Set();
  const itemSong = (item) => item?.song || item;

  const parseLyrics = (value) => {
    if (typeof value !== "string" || !value.trim()) return [];
    const lines = [];
    const plainLines = [];
    for (const raw of value.split(/\r?\n/)) {
      const tags = [...raw.matchAll(/\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]/g)];
      const text = raw.replace(/\[[^\]]+\]/g, "").trim();
      if (!tags.length && text) plainLines.push(text);
      for (const tag of tags) {
        const fraction = Number(tag[3] || 0);
        lines.push({
          time: Number(tag[1]) * 60 + Number(tag[2]) + (tag[3]?.length === 3 ? fraction / 1000 : fraction / 100),
          text: text || "♪",
        });
      }
    }
    if (!lines.length) {
      return plainLines.map((text, index) => ({
        time: index ? Number.POSITIVE_INFINITY : 0,
        text,
      }));
    }
    return lines.sort((left, right) => left.time - right.time);
  };

  const renderLyrics = (song, current = 0) => {
    const key = song ? songKey(song) : "";
    if (key !== lyrics.key) {
      lyrics = { key, lines: parseLyrics(song?.lyrics), current: -1 };
      elements.lyrics.replaceChildren();
      if (!lyrics.lines.length) {
        const empty = document.createElement("div");
        empty.className = "full-player-lyrics-empty";
        empty.textContent = song ? t("lyricsLoading") : t("noSongs");
        elements.lyrics.append(empty);
        return;
      }
      lyrics.lines.forEach((line, index) => {
        const element = document.createElement("button");
        element.type = "button";
        element.className = "lyric-line";
        element.textContent = line.text;
        element.addEventListener("click", () => player.seek(line.time));
        element.dataset.index = String(index);
        elements.lyrics.append(element);
      });
    }
    let active = -1;
    lyrics.lines.forEach((line, index) => {
      if (line.time <= current) active = index;
    });
    if (active === lyrics.current) return;
    lyrics.current = active;
    const lines = elements.lyrics.querySelectorAll(".lyric-line");
    lines.forEach((line, index) => {
      line.classList.toggle("active", index === active);
      if (index === active) line.scrollIntoView?.({ block: "center", behavior: "smooth" });
    });
  };

  const loadLyrics = async (item) => {
    const song = itemSong(item);
    if (!song || song.lyrics || lyricRequests.has(songKey(song))) return;
    const key = songKey(song);
    lyricRequests.add(key);
    try {
      const result = await bridge.apiPost("lyrics", {
        query: song.name || "",
        artist: song.artists || "",
        platform: song.player || "",
      });
      if (result?.lyrics && player.current && songKey(itemSong(player.current)) === key) {
        song.lyrics = result.lyrics;
        lyrics.key = "";
        renderLyrics(song, player.audio.currentTime || 0);
      }
      if (!result?.lyrics && player.current && songKey(itemSong(player.current)) === key) {
        const fallback = await bridge.apiPost("lyrics", {
          query: song.name || "",
          artist: song.artists || "",
          platform: "",
        });
        if (fallback?.lyrics && player.current && songKey(itemSong(player.current)) === key) {
          song.lyrics = fallback.lyrics;
          lyrics.key = "";
          renderLyrics(song, player.audio.currentTime || 0);
        } else {
          const empty = elements.lyrics.querySelector(".full-player-lyrics-empty");
          if (empty) empty.textContent = t("lyricsMissing");
        }
      }
    } catch {
      // Lyrics are optional; keep the player usable when the source is unavailable.
    } finally {
      lyricRequests.delete(key);
    }
  };

  const setOpen = (open) => {
    elements.root.hidden = !open;
    document.body.classList.toggle("full-player-open", open);
    if (open) {
      renderLyrics(itemSong(player.current), player.audio.currentTime || 0);
      loadLyrics(player.current);
      elements.close.focus();
    } else {
      elements.trigger.focus();
    }
  };

  const update = (item) => {
    const song = itemSong(item);
    renderCover(elements.cover, song);
    elements.title.textContent = song?.name || "Music";
    elements.artist.textContent = song?.artists || "";
    elements.favorite.classList.toggle("active", Boolean(song?.is_favorite));
    elements.favorite.disabled = !item;
    setButtonIcon(elements.favorite, "heart", song?.is_favorite ? t("unfavorite") : t("favorite"));
    setButtonIcon(elements.toggle, player.audio.paused ? "play" : "pause", player.audio.paused ? t("play") : t("pause"));
    setButtonIcon(elements.mode, player.mode, t(player.mode));
    renderLyrics(song, player.audio.currentTime || 0);
    if (!elements.root.hidden) loadLyrics(item);
  };

  const updateTime = (current, duration) => {
    elements.elapsed.textContent = formatTime(current);
    elements.total.textContent = formatTime(duration);
    elements.progress.value = String(duration ? Math.round((current / duration) * 1000) : 0);
    renderLyrics(itemSong(player.current), current);
  };

  const bindEvents = () => {
    elements.trigger.addEventListener("click", () => setOpen(true));
    elements.close.addEventListener("click", () => setOpen(false));
    elements.queue.addEventListener("click", () => {
      setOpen(false);
      onShowQueue();
    });
    elements.toggle.addEventListener("click", () => player.toggle());
    elements.previous.addEventListener("click", () => player.previous());
    elements.next.addEventListener("click", () => player.next(true));
    elements.mode.addEventListener("click", () => player.cycleMode());
    elements.favorite.addEventListener("click", () => player.current && onToggleFavorite(player.current));
    elements.progress.addEventListener("input", () => player.seek(Number(elements.progress.value) / 1000));
  };

  return { bindEvents, setOpen, update, updateTime };
}
