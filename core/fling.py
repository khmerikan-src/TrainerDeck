"""FLiNG trainer scraping + download."""

import re
import urllib.parse

import httpx

FLING_BASE = "https://flingtrainer.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def game_slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower())
    return s.strip("-")


def trainer_slug(name: str) -> str:
    return f"{game_slug(name)}-trainer"


def scrape_trainer(slug: str):
    """Scrape a FLiNG trainer page. Returns trainer dict or None."""
    url = f"{FLING_BASE}/trainer/{slug}/"
    try:
        r = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=30.0)
        if r.status_code != 200:
            return None
        html = r.text
    except Exception:
        return None

    options = 0
    m = re.search(r"Options Num (\d+)", html)
    if m:
        options = int(m.group(1))

    links = sorted(set(re.findall(r'href="(https://flingtrainer\.com/downloads/[A-Za-z0-9_,-]+)"', html)))
    files = []
    for l in links:
        try:
            rr = httpx.get(l, headers={**HEADERS, "Referer": url}, follow_redirects=True, timeout=90.0)
            final = str(rr.url)
            fname = urllib.parse.unquote(final.rstrip("/").split("/")[-1])
            size = 0
            try:
                size = int(rr.headers.get("content-length") or 0)
            except Exception:
                size = len(rr.content or b"")
            files.append(
                {
                    "filename": fname,
                    "size": size,
                    "download_url": l,
                    "source_id": l,
                }
            )
        except Exception:
            continue

    return {
        "slug": slug,
        "game": slug,
        "title": f"{slug} Trainer",
        "options": options,
        "files": files,
        "page_url": url,
        "found": bool(files),
    }


def find_trainer(game_name: str):
    slug = trainer_slug(game_name)
    t = scrape_trainer(slug)
    if t and t.get("found"):
        t["game"] = game_name
        t["title"] = f"{game_name} Trainer"
        return t
    # fallback: search FLiNG WP REST by slug variants
    for cand in (slug, game_slug(game_name).replace("-", ""), game_slug(game_name)):
        if not cand:
            continue
        tt = scrape_trainer(cand if not cand.endswith("-trainer") else cand)
        if tt and tt.get("found"):
            tt["game"] = game_name
            tt["title"] = f"{game_name} Trainer"
            return tt
    return None


def download_file(url: str, dest_path: str) -> int:
    """Download a trainer file (following FLiNG redirect chain). Returns bytes saved."""
    r = httpx.get(url, headers={**HEADERS, "Referer": f"{FLING_BASE}/"}, follow_redirects=True, timeout=120.0)
    r.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(r.content)
    return len(r.content)
