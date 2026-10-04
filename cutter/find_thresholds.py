#!/usr/bin/env python3
import subprocess, re
from pathlib import Path

videos = {
    "snaptik_7439261534955523383_v3.mp4": 8,
    "snaptik_7472345980495465751_v3.mp4": 11,
    "snaptik_7477752256650038574_v3.mp4": 15,
    "snaptik_7479500895655300394_v3.mp4": 15,
    "snaptik_7493435822478331159_v3.mp4": 11,
    "snaptik_7496945851625950472_v3.mp4": 12,
    "snaptik_7589495136992742664_v3.mp4": 18,
    "snaptik_7595310889994145046_v3.mp4": 11,
    "snaptik_7597839318551416086_v3.mp4": 1,
}

BASE_DIR = Path(__file__).resolve().parent.parent
DIR = str(BASE_DIR / "backgraund/originals")

def count_scenes(filepath, threshold):
    result = subprocess.run(
        ["ffmpeg", "-i", filepath, "-vf", f"scdet=threshold={threshold}", "-f", "null", "-"],
        capture_output=True, text=True
    )
    return result.stderr.count("lavfi.scd.score") + 1

def get_cut_times(filepath, threshold):
    result = subprocess.run(
        ["ffmpeg", "-i", filepath, "-vf", f"scdet=threshold={threshold}", "-f", "null", "-"],
        capture_output=True, text=True
    )
    times = re.findall(r"lavfi\.scd\.time:\s*([\d.]+)", result.stderr)
    return [float(t) for t in times]

results = {}
for filename, target in videos.items():
    filepath = f"{DIR}/{filename}"
    if target == 1:
        results[filename] = (None, 1, [])
        print(f"{filename}: 1 parca (bolme yok)")
        continue

    lo, hi = 0.5, 50.0
    best_thresh = 5.0
    for _ in range(30):
        mid = (lo + hi) / 2
        count = count_scenes(filepath, mid)
        if count == target:
            best_thresh = mid
            break
        elif count > target:
            lo = mid
        else:
            hi = mid

    final_count = count_scenes(filepath, best_thresh)
    cut_times = get_cut_times(filepath, best_thresh)
    results[filename] = (best_thresh, final_count, cut_times)
    print(f"{filename}: threshold={best_thresh:.2f} -> {final_count} parca, kesimler: {cut_times}")

print("\n=== OZET ===")
for f, (thresh, count, cuts) in results.items():
    target = videos[f]
    status = "OK" if count == target else f"EKSIK (hedef {target})"
    print(f"{f}: {count} parca [{status}]")
