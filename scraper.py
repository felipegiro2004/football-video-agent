import json
import logging
import os
import subprocess
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from config import (
    ENABLE_DAILYMOTION_SEARCH,
    ENABLE_WEB_FALLBACK_SEARCH,
    ENABLE_YOUTUBE_SEARCH,
    HIGHLIGHT_MIN_DURATION_SECONDS,
    HIGHLIGHT_SEARCH_RESULTS,
    MAX_HIGHLIGHT_DURATION_SECONDS,
    TEMP_DIR,
    WEB_FALLBACK_PLATFORMS,
    YTDLP_COOKIES_FILE,
)

LOGGER = logging.getLogger(__name__)
YOUTUBE_BOT_BLOCKED = False
WEB_VIDEO_DOMAINS = (
    "dailymotion.com",
    "vimeo.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "instagram.com",
    "facebook.com",
    "fb.watch",
    "ok.ru",
    "rutube.ru",
    "streamable.com",
)


def _search_youtube_candidates(query):
    global YOUTUBE_BOT_BLOCKED
    if not ENABLE_YOUTUBE_SEARCH or YOUTUBE_BOT_BLOCKED:
        return []

    cmd = [
        "yt-dlp",
        f"ytsearch{HIGHLIGHT_SEARCH_RESULTS}:{query}",
        "--dump-single-json",
        "--no-warnings",
        "--skip-download",
    ]
    if YTDLP_COOKIES_FILE:
        cmd.extend(["--cookies", YTDLP_COOKIES_FILE])

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr_lower = result.stderr.lower()
        if "sign in to confirm you" in stderr_lower or "not a bot" in stderr_lower:
            YOUTUBE_BOT_BLOCKED = True
            LOGGER.warning("YouTube bot protection detected. Switching to web fallback sources.")
        LOGGER.warning("Search failed for query '%s': %s", query, result.stderr.strip())
        return []

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        LOGGER.warning("Could not parse yt-dlp output for query '%s'", query)
        return []

    entries = payload.get("entries", []) if isinstance(payload, dict) else []
    return entries


def _search_dailymotion_candidates(query):
    if not ENABLE_DAILYMOTION_SEARCH:
        return []

    # Public API, no key required for basic search.
    url = "https://api.dailymotion.com/videos"
    params = {
        "search": query,
        "fields": "id,title,url,duration",
        "limit": HIGHLIGHT_SEARCH_RESULTS,
        "sort": "relevance",
    }
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        LOGGER.warning("Dailymotion search failed for '%s': %s", query, exc)
        return []

    payload = response.json()
    items = payload.get("list", [])
    normalized = []
    for item in items:
        normalized.append(
            {
                "title": item.get("title"),
                "duration": item.get("duration"),
                "webpage_url": item.get("url"),
                "source": "dailymotion",
            }
        )
    return normalized


def _search_candidates(query):
    # Try multiple sources. Keep order to preserve relevance.
    merged = []
    merged.extend(_search_dailymotion_candidates(query))
    merged.extend(_search_youtube_candidates(query))
    return merged


def _is_relevant_video(entry, required_terms):
    title = (entry.get("title") or "").lower()
    duration = entry.get("duration") or 0

    if duration and (
        duration < HIGHLIGHT_MIN_DURATION_SECONDS or duration > MAX_HIGHLIGHT_DURATION_SECONDS
    ):
        return False

    # Ask for at least one team/token match and a highlight keyword.
    has_team_signal = any(term in title for term in required_terms)
    has_highlight_signal = any(
        word in title for word in ("highlight", "highlights", "goals", "goal", "resumen", "summary")
    )
    return has_team_signal and has_highlight_signal


def _run_download(url, output):
    cmd = [
        "yt-dlp",
        url,
        "-o",
        output,
        "-f",
        "mp4/bestvideo+bestaudio/best",
        "--merge-output-format",
        "mp4",
        "--no-playlist",
        "--geo-bypass",
    ]
    if YTDLP_COOKIES_FILE:
        cmd.extend(["--cookies", YTDLP_COOKIES_FILE])
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _extract_ddg_target(href):
    parsed = urlparse(href)
    if parsed.path.startswith("/l/"):
        query = parse_qs(parsed.query)
        uddg = query.get("uddg", [])
        if uddg:
            return unquote(uddg[0])
    return href


def _web_fallback_links(match):
    if not ENABLE_WEB_FALLBACK_SEARCH:
        return []

    base_queries = [
        f"{match['home_team']} vs {match['away_team']} highlights",
        f"{match['home_team']} {match['away_team']} goals",
        f"{match['match_name']} resumen",
    ]
    queries = []
    for platform in WEB_FALLBACK_PLATFORMS:
        for base in base_queries:
            queries.append(f"{base} {platform}")

    links = []
    headers = {"User-Agent": "Mozilla/5.0"}
    for query in queries:
        try:
            response = requests.get(
                "https://duckduckgo.com/html/",
                params={"q": query},
                headers=headers,
                timeout=20,
            )
            response.raise_for_status()
        except requests.RequestException:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.select("a.result__a"):
            href = anchor.get("href", "")
            target = _extract_ddg_target(href)
            lower = target.lower()
            if any(domain in lower for domain in WEB_VIDEO_DOMAINS):
                links.append(target)

    # Keep order and unique
    unique = []
    seen = set()
    for link in links:
        if link not in seen:
            seen.add(link)
            unique.append(link)
    return unique[:10]


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

            result = _run_download(url, output)
            if result.returncode == 0:
                # Find newest created file for this match.
                prefix = os.path.join(TEMP_DIR, filename_base)
                files = [p for p in os.listdir(TEMP_DIR) if p.startswith(os.path.basename(prefix))]
                if files:
                    selected = os.path.join(TEMP_DIR, sorted(files)[-1])
                    LOGGER.info("Downloaded highlight for %s -> %s", match["match_name"], selected)
                    return selected

            LOGGER.warning("Download failed for %s: %s", url, result.stderr.strip())

    # Fallback: non-YouTube sources found via web search.
    for url in _web_fallback_links(match):
        result = _run_download(url, output)
        if result.returncode != 0:
            LOGGER.warning("Fallback download failed for %s: %s", url, result.stderr.strip())
            continue

        prefix = os.path.join(TEMP_DIR, filename_base)
        files = [p for p in os.listdir(TEMP_DIR) if p.startswith(os.path.basename(prefix))]
        if files:
            selected = os.path.join(TEMP_DIR, sorted(files)[-1])
            LOGGER.info("Downloaded fallback highlight for %s -> %s", match["match_name"], selected)
            return selected

    LOGGER.error("No highlight downloaded for %s", match["match_name"])
    return None
