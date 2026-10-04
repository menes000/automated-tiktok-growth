#!/usr/bin/env python3
"""
TikTok otomatik video yükleyici.

İlk çalıştırmada tarayıcı açılır, TikTok'ta giriş yaparsın → token kaydedilir.
Sonraki çalıştırmalarda direkt yükler.

Kullanım:
  python3 tiktok_upload.py                  # output/ klasöründeki en son videoyu yükle
  python3 tiktok_upload.py output/video.mp4 # belirli bir videoyu yükle
"""

import os, sys, json, time, secrets, hashlib, webbrowser, urllib.parse
import urllib.request, http.server, threading
from pathlib import Path

# ── Ayarlar ────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
ENV_FILE     = BASE_DIR / '.env'
TOKEN_FILE   = BASE_DIR / '.tiktok_token.json'
OUTPUT_DIR   = BASE_DIR / 'output'

AUTH_URL     = 'https://www.tiktok.com/v2/auth/authorize/'
TOKEN_URL    = 'https://open.tiktokapis.com/v2/oauth/token/'
UPLOAD_INIT  = 'https://open.tiktokapis.com/v2/post/publish/inbox/video/init/'
STATUS_URL   = 'https://open.tiktokapis.com/v2/post/publish/status/fetch/'

# ── .env yükle ─────────────────────────────────────────────
def load_env():
    if not ENV_FILE.exists():
        print('HATA: .env dosyası bulunamadı')
        sys.exit(1)
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

load_env()
CLIENT_KEY    = os.environ['TIKTOK_CLIENT_KEY']
CLIENT_SECRET = os.environ['TIKTOK_CLIENT_SECRET']
REDIRECT_URI  = os.environ['TIKTOK_REDIRECT_URI']

# ── HTTP isteği yardımcısı ─────────────────────────────────
def http_post(url, data=None, headers=None, raw_body=None):
    if raw_body:
        body = raw_body
    else:
        body = json.dumps(data).encode()
        headers = headers or {}
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=body, headers=headers or {}, method='POST')
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print('HTTP Hata:', e.code, e.read().decode())
        raise

# ── Token yönetimi ──────────────────────────────────────────
def load_token():
    if TOKEN_FILE.exists():
        t = json.loads(TOKEN_FILE.read_text())
        if t.get('expires_at', 0) > time.time() + 60:
            return t
        # Refresh dene
        if t.get('refresh_token'):
            print('Token süresi dolmuş, yenileniyor...')
            try:
                return refresh_token(t['refresh_token'])
            except:
                pass
    return None

def save_token(data):
    data['expires_at'] = time.time() + data.get('expires_in', 86400)
    TOKEN_FILE.write_text(json.dumps(data, indent=2))
    print('Token kaydedildi.')

def refresh_token(refresh_tok):
    resp = http_post(TOKEN_URL, raw_body=urllib.parse.urlencode({
        'client_key':     CLIENT_KEY,
        'client_secret':  CLIENT_SECRET,
        'grant_type':     'refresh_token',
        'refresh_token':  refresh_tok,
    }).encode(), headers={'Content-Type': 'application/x-www-form-urlencoded'})
    save_token(resp)
    return resp

# ── OAuth flow ──────────────────────────────────────────────
def get_token_via_browser():
    print('\nTarayıcı açılıyor, TikTok hesabınla giriş yap ve izin ver...\n')
    state = secrets.token_urlsafe(16)
    code_verifier  = secrets.token_urlsafe(64)
    code_challenge = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = __import__('base64').urlsafe_b64encode(code_challenge).rstrip(b'=').decode()

    # Verifier'ı kaydet — token exchange'de lazım
    (BASE_DIR / '.pkce_verifier').write_text(code_verifier)

    params = {
        'client_key':             CLIENT_KEY,
        'response_type':          'code',
        'scope':                  'user.info.basic,video.upload',
        'redirect_uri':           REDIRECT_URI,
        'state':                  state,
        'code_challenge':         code_challenge,
        'code_challenge_method':  'S256',
    }
    url = AUTH_URL + '?' + urllib.parse.urlencode(params)
    print(f'\nŞu URL\'yi tarayıcıda aç:\n\n{url}\n')
    webbrowser.open(url)

    print('TikTok izin verdikten sonra yönlendirileceksin.')
    print('Tarayıcının adres çubuğundaki tam URL\'yi kopyalayıp buraya yapıştır:')
    redirected_url = input('URL: ').strip()

    parsed = urllib.parse.urlparse(redirected_url)
    qs = urllib.parse.parse_qs(parsed.query)
    if 'code' not in qs:
        print('HATA: URL\'de code bulunamadı')
        sys.exit(1)
    auth_code = qs['code'][0]

    # Code → token
    verifier_file = BASE_DIR / '.pkce_verifier'
    saved_verifier = verifier_file.read_text().strip() if verifier_file.exists() else code_verifier
    resp = http_post(TOKEN_URL, raw_body=urllib.parse.urlencode({
        'client_key':     CLIENT_KEY,
        'client_secret':  CLIENT_SECRET,
        'code':           auth_code,
        'grant_type':     'authorization_code',
        'redirect_uri':   REDIRECT_URI,
        'code_verifier':  saved_verifier,
    }).encode(), headers={'Content-Type': 'application/x-www-form-urlencoded'})

    save_token(resp)
    return resp

# ── Video yükle ────────────────────────────────────────────
def upload_video(video_path: Path, token: str):
    size = video_path.stat().st_size
    print(f'Yükleniyor: {video_path.name} ({size / 1024 / 1024:.1f} MB)')

    # 1. Init (inbox/draft upload)
    init_resp = http_post(UPLOAD_INIT,
        data={
            'source_info': {
                'source':            'FILE_UPLOAD',
                'video_size':         size,
                'chunk_size':         size,
                'total_chunk_count':  1,
            }
        },
        headers={'Authorization': f'Bearer {token}'}
    )

    if init_resp.get('error', {}).get('code', 'ok') != 'ok':
        print('Init hatası:', init_resp)
        sys.exit(1)

    upload_url = init_resp['data']['upload_url']
    publish_id = init_resp['data']['publish_id']
    print(f'Upload URL alındı, publish_id: {publish_id}')

    # 2. Upload
    with open(video_path, 'rb') as f:
        video_data = f.read()

    upload_req = urllib.request.Request(
        upload_url,
        data=video_data,
        method='PUT',
        headers={
            'Content-Type':  'video/mp4',
            'Content-Range': f'bytes 0-{size-1}/{size}',
            'Content-Length': str(size),
        }
    )
    with urllib.request.urlopen(upload_req) as r:
        print(f'Upload yanıtı: {r.status}')

    # 3. Durum takibi
    print('İşleniyor', end='', flush=True)
    for _ in range(30):
        time.sleep(5)
        status_resp = http_post(STATUS_URL,
            data={'publish_id': publish_id},
            headers={'Authorization': f'Bearer {token}'}
        )
        status = status_resp.get('data', {}).get('status', '')
        print(f' [{status}]', end='', flush=True)
        if status in ('PUBLISH_COMPLETE', 'SEND_TO_USER_INBOX'):
            print(f'\nVideo TikTok kutuna gönderildi! Uygulamadan publish edebilirsin.')
            return
        if 'FAIL' in status or 'ERROR' in status:
            print(f'\nHATA: {status_resp}')
            sys.exit(1)

    print('\nZaman aşımı — TikTok panelinden kontrol et')

# ── Ana akış ───────────────────────────────────────────────
def main():
    # Video seç
    if len(sys.argv) > 1:
        video_path = Path(sys.argv[1])
    else:
        videos = sorted(OUTPUT_DIR.glob('output_*.mp4'))
        if not videos:
            print('HATA: output/ klasöründe video yok')
            sys.exit(1)
        video_path = videos[-1]
        print(f'En son video: {video_path.name}')

    if not video_path.exists():
        print(f'HATA: {video_path} bulunamadı')
        sys.exit(1)

    # Token al
    token_data = load_token()
    if not token_data:
        token_data = get_token_via_browser()

    upload_video(video_path, token_data['access_token'])

if __name__ == '__main__':
    main()
