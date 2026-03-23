TOURNAMENTS = ["premier league", "la liga", "champions league"]

# Run date configuration:
# - Set to "YYYY-MM-DD" to run for a specific date.
# - Set to None to use today's date.
TARGET_DATE = None

# Clips and timing
CLIPS_PER_MATCH = 4
CLIP_DURATION_SECONDS = 7
MIN_TOTAL_DURATION_SECONDS = 15
MAX_TOTAL_DURATION_SECONDS = 30

# Processing folders
TEMP_DIR = "assets/temp"
OUTPUT_DIR = "output"
OUTPUT_RETENTION_DAYS = 10

# Discovery / search tuning
HIGHLIGHT_SEARCH_RESULTS = 5
HIGHLIGHT_MIN_DURATION_SECONDS = 45
MAX_HIGHLIGHT_DURATION_SECONDS = 20 * 60

# Downloader behavior
YTDLP_COOKIES_FILE = None  # optional path to Netscape cookies file
ENABLE_YOUTUBE_SEARCH = True
ENABLE_WEB_FALLBACK_SEARCH = True
ENABLE_DAILYMOTION_SEARCH = True

# Public web fallback domains/keywords to search for candidate links.
WEB_FALLBACK_PLATFORMS = [
    "dailymotion",
    "vimeo",
    "x",
    "twitter",
    "tiktok",
    "instagram",
    "facebook",
]
