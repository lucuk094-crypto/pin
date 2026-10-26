"""
GlassPin — Vercel Serverless Function (catch-all /api/*)
Mandiri tanpa dependency eksternal (Python stdlib).
Endpoint: /api/feed, /api/search, /api/comments, /api/download
"""
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

UA = "GlassPin/1.0 (glassmorphism demo app)"

# ---------------------------------------------------------------- cache & comments
_cache = {}
CACHE_TTL = 180
_lock = threading.Lock()

def _comments_path():
    # /tmp writable di Vercel; folder data untuk lokal
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "comments.json")
    try:
        d = os.path.dirname(local)
        os.makedirs(d, exist_ok=True)
        if os.access(d, os.W_OK):
            return local
    except Exception:
        pass
    return "/tmp/glasspin_comments.json"

COMMENTS_FILE = _comments_path()

def load_comments():
    try:
        with open(COMMENTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_comments(data):
    try:
        with open(COMMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ---------------------------------------------------------------- HTTP helpers

def fast_thumb(url):
    """Thumbnail cepat: kecilkan ukuran Flickr langsung; fallback URL asli."""
    if not url:
        return url
    # Flickr: _b (1024) -> _c (800) lebih ringan untuk grid
    m = re.match(r"(https://live\.staticflickr\.com/.+?)_[a-z]\.jpg$", url)
    if m:
        return m.group(1) + "_c.jpg"
    return url

def http_get_json(url, headers=None, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

# ---------------------------------------------------------------- providers
def search_openverse(q, page, page_size, media_type):
    params = urllib.parse.urlencode({"q": q, "page": page, "page_size": min(page_size, 20), "mature": "false"})
    d = http_get_json(f"https://api.openverse.org/v1/images/?{params}", timeout=8)
    items = []
    for r in d.get("results", []):
        if media_type == "video":
            continue
        items.append({
            "id": f"ov-{r.get('id')}",
            "title": (r.get("title") or "Tanpa judul").strip(),
            "description": (r.get("title") or "").strip(),
            "media_type": "image",
            "thumbnail": fast_thumb(r.get("url")),
            "full": r.get("url"),
            "width": r.get("width"), "height": r.get("height"),
            "creator": {"name": r.get("creator") or "Tidak diketahui", "url": r.get("creator_url")},
            "license": f"CC {(r.get('license') or '').upper()} {r.get('license_version') or ''}".strip(),
            "source": {"name": (r.get("source") or "Openverse").title(), "url": r.get("foreign_landing_url")},
            "provider": "openverse",
            "tags": [t.get("name") for t in (r.get("tags") or [])][:8],
        })
    return items, d.get("result_count")

def search_wikimedia(q, page, page_size, media_type):
    limit = min(page_size, 20)
    offset = (page - 1) * limit
    gsrsearch = f"filetype:{'video' if media_type == 'video' else 'bitmap'} {q}"
    params = urllib.parse.urlencode({
        "action": "query", "generator": "search", "gsrsearch": gsrsearch,
        "gsrnamespace": 6, "gsrlimit": limit, "gsroffset": offset,
        "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": 800, "format": "json", "formatversion": 2,
    })
    d = http_get_json(f"https://commons.wikimedia.org/w/api.php?{params}", timeout=8)
    items = []
    for p in (d.get("query", {}).get("pages") or []):
        ii = (p.get("imageinfo") or [{}])[0]
        mime = ii.get("mime", "")
        is_video = mime.startswith("video")
        if media_type == "video" and not is_video:
            continue
        if media_type == "image" and is_video:
            continue
        if media_type == "all" and not (mime.startswith("image") or is_video):
            continue
        em = ii.get("extmetadata") or {}
        def mv(k):
            return re.sub(r"<[^>]+>", "", (em.get(k) or {}).get("value", "")).strip()
        items.append({
            "id": f"wm-{p.get('pageid')}",
            "title": re.sub(r"^File:|\.\w+$", "", p.get("title", ""))[:120] or "Tanpa judul",
            "description": mv("ImageDescription")[:300],
            "media_type": "video" if is_video else "image",
            "thumbnail": ii.get("thumburl") or ii.get("url"),
            "full": ii.get("url"),
            "width": ii.get("width"), "height": ii.get("height"),
            "creator": {"name": mv("Artist")[:80] or "Tidak diketahui", "url": None},
            "license": mv("LicenseShortName") or "Lihat sumber",
            "source": {"name": "Wikimedia Commons", "url": ii.get("descriptionurl")},
            "provider": "wikimedia",
            "tags": [],
        })
    return items, None

def search_pexels(q, page, page_size, media_type, key):
    headers = {"Authorization": key}
    items, total = [], None
    if media_type in ("all", "image"):
        params = urllib.parse.urlencode({"query": q, "per_page": min(page_size, 20), "page": page})
        d = http_get_json(f"https://api.pexels.com/v1/search?{params}", headers=headers, timeout=12)
        total = d.get("total_results")
        for r in d.get("photos", []):
            items.append({
                "id": f"px-{r.get('id')}",
                "title": (r.get("alt") or f"Foto oleh {r.get('photographer','')}").strip(),
                "description": (r.get("alt") or "").strip(),
                "media_type": "image",
                "thumbnail": (r.get("src") or {}).get("large") or (r.get("src") or {}).get("medium"),
                "full": (r.get("src") or {}).get("original"),
                "width": r.get("width"), "height": r.get("height"),
                "creator": {"name": r.get("photographer") or "Tidak diketahui", "url": r.get("photographer_url")},
                "license": "Pexels License (gratis)",
                "source": {"name": "Pexels", "url": r.get("url")},
                "provider": "pexels", "tags": [],
            })
    if media_type in ("all", "video"):
        params = urllib.parse.urlencode({"query": q, "per_page": min(page_size, 20), "page": page})
        d = http_get_json(f"https://api.pexels.com/videos/search?{params}", headers=headers, timeout=12)
        for r in d.get("videos", []):
            files = sorted(r.get("video_files") or [], key=lambda f: f.get("width") or 0)
            if not files:
                continue
            best = files[-1]
            items.append({
                "id": f"pxv-{r.get('id')}",
                "title": "Video Pexels",
                "description": "",
                "media_type": "video",
                "thumbnail": r.get("image"),
                "full": best.get("link"),
                "width": best.get("width"), "height": best.get("height"),
                "creator": {"name": ((r.get("user") or {}).get("name")) or "Tidak diketahui",
                            "url": (r.get("user") or {}).get("url")},
                "license": "Pexels License (gratis)",
                "source": {"name": "Pexels", "url": r.get("url")},
                "provider": "pexels", "tags": [], "duration": r.get("duration"),
            })
    return items, total

def search_pixabay(q, page, page_size, media_type, key):
    items, total = [], None
    if media_type in ("all", "image"):
        params = urllib.parse.urlencode({"key": key, "q": q, "page": page, "per_page": min(page_size, 20),
                                        "safesearch": "true", "lang": "id"})
        d = http_get_json(f"https://pixabay.com/api/?{params}", timeout=12)
        total = d.get("totalHits")
        for r in d.get("hits", []):
            items.append({
                "id": f"pb-{r.get('id')}",
                "title": (r.get("tags") or "Gambar Pixabay").title()[:120],
                "description": f"Tags: {r.get('tags','')}",
                "media_type": "image",
                "thumbnail": r.get("webformatURL") or r.get("previewURL"),
                "full": r.get("largeImageURL") or r.get("webformatURL"),
                "width": r.get("imageWidth"), "height": r.get("imageHeight"),
                "creator": {"name": r.get("user") or "Tidak diketahui", "url": None},
                "license": "Pixabay License (gratis)",
                "source": {"name": "Pixabay", "url": r.get("pageURL")},
                "provider": "pixabay",
                "tags": [t.strip() for t in (r.get("tags") or "").split(",")][:8],
            })
    if media_type in ("all", "video"):
        params = urllib.parse.urlencode({"key": key, "q": q, "page": page, "per_page": min(page_size, 20),
                                        "safesearch": "true", "lang": "id"})
        d = http_get_json(f"https://pixabay.com/api/videos/?{params}", timeout=12)
        for r in d.get("hits", []):
            v = ((r.get("videos") or {}).get("medium") or (r.get("videos") or {}).get("small") or {})
            if not v.get("url"):
                continue
            items.append({
                "id": f"pbv-{r.get('id')}",
                "title": (r.get("tags") or "Video Pixabay").title()[:120],
                "description": f"Tags: {r.get('tags','')}",
                "media_type": "video",
                "thumbnail": f"https://i.vimeocdn.com/video/{r.get('picture_id')}_640x360.jpg" if r.get("picture_id") else None,
                "full": v.get("url"),
                "width": v.get("width"), "height": v.get("height"),
                "creator": {"name": r.get("user") or "Tidak diketahui", "url": None},
                "license": "Pixabay License (gratis)",
                "source": {"name": "Pixabay", "url": r.get("pageURL")},
                "provider": "pixabay",
                "tags": [t.strip() for t in (r.get("tags") or "").split(",")][:8],
                "duration": r.get("duration"),
            })
    return items, total

# ---------------------------------------------------------------- ekspansi kueri
ID_EN_PHRASE = {
    "wallpaper keren": "cool aesthetic wallpaper", "wallpaper hd": "hd wallpaper",
    "alam indah": "beautiful nature", "laut biru": "blue ocean", "pantai sunset": "beach sunset",
    "seni abstrak": "abstract art", "arsitektur modern": "modern architecture",
    "makanan lezat": "delicious food", "desain interior": "interior design",
    "ruang angkasa": "outer space", "hewan lucu": "cute animals", "mobil keren": "cool cars",
    "bunga indah": "beautiful flowers", "pemandangan alam": "nature landscape",
    "gunung indah": "beautiful mountains",
}
ID_EN_WORD = {
    "alam": "nature", "laut": "ocean", "gunung": "mountain", "bunga": "flowers",
    "kucing": "cat", "anjing": "dog", "hewan": "animals", "makanan": "food",
    "pantai": "beach", "kota": "city", "hutan": "forest", "bintang": "stars",
    "mobil": "car", "motor": "motorcycle", "baju": "fashion", "rumah": "house",
    "seni": "art", "arsitektur": "architecture", "pemandangan": "landscape",
    "awan": "clouds", "langit": "sky", "jalanan": "street", "malam": "night",
    "pagi": "morning", "taman": "garden", "danau": "lake", "sungai": "river",
    "air terjun": "waterfall", "sawah": "rice field", "teknologi": "technology",
    "musik": "music", "keren": "cool", "indah": "beautiful", "cantik": "beautiful",
    "gelap": "dark", "terang": "bright", "tradisional": "traditional",
    "pahlawan": "hero", "sejarah": "history", "gunung berapi": "volcano",
    "burung": "birds", "ikan": "fish", "bunga matahari": "sunflower", "mawar": "rose",
    "wanita": "woman", "pria": "man", "anak": "children", "wajah": "face",
    "minimalis": "minimalist",
}

def expand_query(q):
    ql = (q or "").strip()
    variants = [ql]
    low = ql.lower()
    if low in ID_EN_PHRASE:
        variants.append(ID_EN_PHRASE[low])
    en_q = " ".join(ID_EN_WORD.get(w, w) for w in low.split()).strip()
    if en_q and en_q.lower() != low:
        variants.append(en_q)
    out, seen = [], set()
    for v in variants:
        k = v.lower()
        if k not in seen:
            seen.add(k)
            out.append(v)
    return out[:2]

def do_search(q, page=1, page_size=20, media_type="all", pexels_key=None, pixabay_key=None):
    cache_key = f"s|{q}|{page}|{media_type}|{bool(pexels_key)}|{bool(pixabay_key)}"
    with _lock:
        hit = _cache.get(cache_key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]

    variants = expand_query(q)
    jobs = []
    per = max(page_size // len(variants), 8)
    for v in variants:
        jobs.append((f"openverse:{v}", lambda v=v: search_openverse(v, page, per, media_type)))
        jobs.append((f"wikimedia:{v}", lambda v=v: search_wikimedia(v, page, per, media_type)))
        if pexels_key:
            jobs.append((f"pexels:{v}", lambda v=v: search_pexels(v, page, per, media_type, pexels_key)))
        if pixabay_key:
            jobs.append((f"pixabay:{v}", lambda v=v: search_pixabay(v, page, per, media_type, pixabay_key)))

    results = [None] * len(jobs)
    errors = []

    def run(i, label, fn):
        try:
            results[i] = fn()
        except Exception as e:
            errors.append(f"{label}: {e}")

    threads = [threading.Thread(target=run, args=(i, label, fn), daemon=True) for i, (label, fn) in enumerate(jobs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=9)

    pools, total = [], 0
    for res in results:
        if res:
            items, t = res
            pools.append(items)
            total += t or 0

    merged, i = [], 0
    seen_ids, seen_urls, seen_titles = set(), set(), set()
    while any(i < len(p) for p in pools):
        for p in pools:
            if i < len(p):
                it = p[i]
                key_id = it.get("id")
                key_url = (it.get("full") or it.get("thumbnail") or "")[:180]
                key_title = f"{it.get('provider')}|{(it.get('title') or '').strip().lower()[:70]}"
                if (key_id and key_id in seen_ids) or (key_url and key_url in seen_urls) or (key_title in seen_titles):
                    continue
                if key_id:
                    seen_ids.add(key_id)
                if key_url:
                    seen_urls.add(key_url)
                seen_titles.add(key_title)
                merged.append(it)
        i += 1

    payload = {"items": merged, "total": total or len(merged), "errors": errors,
               "query": q, "variants": variants, "page": page}
    with _lock:
        _cache[cache_key] = (time.time(), payload)
        if len(_cache) > 300:
            _cache.clear()
    return payload

FEED_TOPICS = [
    "wallpaper keren", "alam indah", "laut biru", "gunung", "seni abstrak",
    "arsitektur modern", "makanan lezat", "kucing", "bunga", "ruang angkasa",
    "mobil keren", "pantai sunset", "jalanan kota", "hewan lucu", "teknologi",
    "desain interior", "pemandangan", "jalanan malam", "awan", "hutan",
]

def do_feed(page=1, page_size=20, media_type="all", pexels_key=None, pixabay_key=None):
    cache_key = f"f|{page}|{media_type}|{bool(pexels_key)}|{bool(pixabay_key)}"
    with _lock:
        hit = _cache.get(cache_key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
    t1 = FEED_TOPICS[((page - 1) * 2) % len(FEED_TOPICS)]
    t2 = FEED_TOPICS[((page - 1) * 2 + 1) % len(FEED_TOPICS)]
    box = {}
    def grab(key, topic):
        box[key] = do_search(topic, 1, max(page_size // 2, 8), media_type, pexels_key, pixabay_key)
    th1 = threading.Thread(target=grab, args=("a", t1), daemon=True)
    th2 = threading.Thread(target=grab, args=("b", t2), daemon=True)
    th1.start(); th2.start()
    th1.join(timeout=20); th2.join(timeout=20)
    a = box.get("a", {"items": [], "errors": []})
    b = box.get("b", {"items": [], "errors": []})
    payload = {
        "items": a["items"] + b["items"], "total": len(a["items"]) + len(b["items"]),
        "topics": [t1, t2], "query": f"{t1} + {t2}", "page": page,
        "errors": a.get("errors", []) + b.get("errors", []),
    }
    with _lock:
        _cache[cache_key] = (time.time(), payload)
    return payload

# ---------------------------------------------------------------- SSRF guard
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

def safe_remote_url(url):
    try:
        p = urllib.parse.urlparse(url)
        if p.scheme not in ("http", "https"):
            return None
        host = (p.hostname or "").lower()
        if not host or host in BLOCKED_HOSTS:
            return None
        if re.match(r"^127\.|^10\.|^192\.168\.|^172\.(1[6-9]|2\d|3[01])\.|^169\.254\.", host):
            return None
        return url
    except Exception:
        return None

# ---------------------------------------------------------------- handler
class handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        print("[glasspin]", fmt % args)

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def _json_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 2_000_000:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8", "replace") or "{}")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Pexels-Key, X-Pixabay-Key")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        try:
            path = urllib.parse.urlparse(self.path).path
            if path.endswith("/comments"):
                body = self._json_body()
                pin_id = str(body.get("pin_id") or "").strip()
                author = str(body.get("author") or "Anonim").strip()[:40] or "Anonim"
                text = str(body.get("text") or "").strip()[:1000]
                if not pin_id or not text:
                    return self._send(400, {"error": "pin_id dan text wajib diisi"})
                entry = {"id": f"c{int(time.time()*1000)}", "author": author,
                         "text": text, "ts": datetime.now(timezone.utc).isoformat()}
                data = load_comments()
                data.setdefault(pin_id, []).append(entry)
                save_comments(data)
                return self._send(200, {"ok": True, "comment": entry})
            return self._send(404, {"error": "not found"})
        except Exception as e:
            return self._send(500, {"error": str(e)})

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = dict(urllib.parse.parse_qsl(parsed.query))

            if path.endswith("/search"):
                q = (qs.get("q") or "").strip()
                if not q:
                    return self._send(400, {"error": "q wajib diisi"})
                return self._send(200, do_search(
                    q, int(qs.get("page") or 1), int(qs.get("page_size") or 20),
                    qs.get("type") or "all",
                    self.headers.get("X-Pexels-Key"), self.headers.get("X-Pixabay-Key")))

            if path.endswith("/feed"):
                return self._send(200, do_feed(
                    int(qs.get("page") or 1), int(qs.get("page_size") or 20),
                    qs.get("type") or "all",
                    self.headers.get("X-Pexels-Key"), self.headers.get("X-Pixabay-Key")))

            if path.endswith("/comments"):
                pin_id = (qs.get("pin_id") or "").strip()
                return self._send(200, {"pin_id": pin_id, "comments": load_comments().get(pin_id, [])})

            if path.endswith("/download"):
                url = safe_remote_url(qs.get("url") or "")
                if not url:
                    return self._send(400, {"error": "URL tidak valid"})
                filename = re.sub(r"[^\w\-. ]+", "_", (qs.get("filename") or "media").strip())[:100] or "media"
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                    ctype = r.headers.get("Content-Type", "application/octet-stream")
                if "." not in filename:
                    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
                           "image/gif": ".gif", "video/mp4": ".mp4", "video/webm": ".webm",
                           }.get(ctype.split(";")[0].strip(), "")
                    filename += ext
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
                return

            if path.endswith("/ping") or re.search(r"/api/?$", path):
                return self._send(200, {"ok": True, "service": "GlassPin API", "time": datetime.now(timezone.utc).isoformat()})

            return self._send(404, {"error": "not found", "path": path})
        except Exception as e:
            return self._send(500, {"error": str(e)})


# ---------------------------------------------------------------- uji lokal
if __name__ == "__main__":
    from http.server import ThreadingHTTPServer
    PORT = int(os.environ.get("PORT", "8001"))
    print(f"GlassPin API dev -> http://0.0.0.0:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), handler).serve_forever()
