import os
import re
import shutil
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core import fling, library, launch, sgdb

app = FastAPI(title="TrainerDeck")

TRAINER_ROOT = Path.home() / ".trainerdeck" / "trainers"


@app.on_event("startup")
def startup():
    library.init()


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/backends")
def backends():
    return {
        "wine": True,
        "steam": os.path.isdir("/home/aoitako/.steam/steam/steamapps/compatdata"),
        "heroic": len(launch._heroic_prefixes()) > 0,
        "lutris": os.path.isdir(os.path.expanduser("~/.local/share/lutris")),
        "faugus": os.path.isdir("/home/aoitako/Faugus/default"),
        "heronite": os.path.isdir(launch.HERONITE_DATA_DIR),
    }


@app.get("/api/games")
def api_games(q: str, limit: int = 8):
    if not q or len(q.strip()) < 2:
        return {"games": []}
    try:
        games = sgdb.search_games(q, limit=int(limit))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SteamGridDB error: {e}")
    return {"games": games}


@app.get("/api/games/{sgdb_id}/art")
def api_game_art(sgdb_id: int):
    url = sgdb.get_art(sgdb_id)
    if not url:
        raise HTTPException(status_code=404, detail="No artwork found")
    return {"url": url, "game_id": sgdb_id}


class TrainerFindRequest(BaseModel):
    game: str


class TrainerDownloadRequest(BaseModel):
    game: str


@app.post("/api/trainers/find")
def api_trainer_find(req: TrainerFindRequest):
    game = req.game
    if not game or len(game.strip()) < 2:
        raise HTTPException(status_code=400, detail="game name required")
    t = fling.find_trainer(game.strip())
    if not t:
        raise HTTPException(status_code=404, detail=f"No FLiNG trainer found for '{game}'")
    return t


@app.post("/api/trainers/download")
def api_trainer_download(req: TrainerDownloadRequest):
    game = req.game
    if not game or len(game.strip()) < 2:
        raise HTTPException(status_code=400, detail="game name required")
    t = fling.find_trainer(game.strip())
    if not t:
        raise HTTPException(status_code=404, detail=f"No FLiNG trainer found for '{game}'")
    fname = t["files"][0]["filename"] if t.get("files") else f"{fling.game_slug(game)}.exe"
    dest_dir = TRAINER_ROOT / fling.game_slug(game)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / fname
    size = fling.download_file(t["files"][0]["download_url"], str(dest))
    # register
    appid = None
    try:
        r = httpx.post(
            "https://store.steampowered.com/api/storesearch/",
            params={"term": game, "cc": "US", "l": "english"},
            timeout=30.0,
        )
        if r.status_code == 200:
            items = r.json().get("items") or []
            for it in items:
                if it.get("type") == "app" and game.lower().replace("'", "") in (it.get("name") or "").lower().replace("'", ""):
                    appid = it.get("id")
                    break
    except Exception:
        appid = None
    rid = library.add_trainer(
        game=game,
        sgdb_id=None,
        trainer_slug=t.get("slug"),
        filename=fname,
        version=None,
        path=str(dest),
        size=size,
        appid=appid,
    )
    return {"ok": True, "trainer": t, "path": str(dest), "size": size, "library_id": rid}


@app.get("/api/library")
def api_library():
    return {"trainers": library.list_trainers()}


@app.delete("/api/library/{tid}")
def api_library_delete(tid: int):
    library.delete_trainer(tid)
    return {"ok": True}


@app.post("/api/library/{tid}/launch")
def api_library_launch(tid: int, backend: str = "auto"):
    tr = library.get_trainer(tid)
    if not tr:
        raise HTTPException(status_code=404, detail="Trainer not in library")
    if backend == "auto":
        backend = "heroic" if os.path.isdir("/home/aoitako/Games/Heroic/Prefixes") else "wine"
    res = launch.launch_trainer(backend, tr)
    return res


@app.get("/api/library/{tid}")
def api_library_get(tid: int):
    tr = library.get_trainer(tid)
    if not tr:
        raise HTTPException(status_code=404, detail="Trainer not in library")
    return tr


@app.get("/api/launch/{tid}")
def api_launch(tid: int, backend: str = "auto"):
    tr = library.get_trainer(tid)
    if not tr:
        raise HTTPException(status_code=404, detail="Trainer not in library")
    if backend == "auto":
        backend = "heroic" if os.path.isdir("/home/aoitako/Games/Heroic/Prefixes") else "wine"
    res = launch.launch_trainer(backend, tr)
    return res


@app.get("/")
def root():
    return FileResponse("/home/aoitako/trainerdeck/static/index.html")


@app.get("/static/{rest:path}")
def static_files(rest: str):
    return FileResponse(f"/home/aoitako/trainerdeck/static/{rest}")


app.mount("/static", StaticFiles(directory="/home/aoitako/trainerdeck/static"), name="static")


@app.exception_handler(Exception)
def exc_handler(request, exc):
    return {"ok": False, "error": str(exc)}
