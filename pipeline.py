#!/usr/bin/env python3
import sys
from pathlib import Path

import yaml

import cache
from resolver import resolve_all
from stages.discover import discover
from stages.transcripts import fetch_transcripts
from stages.summarize import summarize
from stages.output import write_output


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def run(config_path: str = "config.yaml") -> None:
    cfg = load_config(config_path)
    channel_entries: list[str] = cfg.get("channels", [])
    max_age_hours: int = cfg.get("max_age_hours", 48)

    if not channel_entries:
        print("No channels configured. Add channel IDs or URLs to config.yaml.")
        sys.exit(1)

    # 1. Resolve any URLs / handles to bare channel IDs
    channel_ids = resolve_all(channel_entries)
    if not channel_ids:
        print("[pipeline] No channels could be resolved. Check your config.yaml entries.")
        sys.exit(1)

    # 2. Discover recent videos
    print(f"[pipeline] Discovering videos from {len(channel_ids)} channels...")
    videos = discover(channel_ids, max_age_hours=max_age_hours)
    print(f"[pipeline] Found {len(videos)} videos in the last {max_age_hours}h")

    # 3. Filter already-processed videos
    unseen_ids = set(cache.filter_unseen([v.id for v in videos]))
    videos = [v for v in videos if v.id in unseen_ids]
    print(f"[pipeline] {len(videos)} new (unseen) videos")

    if not videos:
        print("[pipeline] Nothing new. Done.")
        return

    # 4. Fetch transcripts
    videos = fetch_transcripts(videos)
    with_transcript = [v for v in videos if v.transcript]
    print(f"[pipeline] {len(with_transcript)}/{len(videos)} videos have transcripts")

    # 5. Summarize
    items = summarize(with_transcript)
    print(f"[pipeline] Summarized {len(items)} videos")

    # 6. Write output
    if items:
        write_output(items)

    # 7. Mark all fetched videos as seen (even those without transcripts)
    for v in videos:
        cache.mark_seen(v.id)

    print(f"[pipeline] Done. {len(items)} items in today's digest.")


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    run(config_path)
