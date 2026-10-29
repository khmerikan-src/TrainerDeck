"""SteamGridDB API client - game search + artwork."""

import os
import urllib.parse

import httpx

SGDB_API_KEY = os.environ.get("SGDB_API_KEY", "1d3fa937ad19c7591c7ccd90dfe85193")
SGDB_BASE = "https://www.steamgriddb.com/api/v2"

_client = httpx.Client(
    base_url=SGDB_BASE,
    headers={
        "Authorization": f"Bearer {SGDB_API_KEY}",
        "Accept": "application/json",
    },
    timeout=30.0,
)


def _get(path: str):
    r = _client.get(path)
    r.raise_for_status()
    return r.json()


def search_games(query: str, limit: int = 8):
    q = urllib.parse.quote(query.strip())
    data = _get(f"/search/autocomplete/{q}").get("data") or []
    games = []
    for g in data[:limit]:
        art = None
        try:
            art = get_art(g.get("id"))
        except Exception:
            art = None
        games.append(
            {
                "id": g.get("id"),
                "name": g.get("name"),
                "release_date": g.get("release_date"),
                "types": g.get("types") or [],
                "art": art,
            }
        )
    return games


def get_art(game_id: int):
    """Return the best available artwork URL (grid > hero > logo) for a game."""
    endpoints = [
        ("grid", f"/grids/game/{game_id}"),
        ("hero", f"/heroes/game/{game_id}"),
        ("logo", f"/logos/game/{game_id}"),
    ]
    for kind, path in endpoints:
        try:
            j = _get(path)
            data = j.get("data") or []
            if data:
                best = sorted(
                    data,
                    key=lambda x: (x.get("width") or 0) * (x.get("height") or 0),
                    reverse=True,
                )[0]
                url = best.get("thumb") or best.get("url")
                if url:
                    return url
        except Exception:
            continue
    return None
