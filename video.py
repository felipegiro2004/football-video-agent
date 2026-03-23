import subprocess
import os

def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def get_video_duration(video_path):
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = _run(cmd)
    if result.returncode != 0:
        return 0.0
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def extract_audio(video):
    audio = video.replace(".mp4", ".mp3")
    cmd = ["ffmpeg", "-i", video, "-q:a", "0", "-map", "a", audio, "-y"]
    _run(cmd)
    return audio


def cut_clip(input_video, start, duration, output):
    os.makedirs(os.path.dirname(output), exist_ok=True)
    cmd = [
        "ffmpeg",
        "-ss",
        str(max(0, start)),
        "-i",
        input_video,
        "-t",
        str(duration),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-an",
        "-y",
        output,
    ]
    result = _run(cmd)
    return result.returncode == 0 and os.path.exists(output)


def make_vertical(input_file, output_file, overlay_text=None):
    filter_chain = [
        "scale=1080:1920:force_original_aspect_ratio=increase",
        "crop=1080:1920",
    ]
    if overlay_text:
        drawtext = (
            "drawtext=text='{text}':x=(w-text_w)/2:y=h*0.07:"
            "fontsize=42:fontcolor=white:borderw=2:bordercolor=black"
        ).format(text=overlay_text.replace(":", "\\:").replace("'", "\\'"))
        filter_chain.append(drawtext)

    cmd = [
        "ffmpeg",
        "-i",
        input_file,
        "-vf",
        ",".join(filter_chain),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-an",
        "-y",
        output_file,
    ]
    result = _run(cmd)
    return result.returncode == 0 and os.path.exists(output_file)


def merge_clips(clips, output):
    if not clips:
        return False

    args = ["ffmpeg"]
    for clip in clips:
        args.extend(["-i", clip])

    args.extend(
        [
            "-filter_complex",
            f"concat=n={len(clips)}:v=1:a=0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-y",
            output,
        ]
    )
    result = _run(args)
    return result.returncode == 0 and os.path.exists(output)
