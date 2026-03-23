import requests
from bs4 import BeautifulSoup

def get_matches_for_league(league):
    query = f"{league} matches today"
    url = f"https://www.google.com/search?q={query}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    matches = []

    for div in soup.find_all("div"):
        text = div.get_text()

        # filtro básico
        if "vs" in text and len(text) < 40:
            matches.append(text)

    return list(set(matches))


def get_all_matches(leagues):
    all_matches = []

    for league in leagues:
        try:
            matches = get_matches_for_league(league)
            all_matches.extend(matches)
        except:
            continue

    return list(set(all_matches))
