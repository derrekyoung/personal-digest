from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

from models import Video


def _fetch(video_id: str) -> str | None:
    try:
        snippets = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join(s["text"] for s in snippets)
    except (NoTranscriptFound, TranscriptsDisabled):
        return None
    except Exception as e:
        print(f"[transcripts] Error fetching {video_id}: {e}")
        return None


def fetch_transcripts(videos: list[Video]) -> list[Video]:
    for video in videos:
        video.transcript = _fetch(video.id)
        status = "ok" if video.transcript else "no transcript"
        print(f"[transcripts] {video.title[:60]} — {status}")
    return videos
