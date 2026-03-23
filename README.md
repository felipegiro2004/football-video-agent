# football-video-agent

Automated short-form football highlights pipeline for TikTok-style videos.

## What it does
- Finds matches for configured tournaments on a target date.
- Searches and downloads likely highlight videos with fallbacks.
- Detects high-energy moments and creates 9:16 clips.
- Merges clips into one short per match.
- Writes one caption file per video.
- Generates a JSON run report for debugging.

## Sources strategy
- Uses multiple sources instead of YouTube-only:
  - Dailymotion API search
  - YouTube search via yt-dlp (optional)
  - Web fallback links (DuckDuckGo + known video domains: X/Twitter, TikTok, Instagram, Facebook, Vimeo, etc.)
- If no highlight is downloadable, it still creates a placeholder vertical output to avoid empty runs.

## Configure date
Use either option:

1) In `config.py`, set:
- `TARGET_DATE = "YYYY-MM-DD"` to force a date
- `TARGET_DATE = None` to use today

2) Override from environment:
- `RUN_DATE=YYYY-MM-DD`

`RUN_DATE` has priority over `TARGET_DATE`.

## Output
All outputs are written to `output/`:
- `*.mp4` final videos
- `*.txt` captions
- `run_report_*.json` run diagnostics

Old files are auto-cleaned based on `OUTPUT_RETENTION_DAYS` in `config.py`.