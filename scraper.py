import json
import logging
import os
import subprocess

from config import (
    HIGHLIGHT_MIN_DURATION_SECONDS,
    HIGHLIGHT_SEARCH_RESULTS,
    MAX_HIGHLIGHT_DURATION_SECONDS,
    TEMP_DIR,
)

LOGGER = logging.getLogger(__name__)


def _search_candidates(query):
    cmd = [
        "yt-dlp",
        f"ytsearch{HIGHLIGHT_SEARCH_RESULTS}:{query}",
        "--dump-single-json",
        "--no-warnings",
        "--skip-download",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        LOGGER.warning("Search failed for query '%s': %s", query, result.stderr.strip())
        return []

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        LOGGER.warning("Could not parse yt-dlp output for query '%s'", query)
        return []

    entries = payload.get("entries", []) if isinstance(payload, dict) else []
    return entries


def _is_relevant_video(entry, required_terms):
    title = (entry.get("title") or "").lower()
    duration = entry.get("duration") or 0

    if duration and (
        duration < HIGHLIGHT_MIN_DURATION_SECONDS or duration > MAX_HIGHLIGHT_DURATION_SECONDS
    ):
        return False

    # Ask for at least one team/token match and a highlight keyword.
    has_team_signal = any(term in title for term in required_terms)
    has_highlight_signal = any(word in title for word in ("highlight", "highlights", "goals", "resumen"))
    return has_team_signal and has_highlight_signal


def build_search_queries(match):
    match_name = match["match_name"]
    home = match["home_team"]
    away = match["away_team"]
    tournament = match["tournament"]
    date_str = match["date"]

    return [
        f"{match_name} {tournament} highlights {date_str}",
        f"{home} vs {away} highlights",
        f"{home} {away} goals highlights",
        f"{match_name} resumen",
    ]


def download_highlights(match):
    os.makedirs(TEMP_DIR, exist_ok=True)
    filename_base = f"{match['date']}_{match['home_team']}_vs_{match['away_team']}".replace(" ", "_")
    output = os.path.join(TEMP_DIR, f"{filename_base}.%(ext)s")
    required_terms = {
        token.lower()
        for token in [
            *match["home_team"].split(),
            *match["away_team"].split(),
        ]
        if len(token) >= 3
    }

    for query in build_search_queries(match):
        candidates = _search_candidates(query)
        for entry in candidates:
            if not _is_relevant_video(entry, required_terms):
                continue

            url = entry.get("webpage_url") or entry.get("url")
            if not url:
                continue

            cmd = ["yt-dlp", url, "-o", output, "-f", "mp4/bestvideo+bestaudio/best", "--merge-output-format", "mp4"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                # Find newest created file for this match.
                prefix = os.path.join(TEMP_DIR, filename_base)
                files = [p for p in os.listdir(TEMP_DIR) if p.startswith(os.path.basename(prefix))]
                if files:
                    selected = os.path.join(TEMP_DIR, sorted(files)[-1])
                    LOGGER.info("Downloaded highlight for %s -> %s", match["match_name"], selected)
                    return selected

            LOGGER.warning("Download failed for %s: %s", url, result.stderr.strip())

    LOGGER.error("No highlight downloaded for %s", match["match_name"])
    return None
