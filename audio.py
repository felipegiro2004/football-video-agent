import librosa
import numpy as np

def _dedupe_with_gap(times, min_gap_seconds=6):
    if not times:
        return []

    ordered = sorted(times)
    filtered = [ordered[0]]
    for t in ordered[1:]:
        if t - filtered[-1] >= min_gap_seconds:
            filtered.append(t)
    return filtered


def detect_peaks(audio_file, top_k=5):
    y, sr = librosa.load(audio_file, sr=None)
    if y.size == 0:
        return []

    # Short-term energy (RMS) is better than absolute sample values.
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=512)

    if len(rms) < 10:
        return []

    threshold = np.percentile(rms, 92)
    candidate_idx = np.where(rms >= threshold)[0]
    if candidate_idx.size == 0:
        return []

    # Rank by energy descending, then keep with temporal separation.
    ranked_idx = sorted(candidate_idx, key=lambda idx: rms[idx], reverse=True)
    ranked_times = [float(times[idx]) for idx in ranked_idx]
    selected = _dedupe_with_gap(ranked_times, min_gap_seconds=6)
    return selected[:top_k]
