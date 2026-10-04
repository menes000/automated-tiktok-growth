#!/usr/bin/env python3
import subprocess, os, random, textwrap
from pathlib import Path

BASE_DIR   = Path(__file__).parent
SPLIT_DIR  = str(BASE_DIR / 'backgraund/split')
OUTPUT_DIR = str(BASE_DIR / 'output')
QUOTES_FILE = str(BASE_DIR / 'quotes.txt')
SONGS_DIR  = str(BASE_DIR / 'songs')
FONT_PATH  = '/System/Library/Fonts/Supplemental/GillSans.ttc'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Quote seç
with open(QUOTES_FILE, encoding='utf-8') as f:
    quotes = [l.strip() for l in f if l.strip()]
quote = random.choice(quotes)
print(f'Seçilen quote: {quote}')

# Faz sınırları (kümülatif saniye)
PHASE1_END = 3.0   # 0-3s: sadece < 0.6s klipler
PHASE2_END = 6.0   # 3-6s: sadece < 1.0s klipler
TARGET     = 12.0  # 6-12s: hepsi karışık

# Klipleri yükle
clips = []
for f in sorted(os.listdir(SPLIT_DIR)):
    if not f.endswith('.mp4'):
        continue
    fp = f'{SPLIT_DIR}/{f}'
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', fp],
        capture_output=True, text=True
    )
    dur = float(result.stdout.strip())
    clips.append({'file': fp, 'name': f, 'dur': dur})

random.shuffle(clips)

used = set()
sequence = []
total = 0.0

# Faz 1: 0-3s → sadece < 0.6s
pool1 = [c for c in clips if c['dur'] < 0.6]
random.shuffle(pool1)
for c in pool1:
    if total >= PHASE1_END:
        break
    sequence.append(c)
    used.add(c['name'])
    total += c['dur']

# Faz 2: 3-6s → sadece < 1.0s (henüz kullanılmamış)
pool2 = [c for c in clips if c['dur'] < 1.0 and c['name'] not in used]
random.shuffle(pool2)
for c in pool2:
    if total >= PHASE2_END:
        break
    sequence.append(c)
    used.add(c['name'])
    total += c['dur']

# Faz 3: 6-12s → hepsi karışık (henüz kullanılmamış)
pool3 = [c for c in clips if c['name'] not in used]
random.shuffle(pool3)
for c in pool3:
    if total >= TARGET:
        break
    sequence.append(c)
    used.add(c['name'])
    total += c['dur']

print(f'Toplam {len(sequence)} klip seçildi → {total:.2f}s')
print()
for i, c in enumerate(sequence, 1):
    print(f'  {i:02d}. {c["name"]} ({c["dur"]:.2f}s)')

# Mevcut en yüksek numarayı bul, bir artır
existing_nums = []
for f in os.listdir(OUTPUT_DIR):
    if f.startswith('output_') and f.endswith('.mp4'):
        try:
            existing_nums.append(int(f.replace('output_', '').replace('.mp4', '')))
        except:
            pass
num = max(existing_nums) + 1 if existing_nums else 1
output_path = f'{OUTPUT_DIR}/output_{num:03d}.mp4'

# ffmpeg concat filter ile re-encode (donma sorunu olmaz)
inputs = []
for c in sequence:
    inputs += ['-i', c['file']]

filter_parts = ''.join(f'[{i}:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=30[v{i}];' for i in range(len(sequence)))
concat_inputs = ''.join(f'[v{i}]' for i in range(len(sequence)))

escaped = quote.replace("'", "\u2019")

drawtext = (
    f"drawtext=font='Gill Sans Light':"
    f"text='{escaped}':"
    f"fontcolor=white:fontsize=30:borderw=1:bordercolor=black:"
    f"x=(w-text_w)/2:y=(h-text_h)/2"
)

filter_complex = filter_parts + f'{concat_inputs}concat=n={len(sequence)}:v=1:a=0[concat];[concat]{drawtext}[outv]'

cmd = ['ffmpeg', '-y'] + inputs + [
    '-filter_complex', filter_complex,
    '-map', '[outv]',
    '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
    output_path
]

result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print('HATA:', result.stderr[-500:])
    exit(1)

# Şarkı seç
songs = [f for f in os.listdir(SONGS_DIR) if f.endswith(('.mp3', '.wav', '.m4a', '.aac'))]
song_file = f'{SONGS_DIR}/{random.choice(songs)}'
song_dur_result = subprocess.run(
    ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', '-of', 'csv=p=0', song_file],
    capture_output=True, text=True
)
song_dur = float(song_dur_result.stdout.strip())
print(f'Seçilen şarkı: {os.path.basename(song_file)} ({song_dur:.2f}s)')

# Şarkı kısaysa → videoyu şarkı süresine kırp, şarkı uzunsa → şarkıyı video süresine kırp
final_path = output_path.replace('.mp4', '_music.mp4')
video_dur = total

if song_dur < video_dur:
    # Video uzun → videoyu şarkı süresine kırp
    final_dur = song_dur
    print(f'Şarkı kısa → video {final_dur:.2f}s\'e kırpılıyor')
    cmd2 = [
        'ffmpeg', '-y',
        '-i', output_path,
        '-i', song_file,
        '-t', str(final_dur),
        '-map', '0:v', '-map', '1:a',
        '-c:v', 'copy', '-c:a', 'aac', '-shortest',
        final_path
    ]
else:
    # Şarkı uzun → şarkıyı video süresine kırp
    final_dur = video_dur
    print(f'Şarkı uzun → şarkı {final_dur:.2f}s\'e kırpılıyor')
    cmd2 = [
        'ffmpeg', '-y',
        '-i', output_path,
        '-i', song_file,
        '-t', str(final_dur),
        '-map', '0:v', '-map', '1:a',
        '-c:v', 'copy', '-c:a', 'aac', '-shortest',
        final_path
    ]

result2 = subprocess.run(cmd2, capture_output=True, text=True)
if result2.returncode != 0:
    print('MÜZİK HATA:', result2.stderr[-500:])
else:
    os.remove(output_path)  # müziksiz versiyonu sil
    os.rename(final_path, output_path)
    print(f'Video oluşturuldu: {output_path} ({final_dur:.2f}s)')
