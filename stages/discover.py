import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen

from models import Video

RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
NS = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


def _parse_feed(channel_id: str, max_age_hours: int) -> list[Video]:
    url = RSS_URL.format(channel_id=channel_id)
    with urlopen(url, timeout=10) as resp:
        root = ET.fromstring(resp.read())

    channel_name = root.findtext("atom:title", namespaces=NS) or channel_id
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    videos = []

    for entry in root.findall("atom:entry", NS):
        published_str = entry.findtext("atom:published", namespaces=NS) or ""
        try:
            published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        if published_at < cutoff:
            continue

        video_id = entry.findtext("yt:videoId", namespaces=NS) or ""
        title = entry.findtext("atom:title", namespaces=NS) or ""
        url = f"https://www.youtube.com/watch?v={video_id}"

        videos.append(Video(
            id=video_id,
            title=title,
            channel=channel_name,
            url=url,
            published_at=published_at,
        ))

    return videos


def discover(channel_ids: list[str], max_age_hours: int = 48) -> list[Video]:
    videos = []
    for channel_id in channel_ids:
        try:
            videos.extend(_parse_feed(channel_id, max_age_hours))
        except Exception as e:
            print(f"[discover] Failed to fetch {channel_id}: {e}")
    return videos
