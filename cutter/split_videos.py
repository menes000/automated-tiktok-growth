#!/usr/bin/env python3
import subprocess, re, os
from pathlib import Path

videos = {
    "snaptik_7439261534955523383_v3.mp4": 6.69,
    "snaptik_7472345980495465751_v3.mp4": 6.69,
    "snaptik_7477752256650038574_v3.mp4": 3.59,
    "snaptik_7479500895655300394_v3.mp4": 2.05,
    "snaptik_7493435822478331159_v3.mp4": 3.59,
    "snaptik_7496945851625950472_v3.mp4": 5.53,
    "snaptik_7589495136992742664_v3.mp4": 8.23,
    "snaptik_7595310889994145046_v3.mp4": 1.37,
    "snaptik_7597839318551416086_v3.mp4": None,  # tek parca
}

BASE_DIR = Path(__file__).resolve().parent.parent
DIR = str(BASE_DIR / "backgraund/originals")
OUT = str(BASE_DIR / "backgraund/split")
os.makedirs(OUT, exist_ok=True)

def get_duration(filepath):
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", filepath],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())

def get_cut_times(filepath, threshold):
    result = subprocess.run(
        ["ffmpeg", "-i", filepath, "-vf", f"scdet=threshold={threshold}", "-f", "null", "-"],
        capture_output=True, text=True
    )
    times = re.findall(r"lavfi\.scd\.time:\s*([\d.]+)", result.stderr)
    return [float(t) for t in times]

for filename, threshold in videos.items():
    filepath = f"{DIR}/{filename}"
    base = filename.replace(".mp4", "")
    duration = get_duration(filepath)

    if threshold is None:
        # Tek parca - kopyala
        out = f"{OUT}/{base}_part01.mp4"
        subprocess.run(["ffmpeg", "-y", "-i", filepath, "-c", "copy", out], capture_output=True)
        print(f"{filename} -> 1 parca kopyalandi")
        continue

    cuts = get_cut_times(filepath, threshold)
    segments = []
    prev = 0.0
    for t in cuts:
        segments.append((prev, t))
        prev = t
    segments.append((prev, duration))

    print(f"{filename}: {len(segments)} parca bolunuyor...")
    for i, (start, end) in enumerate(segments, 1):
        out = f"{OUT}/{base}_part{i:02d}.mp4"
        subprocess.run([
            "ffmpeg", "-y",
            "-i", filepath,
            "-ss", str(start),
            "-to", str(end),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "128k",
            out
        ], capture_output=True)
        print(f"  part{i:02d}: {start:.2f}s - {end:.2f}s ({end-start:.2f}s)")

print("\nTamamlandi! Dosyalar:", OUT)
