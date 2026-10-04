#!/usr/bin/env python3
import subprocess, os, random, json
from pathlib import Path

BASE_DIR    = Path(__file__).parent
SPLIT_DIR   = str(BASE_DIR / 'backgraund/split')
OUTPUT_DIR  = str(BASE_DIR / 'output')
QUOTES_FILE = str(BASE_DIR / 'quotes.txt')
SONGS_DIR   = str(BASE_DIR / 'songs')
FONT_PATH   = '/System/Library/Fonts/Supplemental/GillSans.ttc'

MAX_BEAT_INTERVAL = 0.5   # saniye — vuruşlar arası max süre
VIDEO_DURATION    = 12.0  # toplam video süresi

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Quote seç ──────────────────────────────────────────────
with open(QUOTES_FILE, encoding='utf-8') as f:
    quotes = [l.strip() for l in f if l.strip()]
quote = random.choice(quotes)
print(f'Quote: {quote}')

# ── Müzik seç ──────────────────────────────────────────────
songs = [f for f in os.listdir(SONGS_DIR) if f.endswith(('.mp3', '.wav', '.m4a', '.aac'))]
song_file = f'{SONGS_DIR}/{random.choice(songs)}'
print(f'Müzik: {os.path.basename(song_file)}')

# ── Beat cache yükle ───────────────────────────────────────
cache_file = song_file + '.beats.json'
if not os.path.exists(cache_file):
    print(f'HATA: Cache bulunamadı → önce build_cache.py çalıştır')
    exit(1)

with open(cache_file) as f:
    intervals = json.load(f)

# 0.5s'den büyük aralıkları recursive ikiye böl
def split_interval(dur, max_dur=0.65):
    if dur <= max_dur:
        return [dur]
    half = dur / 2
    return split_interval(half, max_dur) + split_interval(half, max_dur)

intervals = [d for interval in intervals for d in split_interval(interval)]

print(f'{len(intervals)} aralık → {sum(intervals):.1f}s')

# ── Klipleri yükle ─────────────────────────────────────────
clips = []
for f in sorted(os.listdir(SPLIT_DIR)):
    if not f.endswith('.mp4'):
        continue
    fp = f'{SPLIT_DIR}/{f}'
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', fp],
        capture_output=True, text=True
    )
    try:
        dur = float(result.stdout.strip())
        clips.append({'file': fp, 'dur': dur})
    except:
        pass

print(f'{len(clips)} klip yüklendi')

# ── Her beat aralığı için klip seç ve kırp ─────────────────
sequence = []  # (file, trim_dur, start)
used = set()

for interval_dur in intervals:
    eligible = [c for c in clips if c['dur'] > interval_dur + 0.05 and c['file'] not in used]
    if not eligible:
        used.clear()
        eligible = [c for c in clips if c['dur'] > interval_dur + 0.05]
    if not eligible:
        eligible = sorted(clips, key=lambda c: c['dur'], reverse=True)[:5]
    clip = random.choice(eligible)
    used.add(clip['file'])
    start = random.uniform(0.05, max(0.05, clip['dur'] - interval_dur - 0.05))
    sequence.append((clip['file'], interval_dur, start))

print(f'{len(sequence)} klip seçildi')

# ── Output numarası belirle ────────────────────────────────
existing_nums = []
for f in os.listdir(OUTPUT_DIR):
    if f.startswith('output_') and f.endswith('.mp4'):
        try:
            existing_nums.append(int(f.replace('output_', '').replace('.mp4', '')))
        except:
            pass
num = max(existing_nums) + 1 if existing_nums else 1
output_path = f'{OUTPUT_DIR}/output_{num:03d}.mp4'

# ── FFmpeg filter_complex ──────────────────────────────────
inputs = []
for filepath, dur, start in sequence:
    inputs += ['-i', filepath]

# trim filter → frame-accurate seek (B-frame karışması olmaz)
filter_parts = ''
for i, (_fp, dur, start) in enumerate(sequence):
    filter_parts += f'[{i}:v]trim=start={start:.4f}:duration={dur:.4f},setpts=PTS-STARTPTS[v{i}];'

concat_inputs = ''.join(f'[v{i}]' for i in range(len(sequence)))

escaped = quote.replace("'", "\u2019")
drawtext = (
    f"drawtext=font='Gill Sans Light':"
    f"text='{escaped}':"
    f"fontcolor=white:fontsize=30:borderw=1:bordercolor=black:"
    f"x=(w-text_w)/2:y=(h-text_h)/2"
)

filter_complex = (
    filter_parts
    + f'{concat_inputs}concat=n={len(sequence)}:v=1:a=0[concat];'
    + f'[concat]{drawtext}[outv]'
)

# Klip sınırlarına keyframe zorla (B-frame karışmasını önler)
cumulative = 0.0
kf_times = []
for _, dur, _ in sequence[:-1]:
    cumulative += dur
    kf_times.append(f'{cumulative:.4f}')
force_kf = ','.join(kf_times) if kf_times else '0'

cmd = ['ffmpeg', '-y'] + inputs + [
    '-filter_complex', filter_complex,
    '-map', '[outv]',
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
    '-bf', '0',
    '-force_key_frames', force_kf,
    '-shortest',
    output_path
]

print('Video render ediliyor...')
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print('HATA:', result.stderr[-1000:])
    exit(1)

# ── Müzik ekle ─────────────────────────────────────────────
video_dur = sum(dur for _, dur, _s in sequence)
final_path = output_path.replace('.mp4', '_music.mp4')

cmd2 = [
    'ffmpeg', '-y',
    '-i', output_path,
    '-i', song_file,
    '-map', '0:v', '-map', '1:a',
    '-c:v', 'copy', '-c:a', 'aac', '-shortest',
    final_path
]

result2 = subprocess.run(cmd2, capture_output=True, text=True)
if result2.returncode != 0:
    print('MÜZİK HATA:', result2.stderr[-500:])
else:
    os.remove(output_path)
    os.rename(final_path, output_path)
    print(f'\nTamamlandi: {output_path} ({video_dur:.2f}s)')
