import logging
import re
from datetime import date

import requests

LOGGER = logging.getLogger(__name__)

# ESPN public scoreboard API slugs
TOURNAMENT_TO_SLUG = {
    "premier league": "eng.1",
    "la liga": "esp.1",
    "champions league": "uefa.champions",
}


def normalize_team_name(name):
    text = re.sub(r"\s+", " ", (name or "").strip())
    text = re.sub(r"^\d+\s*-\s*\d+\s*", "", text)
    return text


def normalize_match_name(home_team, away_team):
    return f"{normalize_team_name(home_team)} vs {normalize_team_name(away_team)}"


def get_matches_for_tournament(tournament, target_date=None):
    if target_date is None:
        target_date = date.today()

    slug = TOURNAMENT_TO_SLUG.get(tournament.lower())
    if not slug:
        LOGGER.warning("Tournament '%s' has no API mapping. Skipping.", tournament)
        return []

    day = target_date.strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard"

    try:
        response = requests.get(url, params={"dates": day}, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        LOGGER.error("Failed fetching matches for %s: %s", tournament, exc)
        return []

    data = response.json()
    events = data.get("events", [])

    matches = []
    for event in events:
        comps = event.get("competitions", [])
        if not comps:
            continue

        competitors = comps[0].get("competitors", [])
        if len(competitors) < 2:
            continue

        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
        home_team = normalize_team_name(home.get("team", {}).get("displayName", ""))
        away_team = normalize_team_name(away.get("team", {}).get("displayName", ""))

        if not home_team or not away_team:
            continue

        match_name = normalize_match_name(home_team, away_team)
        matches.append(
            {
                "match_name": match_name,
                "home_team": home_team,
                "away_team": away_team,
                "tournament": tournament.title(),
                "date": str(target_date),
            }
        )

    unique = {(m["match_name"], m["tournament"]): m for m in matches}
    return list(unique.values())


def get_all_matches(tournaments, target_date=None):
    all_matches = []

    for tournament in tournaments:
        tournament_matches = get_matches_for_tournament(tournament, target_date=target_date)
        if not tournament_matches:
            scope = target_date.isoformat() if target_date else "today"
            LOGGER.info("No matches found for %s on %s", tournament, scope)
        all_matches.extend(tournament_matches)

    unique = {(m["match_name"], m["tournament"]): m for m in all_matches}
    return list(unique.values())
