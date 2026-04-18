import re
import sqlite3
from pathlib import Path
from urllib.request import urlopen, Request

DB_PATH = Path(__file__).parent / "cache.db"

# Matches a bare YouTube channel ID: "UC" + 22 base64url characters
_CHANNEL_ID_RE = re.compile(r'^UC[\w-]{22}$')


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS channels (input TEXT PRIMARY KEY, channel_id TEXT NOT NULL)"
    )
    conn.commit()
    return conn


def _get_cached(entry: str) -> str | None:
    with _conn() as conn:
        row = conn.execute("SELECT channel_id FROM channels WHERE input = ?", (entry,)).fetchone()
        return row[0] if row else None


def _store(entry: str, channel_id: str) -> None:
    with _conn() as conn:
        conn.execute("INSERT OR REPLACE INTO channels VALUES (?, ?)", (entry, channel_id))
        conn.commit()


def _extract_from_page(url: str) -> str:
    """Fetch a YouTube channel page and pull the channel ID out of the RSS feed link."""
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=10) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    # Most reliable: the RSS alternate link always contains the real channel ID
    match = re.search(r'feeds/videos\.xml\?channel_id=(UC[\w-]{22})', html)
    if match:
        return match.group(1)

    # Fallback: channelId in the page's inline JSON
    match = re.search(r'"channelId"\s*:\s*"(UC[\w-]{22})"', html)
    if match:
        return match.group(1)

    raise ValueError(f"Could not find a channel ID on page: {url}")


def resolve(entry: str) -> str:
    """
    Resolve any channel reference to a bare channel ID.

    Accepts:
      - Bare ID:           UCBcRF18a7Qf58cCRy5xuWwQ
      - /channel/ URL:     https://www.youtube.com/channel/UCBcRF18a7Qf58cCRy5xuWwQ
      - @handle URL:       https://www.youtube.com/@mkbhd
      - Bare @handle:      @mkbhd
      - Legacy /c/ URL:    https://www.youtube.com/c/mkbhd
      - Short URL:         https://youtu.be/...  (channel page, not a video)

    Resolved IDs are stored in cache.db so the page fetch only happens once.
    """
    entry = entry.strip()

    # Already a bare channel ID — nothing to do
    if _CHANNEL_ID_RE.match(entry):
        return entry

    # Check cache before doing any network request
    cached = _get_cached(entry)
    if cached:
        return cached

    # /channel/UC... URL — ID is right there, no fetch needed
    inline = re.search(r'/channel/(UC[\w-]{22})', entry)
    if inline:
        channel_id = inline.group(1)
        _store(entry, channel_id)
        return channel_id

    # Normalize everything else to a full URL
    if entry.startswith("@"):
        url = f"https://www.youtube.com/{entry}"
    elif not entry.startswith("http"):
        url = f"https://www.youtube.com/{entry}"
    else:
        url = entry

    print(f"[resolver] Resolving {entry} ...")
    channel_id = _extract_from_page(url)
    _store(entry, channel_id)
    print(f"[resolver] {entry} → {channel_id}")
    return channel_id


def resolve_all(entries: list[str]) -> list[str]:
    results = []
    for entry in entries:
        try:
            results.append(resolve(entry))
        except Exception as e:
            print(f"[resolver] Failed to resolve '{entry}': {e}")
    return results
