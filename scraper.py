import subprocess

def search_matches():
    # simplificado (MVP)
    return [
        "barcelona vs real madrid",
        "manchester city vs liverpool"
    ]

def download_highlights(match):
    query = f"{match} highlights"
    output = "assets/temp/%(title)s.%(ext)s"
    cmd = f'yt-dlp "ytsearch1:{query}" -o "{output}"'
    subprocess.run(cmd, shell=True)
