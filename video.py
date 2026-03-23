import subprocess
import os

def extract_audio(video):
    audio = video.replace(".mp4", ".mp3")
    cmd = f'ffmpeg -i "{video}" -q:a 0 -map a "{audio}" -y'
    subprocess.run(cmd, shell=True)
    return audio


def cut_clip(input_video, start, duration, output):
    cmd = f'ffmpeg -ss {start} -i "{input_video}" -t {duration} -y "{output}"'
    subprocess.run(cmd, shell=True)


def make_vertical(input_file, output_file):
    cmd = f'ffmpeg -i "{input_file}" -vf "scale=1080:1920" -y "{output_file}"'
    subprocess.run(cmd, shell=True)


def merge_clips(clips, output):
    inputs = " ".join([f'-i "{c}"' for c in clips])
    cmd = f'ffmpeg {inputs} -filter_complex "concat=n={len(clips)}:v=1:a=0" -y "{output}"'
    subprocess.run(cmd, shell=True)
