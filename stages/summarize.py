import json
import anthropic

from models import Video, DigestItem

_client = anthropic.Anthropic()

_SYSTEM = (
    "You are a concise news analyst. Given a YouTube video transcript, extract the key information. "
    "Respond ONLY with valid JSON matching this schema: "
    '{"summary": "<2-3 sentence tldr>", "insights": ["<insight>", ...], "tags": ["<tag>", ...]}. '
    "Insights should be 3-5 specific, non-obvious points. Tags should be 2-4 short topic labels."
)


def _summarize(video: Video) -> DigestItem:
    with _client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=1024,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{
            "role": "user",
            "content": f"Title: {video.title}\nChannel: {video.channel}\n\nTranscript:\n{video.transcript}",
        }],
    ) as stream:
        raw = stream.get_final_message().content[0].text

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"summary": raw, "insights": [], "tags": []}

    return DigestItem(
        video=video,
        summary=data.get("summary", ""),
        insights=data.get("insights", []),
        tags=data.get("tags", []),
    )


def summarize(videos: list[Video]) -> list[DigestItem]:
    items = []
    for video in videos:
        if not video.transcript:
            continue
        try:
            item = _summarize(video)
            print(f"[summarize] {video.title[:60]}")
            items.append(item)
        except Exception as e:
            print(f"[summarize] Failed for {video.title[:60]}: {e}")
    return items
