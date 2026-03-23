from datetime import date

def generate_caption(match):
    today = str(date.today())
    if isinstance(match, dict):
        return f"{today} - {match['home_team']} vs {match['away_team']} - {match['tournament']} ⚽🔥"
    return f"{today} - {match} - Football ⚽🔥"

def generate_lines():
    return [
        "Gol clave ⚽🔥",
        "Qué locura 🤯",
        "Definición perfecta 🎯",
        "Partido increíble 🔥"
    ]
