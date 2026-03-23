import os
from scraper import search_matches, download_highlights
from video import extract_audio, cut_clip, make_vertical, merge_clips
from audio import detect_peaks
from ai import generate_caption, generate_lines

def main():
    os.makedirs("assets/temp", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    matches = search_matches()

    for match in matches:
        print("⚽ Procesando:", match)

        download_highlights(match)

        videos = [f for f in os.listdir("assets/temp") if f.endswith(".mp4")]

        if not videos:
            continue

        video_path = f"assets/temp/{videos[-1]}"

        audio = extract_audio(video_path)
        peaks = detect_peaks(audio)

        clips = []
        for i, t in enumerate(peaks[:4]):
            out = f"assets/temp/clip_{i}.mp4"
            cut_clip(video_path, t, 8, out)

            vert = f"assets/temp/vert_{i}.mp4"
            make_vertical(out, vert)

            clips.append(vert)

        final_video = f"output/{match.replace(' ', '_')}.mp4"
        merge_clips(clips, final_video)

        caption = generate_caption(match)

        with open(f"output/{match}.txt", "w") as f:
            f.write(caption)

        print("✅ Video listo:", final_video)


if __name__ == "__main__":
    main()
