import json
import anthropic

from models import Video, DigestItem

_client = anthropic.Anthropic()


def _build_system(interests: list[str]) -> str:
    if interests:
        quoted = ", ".join(f'"{i}"' for i in interests)
        interest_block = (
            f"The user's interests are: {quoted}. "
            "Use these to set relevance_score and identify which insights connect to them."
        )
    else:
        interest_block = (
            "No specific interests provided. Set relevance_score to 0 and relevant_insights to []."
        )

    return (
        "You are a concise news analyst. Given a YouTube video transcript, extract the key information. "
        "Respond ONLY with valid JSON matching this schema exactly:\n"
        "{\n"
        '  "summary": "<2-3 sentence tldr>",\n'
        '  "insights": ["<insight 1>", "<insight 2>", ...],\n'
        '  "tags": ["<tag>", ...],\n'
        '  "relevance_score": <integer 0-10>,\n'
        '  "relevant_insights": [<0-based indices of insights that connect to the user\'s interests>]\n'
        "}\n\n"
        "Rules:\n"
        "- insights: 3-5 specific, non-obvious points from the video.\n"
        "- tags: 2-4 short topic labels.\n"
        "- relevance_score: how directly the video addresses the user's interests. "
        "0 = no connection, 10 = directly on-topic.\n"
        "- relevant_insights: 0-based indices of insights that connect to the user's interests. "
        "Empty array if none or no interests provided.\n"
        + interest_block
    )


def _summarize(video: Video, system_prompt: str) -> DigestItem:
    with _client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=1024,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{
            "role": "user",
            "content": f"Title: {video.title}\nChannel: {video.channel}\n\nTranscript:\n{video.transcript}",
        }],
    ) as stream:
        raw = stream.get_final_message().content[0].text

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"summary": raw, "insights": [], "tags": [], "relevance_score": 0, "relevant_insights": []}

    return DigestItem(
        video=video,
        summary=data.get("summary", ""),
        insights=data.get("insights", []),
        tags=data.get("tags", []),
        relevance_score=int(data.get("relevance_score", 0)),
        relevant_insights=[int(i) for i in data.get("relevant_insights", [])],
    )


def summarize(videos: list[Video], interests: list[str] | None = None) -> list[DigestItem]:
    # Build the system prompt once so all videos in this run share the same cached string
    system_prompt = _build_system(interests or [])

    items = []
    for video in videos:
        if not video.transcript:
            continue
        try:
            item = _summarize(video, system_prompt)
            print(f"[summarize] {video.title[:60]} (relevance: {item.relevance_score}/10)")
            items.append(item)
        except Exception as e:
            print(f"[summarize] Failed for {video.title[:60]}: {e}")
    return items
