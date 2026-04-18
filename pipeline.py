#!/usr/bin/env python3
import argparse
import sys

import yaml
from dotenv import load_dotenv

load_dotenv()

import cache
from resolver import resolve_all
from stages.discover import discover
from stages.transcripts import fetch_transcripts
from stages.summarize import summarize
from stages.output import write_output
from stages.email_sender import send_email


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def run(config_path: str = "config.yaml", test: bool = False, limit: int | None = None, interests: list[str] | None = None, to: list[str] | None = None) -> None:
    cfg = load_config(config_path)
    channel_entries: list[str] = cfg.get("channels", [])
    max_age_hours: int = cfg.get("max_age_hours", 48)
    output_dir: str | None = cfg.get("output_dir")
    email_cfg: dict = cfg.get("email", {})
    interests = interests or cfg.get("interests", [])
    if interests:
        print(f"[pipeline] Interests: {', '.join(interests)}")

    if test:
        print("[pipeline] TEST MODE — cache reads and writes are disabled")

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

    # 3. Filter already-processed videos (skipped in test mode)
    if test:
        print(f"[pipeline] Skipping cache filter — processing all {len(videos)} videos")
    else:
        unseen_ids = set(cache.filter_unseen([v.id for v in videos]))
        videos = [v for v in videos if v.id in unseen_ids]
        print(f"[pipeline] {len(videos)} new (unseen) videos")

    if not videos:
        print("[pipeline] Nothing new. Done.")
        return

    # 4. Apply limit if set
    if limit:
        videos = videos[:limit]
        print(f"[pipeline] Limiting to {len(videos)} video(s)")

    # 5. Fetch transcripts
    videos = fetch_transcripts(videos)
    with_transcript = [v for v in videos if v.transcript]
    print(f"[pipeline] {len(with_transcript)}/{len(videos)} videos have transcripts")

    # 6. Summarize
    items = summarize(with_transcript, interests=interests)
    print(f"[pipeline] Summarized {len(items)} videos")

    # 6a. Sort by relevance to interests (highest first)
    items.sort(key=lambda item: item.relevance_score, reverse=True)

    # 7. Write output
    if items:
        write_output(items, output_dir=output_dir)

    # 8. Send email digest (skipped if not configured)
    if items:
        send_email(items, email_cfg, to_override=to)

    # 9. Mark all fetched videos as seen (skipped in test mode)
    if not test:
        for v in videos:
            cache.mark_seen(v.id)

    print(f"[pipeline] Done. {len(items)} items in today's digest.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the personal digest pipeline.")
    parser.add_argument("--config", default="config.yaml", help="Path to config file (default: config.yaml)")
    parser.add_argument("--test", action="store_true", help="Test mode: skip cache reads/writes so you can re-run freely")
    parser.add_argument("--limit", type=int, metavar="N", help="Process at most N videos (useful with --test)")
    parser.add_argument("--interests", nargs="+", metavar="TOPIC", help="Areas of interest to focus on (overrides config.yaml)")
    parser.add_argument("--to", nargs="+", metavar="EMAIL", help="Email address(es) to send the digest to (overrides config.yaml email.to)")
    args = parser.parse_args()

    run(config_path=args.config, test=args.test, limit=args.limit, interests=args.interests, to=args.to)
