#!/bin/bash
set -e

# ── Sistem bağımlılıkları (Ubuntu/Debian) ──────────────────
sudo apt-get update -qq
sudo apt-get install -y ffmpeg python3 python3-pip

# ── Python paketleri ───────────────────────────────────────
pip3 install -r requirements.txt --break-system-packages

# ── Klasörleri oluştur ─────────────────────────────────────
mkdir -p songs output backgraund/split

echo ""
echo "Kurulum tamamlandı."
echo ""
echo "Sıradaki adımlar:"
echo "  1. songs/      → şarkıları koy (mp3/wav/m4a/aac)"
echo "  2. backgraund/split/ → split klipleri koy (mp4)"
echo "  3. python3 build_cache.py   → beat cache oluştur"
echo "  4. python3 make_video_beat.py → video üret"
