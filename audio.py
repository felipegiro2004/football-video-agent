import librosa
import numpy as np

def detect_peaks(audio_file):
    y, sr = librosa.load(audio_file)

    energy = np.abs(y)
    threshold = np.percentile(energy, 95)

    peaks = np.where(energy > threshold)[0]
    times = librosa.frames_to_time(peaks, sr=sr)

    return list(set(times))[:10]
