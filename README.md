# personal-digest

Pulls recent YouTube videos from channels you follow, fetches their transcripts, and uses Claude to produce a daily markdown digest with summaries and key insights. Runs locally, no YouTube API key required.

---

## How it works

```
config.yaml (channel IDs)
    ↓
discover       — fetches YouTube RSS feeds to find videos published in the last N hours
    ↓
filter         — skips videos already seen (SQLite cache)
    ↓
transcripts    — pulls auto-generated or manual captions directly from YouTube
    ↓
summarize      — sends each transcript to Claude, gets a summary + insights + tags
    ↓
output         — writes output/digest_YYYY-MM-DD.md + macOS notification
```

---

## Getting started

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

If you're on macOS with Homebrew, use a virtual environment to avoid conflicts with the system Python:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Whenever you return to work on this project, activate the environment first:

```bash
source venv/bin/activate
```

To deactivate when you're done:

```bash
deactivate
```

**2. Set your Anthropic API key**

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Add this to your shell profile (`~/.zshrc` or `~/.bashrc`) to make it permanent.

**3. Add your channels to `config.yaml`**

You can use any format — the app resolves it to a channel ID automatically and caches the result, so the lookup only happens once per entry:

```yaml
channels:
  - "@mkbhd"                                              # bare handle
  - "https://www.youtube.com/@LinusTechTips"             # full handle URL
  - "https://www.youtube.com/c/veritasium"               # legacy /c/ URL
  - "https://www.youtube.com/channel/UCBcRF18a7Qf58cCRy5xuWwQ"  # channel URL
  - UCBcRF18a7Qf58cCRy5xuWwQ                             # bare ID (also works)

max_age_hours: 48  # how far back to look for new videos
```

The first time the pipeline runs with a new URL or handle, it fetches the channel page to extract the ID and stores it in `cache.db`. Every subsequent run uses the cached ID — no network lookup needed.

**4. Run it**

```bash
python pipeline.py
```

Output lands in `output/digest_YYYY-MM-DD.md`. A macOS notification fires when complete.

---

## Running on a schedule

To run daily automatically, add a cron job:

```bash
crontab -e
```

```cron
0 8 * * * cd /path/to/personal-digest && ANTHROPIC_API_KEY=sk-ant-... python pipeline.py >> logs/digest.log 2>&1
```

Or use `launchd` on macOS for more reliable scheduling when the machine is asleep.

---

## Gotchas

**Videos without transcripts are silently skipped.**
Many videos have no captions — live streams, videos with music only, channels that disable captions, or very new uploads where auto-captions haven't generated yet. The pipeline logs `no transcript` for each skip and still marks the video as seen so it won't be retried on the next run.

**Auto-generated captions can be noisy.**
YouTube's auto-captions don't include punctuation and often mangle proper nouns, technical terms, and non-English words. Claude handles this well in practice, but summaries for low-quality transcripts will be lower quality too. If a channel has manual captions, those are used preferentially.

**The cache is permanent by default.**
`cache.db` (SQLite) records every video ID that has been processed. Once a video is marked seen, it won't be re-processed even if the summary was bad or the transcript failed. To force a rerun of a specific video, delete its row:

```bash
sqlite3 cache.db "DELETE FROM seen WHERE video_id = 'dQw4w9WgXcQ';"
```

To reset everything and start fresh:

```bash
rm cache.db
```

**RSS feeds only return the 15 most recent videos.**
YouTube's RSS endpoint doesn't support pagination. If a channel posts more than 15 videos within your `max_age_hours` window, older ones will be missed. This is unlikely for most channels but worth knowing for very high-volume feeds.

**Channel IDs vs. handle URLs are different.**
`@mkbhd` is a handle, not a channel ID. The RSS feed requires the raw `UC...` ID format. Handles don't work.

**YouTube may rate-limit transcript fetches.**
`youtube-transcript-api` scrapes YouTube's timedtext endpoint, the same one your browser uses. Heavy usage (dozens of videos in rapid succession) may result in temporary 429 errors. The pipeline logs these and continues — affected videos are still marked seen and won't be retried. If this becomes a recurring issue, add a `time.sleep(1)` between fetches in `stages/transcripts.py`.

---

## Notes

**Prompt caching reduces cost on large runs.**
The Claude system prompt is sent with `cache_control: ephemeral`. After the first video summary, subsequent summaries in the same run read the system prompt from Anthropic's cache (~10% of normal cost for that portion). For runs with many videos this adds up.

**The cache marks videos seen regardless of whether summarization succeeded.**
This is intentional — if a transcript exists but Claude fails for some reason, you probably don't want to retry on every subsequent run. If you want to re-summarize a failed video, remove it from the cache manually (see above).

**Digests are append-safe.**
Running the pipeline twice in one day produces two separate files only if the timestamps differ enough to generate a different filename — but since filenames use `YYYY-MM-DD`, a second same-day run will overwrite the first. The cache ensures no video is summarized twice regardless.

---

## Debugging

**Nothing shows up in the digest**

Check each stage in sequence:

```bash
# Are your channel IDs correct? Test an RSS feed directly:
curl "https://www.youtube.com/feeds/videos.xml?channel_id=UCBcRF18a7Qf58cCRy5xuWwQ"

# Have all recent videos already been cached?
sqlite3 cache.db "SELECT COUNT(*) FROM seen;"
sqlite3 cache.db "SELECT * FROM seen LIMIT 20;"

# Reset the cache and rerun with a wider window:
rm cache.db
# Edit config.yaml: max_age_hours: 168  (7 days)
python pipeline.py
```

**Transcript errors**

```
[transcripts] VideoName — no transcript
```

This is expected for videos without captions. If you're seeing it for videos that definitely have captions, the video may be too new (auto-captions can take minutes to an hour to generate) or the `youtube-transcript-api` library may need updating:

```bash
pip install --upgrade youtube-transcript-api
```

**Claude API errors**

```
[summarize] Failed for VideoName: ...
```

Common causes:
- `AuthenticationError` — `ANTHROPIC_API_KEY` is not set or is invalid
- `RateLimitError` — you've hit your API rate limit; the pipeline will continue and skip that video
- `BadRequestError` — the transcript was too long. Very long videos (3+ hours) may exceed the context window. You can truncate transcripts in `stages/transcripts.py` before passing to Claude.

**Channel resolution fails**

```
[resolver] Failed to resolve '@somechannel': Could not find a channel ID on page: ...
```

The handle or URL may be misspelled, the channel may have been deleted, or YouTube blocked the page fetch. Verify it by visiting the URL directly in a browser. Once you've confirmed the correct URL, the resolved ID is cached — to force a re-resolution, delete the row:

```bash
sqlite3 cache.db "DELETE FROM channels WHERE input = '@somechannel';"
```

To see all currently cached channel resolutions:

```bash
sqlite3 cache.db "SELECT * FROM channels;"
```

**RSS feed fetch errors**

```
[discover] Failed to fetch UCxxxxxxx: ...
```

The channel ID may be wrong, the channel may have been deleted, or YouTube may be temporarily blocking requests. Verify by visiting the RSS URL directly in a browser:
`https://www.youtube.com/feeds/videos.xml?channel_id=UCxxxxxxx`

**macOS notification doesn't appear**

The notification uses `osascript`, which requires notification permissions. Go to System Settings → Notifications → Script Editor (or Terminal, depending on how you run the script) and enable notifications. Notification failures are silent and don't affect the digest output.

---

## Project structure

```
personal-digest/
├── pipeline.py          # entry point
├── config.yaml          # channel URLs/handles and settings
├── models.py            # Video and DigestItem dataclasses
├── cache.py             # SQLite-backed seen-video filter
├── resolver.py          # resolves URLs/handles to channel IDs, caches results
├── requirements.txt
├── stages/
│   ├── discover.py      # YouTube RSS → List[Video]
│   ├── transcripts.py   # transcript fetching
│   ├── summarize.py     # Claude summarization
│   └── output.py        # markdown writer + notification
├── output/              # generated digests (created on first run)
└── cache.db             # SQLite database (created on first run)
```
