"""
One-shot pipeline to refresh the IPTV channel list from a new M3U playlist.

Meant to be run whenever you get a fresh M3U file from your IPTV provider
(e.g. once a day). It does everything in one go:

  1. Parses the M3U file and categorizes each channel.
  2. Rewrites js/live_channels.js (the source-of-truth JS copy).
  3. Rewrites data/channels.json (what the app actually fetches at runtime).
  4. Bumps the Service Worker cache version in sw.js, so browsers that
     already visited the site pick up the new channel list instead of
     serving the old cached one forever.

Run with:
    python tools/update_channels_from_m3u.py
        (auto-downloads the M3U using tools/iptv_credentials.json if it
        exists, otherwise falls back to the local M3U file below)

    python tools/update_channels_from_m3u.py --m3u "C:\\path\\to\\new_playlist.m3u"
        (uses a specific local M3U file instead)

    python tools/update_channels_from_m3u.py --url "http://host:port/get.php?..."
        (downloads the M3U from any URL instead)

Credentials file (tools/iptv_credentials.json, NOT committed to git):
    {
      "host": "ugeen.live",
      "port": 8080,
      "username": "...",
      "password": "..."
    }
"""
import argparse
import json
import os
import re
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_M3U_PATH = os.path.join(BASE_DIR, 'tv_channels_Ugeen_VIPg6SEke (3).m3u')
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'tools', 'iptv_credentials.json')
JS_PATH = os.path.join(BASE_DIR, 'js', 'live_channels.js')
JSON_PATH = os.path.join(BASE_DIR, 'data', 'channels.json')
SW_PATH = os.path.join(BASE_DIR, 'sw.js')

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)

CATEGORY_RULES = [
    ('sport', ['bein', 'sport', 'ssc', 'koora', 'futbol', 'football', '⚽', 'max ', 'dazn', 'espn', 'sky sport', 'euro sport', 'nba', 'nfl', 'ufc', 'wwe', 'tennis', 'golf', 'f1', 'formula', 'liga', 'كورة', 'رياض']),
    ('news', ['news', 'jazeera', 'arabiya', 'bbc', 'cnn', 'cnbc', 'france 24', 'sky news', 'reuters', 'bloomberg', 'اخبار', 'العربية', 'الجزيرة', 'mbc action']),
    ('religious', ['quran', 'quraan', 'qraan', 'islam', 'majd', 'resala', 'nas', 'iqraa', 'makkah', 'sunna', 'hadeth', 'religious', 'قرءان', 'قرآن', 'اسلام', 'دين', 'راديو', 'istiqama']),
    ('kids', ['kids', 'kid', 'cartoon', 'spacetoon', 'nick', 'disney jr', 'baby', 'junior', 'أطفال', 'طفل', 'cn j', 'cnej']),
    ('entertainment', ['mbc', 'rotana', 'drama', 'movie', 'cinema', 'series', 'entertainment', 'tv ', ' hd', 'fhd', '4k']),
]

CATEGORY_EMOJI = {
    'sport': '⚽',
    'news': '📰',
    'entertainment': '🌟',
    'religious': '🕌',
    'kids': '🧸',
    'other': '📺',
}


def is_separator(name):
    if '---' in name or '★★' in name or '●•' in name:
        return True
    if name.strip().lower() in ('ugeen promo', 'test-grey'):
        return True
    return False


def detect_category(name):
    lower = name.lower()
    for cat, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw in lower:
                return cat
    return 'other'


def to_hls_url(url):
    if '.m3u8' in url:
        return url
    match = re.match(r'^(https?://[^/]+)/([^/]+)/([^/]+)/(\d+)$', url.strip())
    if match:
        base, user, pwd, stream_id = match.groups()
        return f'{base}/live/{user}/{pwd}/{stream_id}.m3u8'
    return url


def parse_m3u(path):
    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    channels = []
    idx = 0
    for i, line in enumerate(lines):
        if not line.startswith('#EXTINF'):
            continue

        title_match = re.search(r',\s*(.*)$', line)
        title = title_match.group(1).strip() if title_match else 'Unknown'
        if is_separator(title):
            continue

        url = lines[i + 1] if i + 1 < len(lines) else ''
        if not url.startswith('http'):
            continue

        category = detect_category(title)
        idx += 1
        channels.append({
            'id': f'iptv_{idx}',
            'name': title,
            'category': category,
            'emoji': CATEGORY_EMOJI.get(category, '📺'),
            'url': to_hls_url(url),
            'rawUrl': url,
        })

    return channels


def write_js(channels):
    with open(JS_PATH, 'w', encoding='utf-8') as out:
        out.write('/* Auto-generated from M3U playlist — do not edit manually.\n')
        out.write('   NOTE: no longer loaded by index.html directly - see js/data.js header\n')
        out.write('   and js/data-loader.js / data/channels.json. */\n')
        out.write('const channels = ')
        json.dump(channels, out, ensure_ascii=False, indent=2)
        out.write(';\n')
    print(f'Wrote {JS_PATH} ({len(channels)} channels)')


def write_json(channels):
    with open(JSON_PATH, 'w', encoding='utf-8') as out:
        json.dump(channels, out, ensure_ascii=False, separators=(',', ':'))
    print(f'Wrote {JSON_PATH} ({len(channels)} channels)')


def bump_service_worker_cache():
    with open(SW_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    match = re.search(r"const CACHE_NAME = 'mo-v(\d+)';", content)
    if not match:
        print(f'WARNING: could not find CACHE_NAME version in {SW_PATH}; skipping cache bump.')
        return

    new_version = int(match.group(1)) + 1
    content = re.sub(r"mo-v\d+'", f"mo-v{new_version}'", content)
    content = re.sub(r"mo-static-v\d+'", f"mo-static-v{new_version}'", content)
    content = re.sub(r"mo-dynamic-v\d+'", f"mo-dynamic-v{new_version}'", content)

    with open(SW_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Bumped Service Worker cache version to v{new_version} in {SW_PATH}')


def load_credentials():
    """Load Xtream Codes panel credentials from tools/iptv_credentials.json,
    if that file exists. This file is gitignored on purpose - never commit
    real credentials."""
    if not os.path.isfile(CREDENTIALS_PATH):
        return None
    with open(CREDENTIALS_PATH, 'r', encoding='utf-8') as f:
        creds = json.load(f)
    required = ('host', 'port', 'username', 'password')
    if not all(k in creds for k in required):
        print(f'WARNING: {CREDENTIALS_PATH} is missing one of {required}; ignoring it.')
        return None
    return creds


def build_xtream_m3u_url(creds):
    return (f"http://{creds['host']}:{creds['port']}/get.php?"
            f"username={creds['username']}&password={creds['password']}"
            f"&type=m3u_plus&output=ts")


def download_m3u(url, dest_path):
    print('Downloading M3U playlist...')
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    with open(dest_path, 'wb') as f:
        f.write(data)
    print(f'Saved downloaded playlist to {dest_path} ({len(data)} bytes)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--m3u', default=None,
                         help='path to a local M3U file to use directly (skips downloading)')
    parser.add_argument('--url', default=None,
                         help='URL to download the M3U playlist from')
    args = parser.parse_args()

    m3u_path = args.m3u

    if not m3u_path:
        url = args.url
        if not url:
            creds = load_credentials()
            if creds:
                url = build_xtream_m3u_url(creds)
                print(f"Using saved credentials for {creds['host']}:{creds['port']} "
                      f"(user: {creds['username']})")
        if url:
            download_m3u(url, DEFAULT_M3U_PATH)
            m3u_path = DEFAULT_M3U_PATH
        else:
            m3u_path = DEFAULT_M3U_PATH
            print(f'No --url given and no {CREDENTIALS_PATH} found; '
                  f'using existing local file: {m3u_path}')

    if not os.path.isfile(m3u_path):
        print(f'M3U file not found: {m3u_path}')
        raise SystemExit(1)

    channels = parse_m3u(m3u_path)
    if not channels:
        print('No channels were parsed from the M3U file - aborting without '
              'overwriting the existing channel list.')
        raise SystemExit(1)

    write_js(channels)
    write_json(channels)
    bump_service_worker_cache()

    cats = {}
    for ch in channels:
        cats[ch['category']] = cats.get(ch['category'], 0) + 1

    print(f'\nDone: {len(channels)} channels total')
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f'  {cat}: {count}')

    print('\nNext step: refresh the site in your browser (a hard refresh, '
          'Ctrl+F5, guarantees you see the new list immediately).')


if __name__ == '__main__':
    main()
