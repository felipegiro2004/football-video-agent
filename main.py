import os
import json
import logging
import re
import shutil
from datetime import date, datetime, timedelta

from matches import get_all_matches
from config import (
    CLIPS_PER_MATCH,
    CLIP_DURATION_SECONDS,
    MAX_TOTAL_DURATION_SECONDS,
    MIN_TOTAL_DURATION_SECONDS,
    OUTPUT_DIR,
    OUTPUT_RETENTION_DAYS,
    TARGET_DATE,
    TEMP_DIR,
    TOURNAMENTS,
)
from scraper import download_highlights
from video import (
    create_placeholder_video,
    cut_clip,
    extract_audio,
    get_video_duration,
    make_vertical,
    merge_clips,
)
from audio import detect_peaks
from ai import generate_caption


LOGGER = logging.getLogger(__name__)


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def sanitize_filename(text):
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip())
    return safe.strip("_") or "video"


def reset_temp_folder():
    if os.path.isdir(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR, exist_ok=True)


def resolve_target_date():
    configured = os.getenv("RUN_DATE", TARGET_DATE)
    if not configured:
        return date.today()
    try:
        return datetime.strptime(str(configured), "%Y-%m-%d").date()
    except ValueError:
        LOGGER.warning("Invalid date '%s'. Falling back to today.", configured)
        return date.today()


def cleanup_old_output(retention_days):
    if retention_days <= 0 or not os.path.isdir(OUTPUT_DIR):
        return

    cutoff = datetime.now() - timedelta(days=retention_days)
    for entry in os.listdir(OUTPUT_DIR):
        path = os.path.join(OUTPUT_DIR, entry)
        if not os.path.isfile(path):
            continue
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            if mtime < cutoff:
                os.remove(path)
                LOGGER.info("Deleted old output: %s", path)
        except OSError:
            LOGGER.warning("Could not delete old output file: %s", path)


def choose_clip_starts(video_path, audio_path):
    duration = get_video_duration(video_path)
    if duration <= 0:
        return []

    peaks = detect_peaks(audio_path, top_k=CLIPS_PER_MATCH + 1)
    starts = []
    for peak in peaks:
        start = max(0, peak - 2.5)  # Include a few seconds before the moment.
        if start + CLIP_DURATION_SECONDS <= duration:
            starts.append(start)

    if starts:
        return starts[:CLIPS_PER_MATCH]

    # Fallback: deterministic timeline clips from first ~1 minute.
    usable_span = min(duration, 60.0)
    if usable_span <= CLIP_DURATION_SECONDS:
        return [0.0]

    gap = max(4.0, (usable_span - CLIP_DURATION_SECONDS) / max(CLIPS_PER_MATCH, 1))
    generated = []
    t = 0.0
    while len(generated) < CLIPS_PER_MATCH and t + CLIP_DURATION_SECONDS <= duration:
        generated.append(t)
        t += gap
    return generated


def build_output_paths(match):
    stem = sanitize_filename(
        f"{match['date']}_{match['home_team']}_vs_{match['away_team']}_{match['tournament']}"
    )
    return (
        os.path.join(OUTPUT_DIR, f"{stem}.mp4"),
        os.path.join(OUTPUT_DIR, f"{stem}.txt"),
    )


def write_run_report(run_date, report):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(OUTPUT_DIR, f"run_report_{run_date}_{stamp}.json")
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    LOGGER.info("Run report written: %s", report_path)


def process_match(match):
    LOGGER.info("Processing: %s (%s)", match["match_name"], match["tournament"])
    reset_temp_folder()

    highlight_path = download_highlights(match)
    if not highlight_path or not os.path.exists(highlight_path):
        LOGGER.error("No highlight found for %s. Creating placeholder output.", match["match_name"])
        video_output, caption_output = build_output_paths(match)
        placeholder_text = f"{match['home_team']} vs {match['away_team']}\\nHighlights unavailable"
        placeholder_ok = create_placeholder_video(video_output, placeholder_text, duration=15)
        caption = generate_caption(match)
        with open(caption_output, "w", encoding="utf-8") as handle:
            handle.write(caption)
        return {
            "ok": placeholder_ok,
            "reason": "placeholder_generated" if placeholder_ok else "highlight_not_found",
            "match": match["match_name"],
            "tournament": match["tournament"],
            "video_output": video_output if placeholder_ok else None,
            "caption_output": caption_output,
            "clips_used": 0,
        }

    audio_path = extract_audio(highlight_path)
    starts = choose_clip_starts(highlight_path, audio_path)
    if not starts:
        LOGGER.error("No candidate segments for %s", match["match_name"])
        return {"ok": False, "reason": "no_candidate_segments", "match": match["match_name"]}

    max_clips_by_duration = max(1, int(MAX_TOTAL_DURATION_SECONDS // CLIP_DURATION_SECONDS))
    min_clips_by_duration = max(1, int(MIN_TOTAL_DURATION_SECONDS // CLIP_DURATION_SECONDS))
    target_clips = min(max_clips_by_duration, max(min_clips_by_duration, len(starts)))
    starts = starts[:target_clips]

    vertical_clips = []
    for idx, start in enumerate(starts):
        cut_path = os.path.join(TEMP_DIR, f"clip_{idx}.mp4")
        vertical_path = os.path.join(TEMP_DIR, f"clip_{idx}_vertical.mp4")

        if not cut_clip(highlight_path, start, CLIP_DURATION_SECONDS, cut_path):
            LOGGER.warning("Cut failed at %.2fs for %s", start, match["match_name"])
            continue

        overlay = f"{match['home_team']} vs {match['away_team']}"
        if not make_vertical(cut_path, vertical_path, overlay_text=overlay):
            LOGGER.warning("Vertical conversion failed for clip %s", idx)
            continue

        vertical_clips.append(vertical_path)

    if not vertical_clips:
        LOGGER.error("No usable clips generated for %s", match["match_name"])
        return {"ok": False, "reason": "no_usable_clips", "match": match["match_name"]}

    video_output, caption_output = build_output_paths(match)
    if not merge_clips(vertical_clips, video_output):
        LOGGER.error("Merge failed for %s", match["match_name"])
        return {"ok": False, "reason": "merge_failed", "match": match["match_name"]}

    caption = generate_caption(match)
    with open(caption_output, "w", encoding="utf-8") as handle:
        handle.write(caption)

    LOGGER.info("Output ready: %s", video_output)
    return {
        "ok": True,
        "match": match["match_name"],
        "tournament": match["tournament"],
        "video_output": video_output,
        "caption_output": caption_output,
        "clips_used": len(vertical_clips),
    }

def main():
    setup_logging()
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    cleanup_old_output(OUTPUT_RETENTION_DAYS)

    target_date = resolve_target_date()
    matches = get_all_matches(TOURNAMENTS, target_date=target_date)
    LOGGER.info("Matches found for %s: %s", target_date.isoformat(), len(matches))
    if not matches:
        LOGGER.warning("No matches found for configured tournaments.")
        write_run_report(
            target_date.isoformat(),
            {
                "run_date": target_date.isoformat(),
                "generated_at": datetime.now().isoformat(),
                "matches_found": 0,
                "success_count": 0,
                "failed_count": 0,
                "items": [],
            },
        )
        return

    ok = 0
    items = []
    for match in matches:
        try:
            result = process_match(match)
            items.append(result)
            if result.get("ok"):
                ok += 1
        except Exception:
            LOGGER.exception("Unexpected failure while processing %s", match.get("match_name"))
            items.append(
                {"ok": False, "reason": "unexpected_exception", "match": match.get("match_name")}
            )

    LOGGER.info("Run finished. Success: %s / %s", ok, len(matches))
    write_run_report(
        target_date.isoformat(),
        {
            "run_date": target_date.isoformat(),
            "generated_at": datetime.now().isoformat(),
            "matches_found": len(matches),
            "success_count": ok,
            "failed_count": len(matches) - ok,
            "items": items,
        },
    )


if __name__ == "__main__":
    main()
