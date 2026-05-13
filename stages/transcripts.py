import json
import os
import urllib.request

from http_utils import SSL_CONTEXT
import yt_dlp
from yt_dlp.utils import DownloadError

from models import Video

# yt-dlp options for fetching subtitle metadata only — no video download.
_YDL_BASE_OPTS = {
    "skip_download": True,
    "writesubtitles": True,
    "writeautomaticsub": True,
    "subtitleslangs": ["en", "en-US", "en-GB"],
    "quiet": True,
    "no_warnings": True,
}

# Preferred subtitle formats, in order. json3 is easiest to parse cleanly;
# vtt is a reliable fallback that yt-dlp always exposes.
_PREFERRED_FORMATS = ("json3", "srv3", "vtt", "ttml")
_PREFERRED_LANGS = ("en", "en-US", "en-GB")


def _build_opts() -> dict:
    """Build YoutubeDL options, layering in optional cookie config from env."""
    opts = dict(_YDL_BASE_OPTS)
    cookies_path = os.environ.get("YOUTUBE_COOKIES_PATH")
    cookies_browser = os.environ.get("YOUTUBE_COOKIES_FROM_BROWSER")
    if cookies_path:
        opts["cookiefile"] = cookies_path
    elif cookies_browser:
        # yt-dlp expects a tuple: (browser_name,) or (browser_name, profile, ...)
        opts["cookiesfrombrowser"] = (cookies_browser,)
    return opts


def _pick_track(tracks: list[dict]) -> dict | None:
    """Pick the best subtitle track URL from a list of format dicts."""
    by_ext = {t.get("ext"): t for t in tracks if t.get("url")}
    for fmt in _PREFERRED_FORMATS:
        if fmt in by_ext:
            return by_ext[fmt]
    # Fallback: first track that has a URL.
    for t in tracks:
        if t.get("url"):
            return t
    return None


def _flatten_json3(data: dict) -> str:
    """Extract text from a YouTube json3 subtitle payload."""
    out: list[str] = []
    for event in data.get("events", []) or []:
        for seg in event.get("segs", []) or []:
            text = seg.get("utf8", "")
            if text and text != "\n":
                out.append(text)
    return " ".join("".join(out).split())


def _flatten_vtt(text: str) -> str:
    """Strip WEBVTT cue headers and timestamps; return plain text."""
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("WEBVTT") or line.startswith("NOTE") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if "-->" in line:
            continue
        # Skip cue identifiers (numeric or alphanumeric tokens with no spaces).
        if line.isdigit():
            continue
        lines.append(line)
    return " ".join(" ".join(lines).split())


def _download_and_flatten(track: dict) -> str | None:
    """Fetch a subtitle track URL and reduce it to plain text."""
    url = track["url"]
    ext = track.get("ext", "")
    try:
        with urllib.request.urlopen(url, timeout=30, context=SSL_CONTEXT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[transcripts] Failed to download subtitle track: {e}")
        return None

    if ext in ("json3", "srv3"):
        try:
            return _flatten_json3(json.loads(body))
        except Exception:
            return None
    if ext == "vtt":
        return _flatten_vtt(body)
    # ttml / unknown: best-effort strip of XML tags.
    if ext == "ttml":
        import re
        stripped = re.sub(r"<[^>]+>", " ", body)
        return " ".join(stripped.split())
    return None


def _is_block_error(msg: str) -> bool:
    lower = msg.lower()
    return (
        "sign in to confirm" in lower
        or "http error 429" in lower
        or "ip" in lower and "block" in lower
        or "too many requests" in lower
    )


def _fetch(video_id: str) -> str | None:
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with yt_dlp.YoutubeDL(_build_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as e:
        msg = str(e)
        first_line = msg.splitlines()[0] if msg else "unknown error"
        if _is_block_error(msg):
            print(f"[transcripts] BLOCKED on {video_id}: {first_line}")
            print("[transcripts] See README → 'If YouTube blocks transcript fetches' for free workarounds.")
        else:
            print(f"[transcripts] Error fetching {video_id}: {first_line}")
        return None
    except Exception as e:
        print(f"[transcripts] Error fetching {video_id}: {e}")
        return None

    if not info:
        return None

    # Prefer manually-created subtitles over auto-generated ones.
    subs = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}

    for lang in _PREFERRED_LANGS:
        for source in (subs, auto):
            tracks = source.get(lang)
            if tracks:
                track = _pick_track(tracks)
                if track:
                    text = _download_and_flatten(track)
                    if text:
                        return text
    return None


def fetch_transcripts(videos: list[Video]) -> list[Video]:
    for video in videos:
        video.transcript = _fetch(video.id)
        status = "ok" if video.transcript else "no transcript"
        print(f"[transcripts] {video.title[:60]} — {status}")
    return videos
