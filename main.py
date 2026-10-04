#!/usr/bin/env python3
"""
Tam pipeline: video oluştur → TikTok'a yükle
Kullanım: python3 main.py
"""

import subprocess, sys
from pathlib import Path

BASE_DIR = Path(__file__).parent

def run(script):
    result = subprocess.run([sys.executable, BASE_DIR / script], check=False)
    if result.returncode != 0:
        print(f'\nHATA: {script} başarısız oldu')
        sys.exit(1)

print('=' * 40)
print('1/2  Video oluşturuluyor...')
print('=' * 40)
run('make_video_beat.py')

print()
print('=' * 40)
print('2/2  TikTok\'a yükleniyor...')
print('=' * 40)
run('tiktok_upload.py')

print()
print('Pipeline tamamlandı.')
