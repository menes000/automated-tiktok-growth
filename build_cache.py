#!/usr/bin/env python3
"""
Tüm şarkıların beat cache'lerini oluşturur.
Yeni şarkı ekleyince tekrar çalıştır.
"""
import subprocess, os, json
from pathlib import Path
import librosa

BASE_DIR          = Path(__file__).parent
SONGS_DIR         = str(BASE_DIR / 'songs')
MAX_BEAT_INTERVAL = 0.5
VIDEO_DURATION    = 12.0

songs = sorted([f for f in os.listdir(SONGS_DIR) if f.endswith(('.mp3', '.wav', '.m4a', '.aac'))])

for filename in songs:
    song_file  = f'{SONGS_DIR}/{filename}'
    cache_file = song_file + '.beats.json'

    # Şarkı süresi
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', song_file],
        capture_output=True, text=True
    )
    song_dur = float(result.stdout.strip())
    target   = VIDEO_DURATION if song_dur >= VIDEO_DURATION else song_dur

    # Beat tespiti
    y, sr = librosa.load(song_file, duration=target)
    _, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()

    if not beat_times or beat_times[0] > 0.1:
        beat_times = [0.0] + beat_times
    beat_times.append(target)

    # Aralıkları hesapla
    intervals = []
    for i in range(len(beat_times) - 1):
        dur = beat_times[i + 1] - beat_times[i]
        if dur >= 0.1:
            intervals.append(dur)

    # target süresine tamamla
    base = intervals[:]
    while sum(intervals) < target and base:
        for dur in base:
            intervals.append(dur)
            if sum(intervals) >= target:
                break

    total = 0.0
    trimmed = []
    for dur in intervals:
        if total + dur > target:
            remaining = target - total
            if remaining >= 0.1:
                trimmed.append(remaining)
            break
        trimmed.append(dur)
        total += dur
    intervals = trimmed

    with open(cache_file, 'w') as f:
        json.dump(intervals, f)

    print(f'{filename}  {song_dur:.2f}s  →  {len(intervals)} aralık, {sum(intervals):.2f}s')

print('\nTüm cache\'ler oluşturuldu.')
