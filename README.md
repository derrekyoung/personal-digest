# personal-digest

Pulls recent YouTube videos from channels you follow, fetches their transcripts, and uses Claude or OpenAI to produce a daily markdown digest with summaries and key insights. Runs locally, no YouTube API key required.

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
summarize      — sends each transcript to your configured LLM provider, gets a summary + insights + tags
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

**2. Choose your LLM provider and set its API key**

By default, summarization uses Anthropic Claude. To switch providers, set the `llm` block in `config.yaml`:

```yaml
llm:
  provider: anthropic   # anthropic (default) or openai
  # model: claude-opus-4-7   # optional model override
```

Set the matching API key:

```bash
# for Claude
export ANTHROPIC_API_KEY=sk-ant-...

# for OpenAI
export OPENAI_API_KEY=sk-proj-...
```

Add whichever variable you use to your shell profile (`~/.zshrc` or `~/.bashrc`) to make it permanent.

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

llm:
  provider: anthropic  # or openai
  # model: claude-opus-4-7  # optional model override
```

The first time the pipeline runs with a new URL or handle, it fetches the channel page to extract the ID and stores it in `cache.db`. Every subsequent run uses the cached ID — no network lookup needed.

**4. Run it**

```bash
python pipeline.py
```

Output lands in `output/digest_YYYY-MM-DD.md`. A macOS notification fires when complete.

---

## Testing

While developing or troubleshooting, the cache can get in the way — videos get marked seen and won't reprocess on subsequent runs. Use `--test` to bypass this entirely:

```bash
# Ignore the cache — re-processes all recent videos every time, never writes to cache.db
python pipeline.py --test

# Same, but cap at 1 video — fastest way to verify the full pipeline end-to-end
python pipeline.py --test --limit 1

# Process at most 3 videos without touching the cache
python pipeline.py --test --limit 3
```

`--test` skips both the "filter already seen" step and the "mark as seen" step, so `cache.db` is left completely untouched. You can run it as many times as you want without needing to clear the database.

`--limit N` works independently of `--test` — you can also use it in normal mode to do a partial run:

```bash
# Normal run, but only process the 2 most recent unseen videos
python pipeline.py --limit 2
```

---

## Secrets and environment variables

Sensitive values (API keys, email passwords) are stored in a `.env` file that is never committed to git.

**1. Copy the example file and fill in your values**

```bash
cp .env.example .env
```

Then edit `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...
DIGEST_EMAIL_PASSWORD=xxxx xxxx xxxx xxxx
```

The app loads `.env` automatically on startup via `python-dotenv`. `.env` is listed in `.gitignore` — only `.env.example` (with placeholder values) is tracked.

---

## Email delivery

The pipeline can optionally email the digest as a formatted HTML message after each run. It uses Python's built-in `smtplib` — no extra dependencies.

**1. Get an App Password from your email provider**

Gmail requires an App Password for programmatic sending (your regular password won't work):
1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) (requires 2FA to be enabled)
2. Create a new app password — name it anything (e.g. "personal-digest")
3. Copy the 16-character password

For iCloud Mail, go to [appleid.apple.com](https://appleid.apple.com) → Sign-In and Security → App-Specific Passwords.

**2. Store the password in `.env`**

Add your app password to `.env` (see [Secrets and environment variables](#secrets-and-environment-variables) above):

```
DIGEST_EMAIL_PASSWORD=xxxx xxxx xxxx xxxx
```

**3. Configure `config.yaml`**

Uncomment and fill in the `email` block:

```yaml
email:
  enabled: true                   # set to false (or omit) to disable email
  smtp_host: smtp.gmail.com       # smtp.mail.me.com for iCloud
  smtp_port: 587
  username: you@gmail.com
  from: you@gmail.com
  to:
    - you@gmail.com
    - someone@example.com
```

Email is skipped silently if the `email` block is absent, `enabled` is `false` (the default), or `to` is empty.

**4. Override recipients at the command line**

Use `--to` to send to one or more addresses without editing `config.yaml`:

```bash
python pipeline.py --to someone@example.com
python pipeline.py --to alice@example.com bob@example.com
```

`--to` also acts as a fallback for `username` and `from` when those aren't set in `config.yaml`. This means you can do a one-off send with just the flag and a password — no `config.yaml` email block needed:

```bash
python pipeline.py --to me@gmail.com  # uses me@gmail.com for username, from, and to
```

Config values always win: `--to` only fills in fields that are absent from `config.yaml`.

---

## Custom output directory

By default, digests are written to `output/` inside the project directory. To send them somewhere else — an Obsidian vault, a Dropbox folder, etc. — set `output_dir` in `config.yaml`:

```yaml
output_dir: ~/Documents/Obsidian/Digests
```

Supports absolute paths and `~` expansion. The directory is created automatically if it doesn't exist.

---

## If YouTube blocks transcript fetches

YouTube aggressively blocks transcript requests from cloud-provider IPs and sometimes rate-limits residential IPs after heavy use. When this happens you'll see `BLOCKED on …` log lines from the `[transcripts]` stage and an empty digest. There are two free workarounds — pick whichever fits your run environment.

**Option 1 — Local: read cookies straight from your browser**

If you're running locally and signed into YouTube in any browser, point yt-dlp at that browser's cookie store. No file to manage.

```
# in .env
YOUTUBE_COOKIES_FROM_BROWSER=safari   # or chrome, firefox, edge, brave
```

That's it — yt-dlp pulls cookies live from the browser profile on every run. Doesn't work for remote runs (no browser to read from).

**Option 2 — Local + remote: cookies.txt file**

Export a Netscape-format `cookies.txt` while signed into youtube.com using the **Get cookies.txt LOCALLY** browser extension ([Chrome](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) / [Firefox](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt-one-click/)). Save it as `cookies.txt` in the repo root (it's gitignored).

```
# in .env
YOUTUBE_COOKIES_PATH=cookies.txt
```

Cookies typically last a few weeks before YouTube rotates them — re-export when you start seeing `BLOCKED` again. Note that YouTube can theoretically ban accounts used this way; use a low-stakes account if that worries you.

**For remote runs**, store the cookies content as a repo secret (see the Cowork section below).

---

## Running as a scheduled Claude Cowork job

Claude Cowork's scheduled jobs run as **remote agents in Anthropic's cloud** — they do not have access to your local machine or local files. To schedule this pipeline:

**Prerequisites**

1. Push this repo to GitHub (the remote agent clones it fresh each run)
2. The provider API key must be available in the remote environment (`ANTHROPIC_API_KEY` for Claude or `OPENAI_API_KEY` for OpenAI) — set it as a repository secret or include it in the agent prompt (see below)
3. Make sure `output_dir` in `config.yaml` points somewhere the output can be recovered from — the most practical option is a path inside the repo so the agent can commit it back

**Suggested config for scheduled runs**

```yaml
# config.yaml
output_dir: digests   # relative path inside the repo — agent commits it back
max_age_hours: 25     # slightly over 24h to avoid edge cases on daily runs
```

**Setting up the trigger**

In a Claude Cowork session, use `/schedule` and ask to create a new scheduled trigger. When prompted for the agent prompt, use something like:

```
Clone the repo. If the YOUTUBE_COOKIES_B64 secret is set, decode it to cookies.txt
and export YOUTUBE_COOKIES_PATH so yt-dlp picks it up:

  if [ -n "$YOUTUBE_COOKIES_B64" ]; then
    echo "$YOUTUBE_COOKIES_B64" | base64 -d > cookies.txt
    export YOUTUBE_COOKIES_PATH=cookies.txt
  fi

Then run the pipeline:

  python3 -m venv venv && source venv/bin/activate
  pip install -q -r requirements.txt
  python pipeline.py

After the pipeline completes, commit any new files in the digests/ directory and push to main:
  git add digests/
  git config user.email "digest-bot@users.noreply.github.com"
  git config user.name "Digest Bot"
  git commit -m "digest: $(date +%Y-%m-%d)" || echo "nothing to commit"
  git push
```

Set the schedule to whatever cadence you want (minimum 1 hour). Daily at 8am ET is `0 13 * * *` in UTC.

**Handling YouTube IP blocks on remote runs**

Anthropic's cloud IPs are usually blocked by YouTube. If your first remote run logs `BLOCKED on …` for every video, add cookies as a repo secret:

1. Export `cookies.txt` locally while signed into youtube.com (see [If YouTube blocks transcript fetches](#if-youtube-blocks-transcript-fetches)).
2. Base64-encode it: `base64 -i cookies.txt | pbcopy` (macOS).
3. Add it to the repo as a secret named `YOUTUBE_COOKIES_B64`.

The agent prompt above already decodes the secret into `cookies.txt` and exports `YOUTUBE_COOKIES_PATH` — no further changes needed. Re-export and update the secret every few weeks when YouTube rotates cookies.

**Retrieving the output**

After each run, `git pull` locally to get the latest digest files from the `digests/` directory. Or point `output_dir` at a path your sync tool watches.

---

## Running on a schedule

To run daily automatically, add a cron job:

```bash
crontab -e
```

```cron
0 8 * * * cd /path/to/personal-digest && ANTHROPIC_API_KEY=sk-ant-... python pipeline.py >> logs/digest.log 2>&1
```

If you're using OpenAI, export `OPENAI_API_KEY` instead and set `llm.provider: openai` in `config.yaml`.

Or use `launchd` on macOS for more reliable scheduling when the machine is asleep.

---

## Gotchas

**Videos without transcripts are silently skipped.**
Many videos have no captions — live streams, videos with music only, channels that disable captions, or very new uploads where auto-captions haven't generated yet. The pipeline logs `no transcript` for each skip and still marks the video as seen so it won't be retried on the next run.

**Auto-generated captions can be noisy.**
YouTube's auto-captions don't include punctuation and often mangle proper nouns, technical terms, and non-English words. Modern LLMs handle this well in practice, but summaries for low-quality transcripts will be lower quality too. If a channel has manual captions, those are used preferentially.

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

**YouTube may block transcript fetches.**
The pipeline uses `yt-dlp` to pull subtitles from YouTube. If you see `BLOCKED on …` in the logs and an empty digest, your IP has been rate-limited or blocked. This is common on cloud-provider IPs (AWS, GCP, Azure, Anthropic's cloud) and occasionally hits residential IPs after heavy usage. See [If YouTube blocks transcript fetches](#if-youtube-blocks-transcript-fetches) below for free workarounds.

---

## Notes

**Prompt caching reduces cost on large runs (Anthropic only).**
When using Claude, the system prompt is sent with `cache_control: ephemeral`. After the first video summary, subsequent summaries in the same run read the system prompt from Anthropic's cache (~10% of normal cost for that portion). For runs with many videos this adds up.

**The cache marks videos seen regardless of whether summarization succeeded.**
This is intentional — if a transcript exists but summarization fails for some reason, you probably don't want to retry on every subsequent run. If you want to re-summarize a failed video, remove it from the cache manually (see above).

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

**LLM API errors**

```
[summarize] Failed for VideoName: ...
```

Common causes:
- `AuthenticationError` — your configured provider key (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`) is not set or is invalid
- `RateLimitError` — you've hit your API rate limit; the pipeline will continue and skip that video
- `BadRequestError` — the transcript was too long. Very long videos (3+ hours) may exceed the context window. You can truncate transcripts in `stages/transcripts.py` before passing to the model.

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

If you see SSL errors like `CERTIFICATE_VERIFY_FAILED`, your Python install likely doesn't trust the system CA store correctly. Update dependencies so `certifi` is installed and retry:

```bash
pip install -r requirements.txt
```

On macOS with python.org builds, you may also need to run the bundled certificate installer once:

```bash
open "/Applications/Python 3.*/Install Certificates.command"
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
├── .env.example         # template for secrets (committed); copy to .env and fill in
├── models.py            # Video and DigestItem dataclasses
├── cache.py             # SQLite-backed seen-video filter
├── resolver.py          # resolves URLs/handles to channel IDs, caches results
├── requirements.txt
├── stages/
│   ├── discover.py      # YouTube RSS → List[Video]
│   ├── transcripts.py   # transcript fetching
│   ├── summarize.py     # LLM summarization (Anthropic/OpenAI)
│   └── output.py        # markdown writer + notification
├── output/              # generated digests (created on first run)
└── cache.db             # SQLite database (created on first run)
```
