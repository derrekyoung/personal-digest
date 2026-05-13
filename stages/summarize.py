import json

from models import Video, DigestItem

DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODEL_BY_PROVIDER = {
    "anthropic": "claude-opus-4-7",
    "openai": "gpt-4.1-mini",
}

_anthropic_client = None
_openai_client = None


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


def _normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized in {"claude", "anthropic"}:
        return "anthropic"
    if normalized == "openai":
        return "openai"
    raise ValueError(f"Unsupported LLM provider '{provider}'. Use 'anthropic' or 'openai'.")


def _resolve_llm_config(llm_config: dict | None) -> tuple[str, str]:
    cfg = llm_config or {}
    provider = _normalize_provider(str(cfg.get("provider", DEFAULT_PROVIDER)))
    model = str(cfg.get("model") or DEFAULT_MODEL_BY_PROVIDER[provider]).strip()
    return provider, model


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError("Anthropic support requires installing the 'anthropic' package.") from exc
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("OpenAI support requires installing the 'openai' package.") from exc
        _openai_client = OpenAI()
    return _openai_client


def _build_user_message(video: Video) -> str:
    return f"Title: {video.title}\nChannel: {video.channel}\n\nTranscript:\n{video.transcript}"


def _summarize_with_anthropic(video: Video, system_prompt: str, model: str) -> str:
    client = _get_anthropic_client()
    with client.messages.stream(
        model=model,
        max_tokens=1024,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": _build_user_message(video)}],
    ) as stream:
        return stream.get_final_message().content[0].text


def _summarize_with_openai(video: Video, system_prompt: str, model: str) -> str:
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": _build_user_message(video)},
        ],
    )
    return response.choices[0].message.content or ""


def _summarize(video: Video, system_prompt: str, provider: str, model: str) -> DigestItem:
    if provider == "anthropic":
        raw = _summarize_with_anthropic(video, system_prompt, model)
    elif provider == "openai":
        raw = _summarize_with_openai(video, system_prompt, model)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

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


def summarize(
    videos: list[Video], interests: list[str] | None = None, llm_config: dict | None = None
) -> list[DigestItem]:
    provider, model = _resolve_llm_config(llm_config)
    print(f"[summarize] Provider: {provider}, model: {model}")

    # Build the system prompt once so all videos in this run share the same cached string
    system_prompt = _build_system(interests or [])

    items = []
    for video in videos:
        if not video.transcript:
            continue
        try:
            item = _summarize(video, system_prompt, provider, model)
            print(f"[summarize] {video.title[:60]} (relevance: {item.relevance_score}/10)")
            items.append(item)
        except Exception as e:
            print(f"[summarize] Failed for {video.title[:60]}: {e}")
    return items
