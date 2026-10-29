"""Launch trainers through Wine/Proton backends (Steam, Heroic, Lutris, Faugus, Heronite, Wine)."""

import glob
import json
import os
import re
import subprocess
import time

HOME = "/home/aoitako"
PROTON_ROOTS = [
    f"{HOME}/.steam/steam/steamapps/common",
    f"{HOME}/.local/share/Steam/compatibilitytools.d",
]
HEROIC_PREFIX_BASE = "/home/aoitako/Games/Heroic/Prefixes"
HEROIC_CONFIG_DIR = "/home/aoitako/.config/heroic"
FAUGUS_PREFIX = "/home/aoitako/Faugus/default"
FAUGUS_LAUNCHER_DIR = "/home/aoitako/.local/share/faugus-launcher"
HERONITE_DATA_DIR = os.environ.get("HERONITE_DATA_DIR", "/home/aoitako/.local/share/heronite")
LUTRIS_PREFIX_BASE = os.path.expanduser("~/.local/share/lutris/prefixes")
GAME_WAIT_SECONDS = float(os.environ.get("TRAINERDECK_GAME_WAIT", "30"))

GAME_EXE_OVERRIDES = {
    "ubisoftconnect": "/home/aoitako/Games/Heroic/Ubisoft Game Launcher/UbisoftConnect.exe",
    "stellarblade": "/home/aoitako/Games/Heroic/Stellar Blade/SB/Binaries/Win64/SB-Win64-Shipping.exe",
}


def find_proton_tool_dirs():
    found = []
    for root in PROTON_ROOTS:
        if not os.path.isdir(root):
            continue
        for entry in sorted(os.listdir(root)):
            p = os.path.join(root, entry)
            if os.path.isdir(p) and (
                os.path.isdir(os.path.join(p, "files")) or os.path.isfile(os.path.join(p, "proton"))
            ):
                found.append(p)
    return found


def find_wine_bin():
    """Find a native wine loader (from Proton tools)."""
    best = None
    best_key = ""
    for d in find_proton_tool_dirs():
        cand = os.path.join(d, "files", "bin", "wine")
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            key = os.path.basename(d)
            if key > best_key:
                best = cand
                best_key = key
    if best:
        return best
    p = subprocess.run(["which", "wine"], capture_output=True, text=True)
    return p.stdout.strip() or None


def proton_env(wine_bin: str) -> dict:
    env = dict(os.environ)
    env["WINEPREFIX"] = env.get("WINEPREFIX", "")
    tool_dir = os.path.dirname(os.path.dirname(os.path.dirname(wine_bin)))
    for sub in ("", "/wine", "/wine/x86_64-unix"):
        p = os.path.join(tool_dir, "files", "lib", *sub.split("/")) if sub else os.path.join(tool_dir, "files", "lib")
        if os.path.isdir(p):
            env["LD_LIBRARY_PATH"] = p + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    return env


def _spawn(wine_bin: str, exe: str, wine_prefix: str, backend: str, log_path: str) -> dict:
    env = proton_env(wine_bin)
    env["WINEPREFIX"] = wine_prefix
    env["PATH"] = os.pathsep.join([os.path.dirname(wine_bin), env.get("PATH", "")])
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logf = open(log_path, "ab")
    try:
        proc = subprocess.Popen(
            [str(wine_bin), str(exe)],
            env=env,
            stdout=logf,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            cwd="/",
        )
        return {"ok": True, "backend": backend, "pid": proc.pid, "cmd": [str(wine_bin), str(exe)], "wine_prefix": wine_prefix}
    except Exception as e:
        return {"ok": False, "backend": backend, "error": str(e)}


def _heroic_prefixes() -> list[dict]:
    out = []
    gc_dir = os.path.join(HEROIC_CONFIG_DIR, "GamesConfig")
    if not os.path.isdir(gc_dir):
        return out
    for fn in sorted(os.listdir(gc_dir)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(gc_dir, fn)) as f:
                d = json.load(f)
            entries = d if isinstance(d, dict) else {}
            for k, v in entries.items():
                if not isinstance(v, dict):
                    continue
                wp = v.get("winePrefix") or ""
                wb = v.get("wineVersion") or {}
                bin_path = wb.get("bin") or ""
                out.append(
                    {
                        "appid": int(k) if str(k).isdigit() else None,
                        "name": k,
                        "wine_prefix": wp,
                        "wine_bin": bin_path,
                    }
                )
        except Exception:
            continue
    return out


def _norm(s: str) -> str:
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def _heroic_prefix_for(game_name: str):
    entries = _heroic_prefixes()
    if not entries:
        return None
    target = _norm(game_name)
    best = None
    best_score = -1
    for e in entries:
        p = e.get("wine_prefix") or ""
        if not p or not os.path.isdir(p):
            continue
        score = 0
        if target and target in _norm(p):
            score += 10
        if e.get("name", "") and target and target in _norm(e.get("name", "")):
            score += 5
        if score > best_score:
            best = e
            best_score = score
    if best is None or best_score <= 0:
        for e in entries:
            p = e.get("wine_prefix") or ""
            if p and os.path.isdir(p) and "/" in p:
                best = e
                break
    if best is None:
        best = entries[0]
    return best


def find_game_exe(prefix: str, game_name: str) -> str | None:
    """Find a windows game exe inside a wine prefix by name."""
    target = _norm(game_name)
    if not target:
        return None
    override = GAME_EXE_OVERRIDES.get(target)
    if override and os.path.isfile(override):
        return override
    base = os.path.join(prefix, "drive_c")
    if not os.path.isdir(base):
        return None
    best = None
    best_size = -1
    skip = {"windows", "internet", "accessories", "temp", "users", "startmenu", "desktop", "progdata", "common", "updat", "unins", "microsoft"}
    for dirpath, dirnames, filenames in os.walk(base):
        rel = dirpath[len(base):].lower().replace("\\", "/")
        segs = [s for s in rel.split("/") if s]
        if any(s in skip for s in segs):
            dirnames[:] = []
            continue
        for fn in filenames:
            if not fn.lower().endswith(".exe"):
                continue
            if not (target in _norm(fn) or any(target in _norm(s) for s in segs)):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                sz = os.path.getsize(fp)
            except Exception:
                continue
            if sz > best_size:
                best = fp
                best_size = sz
    return best


def _resolve_backend_ctx(backend: str, game: str, trainer: dict):
    """Resolve wine bin + prefix for wine-based backends. Returns dict."""
    if backend == "steam":
        appid = trainer.get("appid") or 0
        prefix = f"{HOME}/.steam/steam/steamapps/compatdata/{appid}/pfx"
        wb = find_wine_bin()
        return {"backend": backend, "wine_bin": wb, "wine_prefix": prefix, "ok": bool(wb), "error": None if wb else "No proton/wine binary found"}
    if backend == "heroic":
        he = _heroic_prefix_for(game)
        if not he or not he.get("wine_prefix") or not os.path.isdir(he["wine_prefix"]):
            return {"backend": backend, "wine_bin": None, "wine_prefix": None, "ok": False, "error": "No Heroic prefix for this game"}
        wb = he.get("wine_bin") or ""
        if wb and os.path.isfile(wb):
            wb = wb[: -len("/proton")] + "/files/bin/wine"
        if not wb or not os.path.exists(wb):
            wb = find_wine_bin()
        return {"backend": backend, "wine_bin": wb, "wine_prefix": he["wine_prefix"], "ok": True, "error": None}
    if backend == "lutris":
        prefix = None
        lutris_games = os.path.join(os.path.expanduser("~"), ".local", "share", "lutris", "games")
        if os.path.isdir(lutris_games):
            for fn in sorted(os.listdir(lutris_games)):
                if game.lower().replace(" ", "") in fn.lower().replace(" ", ""):
                    prefix = os.path.join(lutris_games, fn, "prefix")
                    if not os.path.isdir(prefix):
                        prefix = os.path.join(lutris_games, fn)
                    break
        if not prefix or not os.path.isdir(prefix):
            prefix = os.path.join(os.path.expanduser("~"), ".lutris", "prefixes", game_slug_safe(game))
        wb = None
        runners = os.path.join(os.path.expanduser("~"), ".local", "share", "lutris", "runners")
        if os.path.isdir(runners):
            for r in sorted(os.listdir(runners)):
                cand = os.path.join(runners, r, "files", "bin", "wine")
                if os.path.isfile(cand):
                    wb = cand
                    break
        if not wb:
            wb = find_wine_bin()
        return {"backend": backend, "wine_bin": wb, "wine_prefix": prefix, "ok": True, "error": None}
    if backend == "faugus":
        wb = None
        for d in find_proton_tool_dirs():
            if "CachyOS" in d or "cachyos" in d:
                cand = os.path.join(d, "files", "bin", "wine")
                if os.path.isfile(cand):
                    wb = cand
                    break
        if not wb:
            wb = find_wine_bin()
        return {"backend": backend, "wine_bin": wb, "wine_prefix": FAUGUS_PREFIX, "ok": True, "error": None}
    if backend == "heronite":
        wb = find_wine_bin()
        prefix = HERONITE_DATA_DIR
        if not (os.path.isdir(prefix) and (os.path.isdir(os.path.join(prefix, "drive_c")) or os.path.isdir(os.path.join(prefix, "pfx")))):
            he = _heroic_prefix_for(game)
            prefix = he.get("wine_prefix") if he else "/home/aoitako/Games/Heroic/Prefixes"
        return {"backend": backend, "wine_bin": wb, "wine_prefix": prefix, "ok": True, "error": None}
    if backend == "wine":
        wb = find_wine_bin()
        prefix = os.environ.get("TRAINERDECK_WINEPREFIX") or (trainer.get("wine_prefix") or "/home/aoitako/.wine")
        return {"backend": backend, "wine_bin": wb or "wine", "wine_prefix": prefix, "ok": True, "error": None}
    return {"backend": backend, "wine_bin": None, "wine_prefix": None, "ok": False, "error": f"Unknown backend: {backend}"}


def launch_trainer(backend: str, trainer: dict) -> dict:
    exe = trainer.get("path") or trainer.get("file_path")
    if not exe or not os.path.exists(exe):
        return {"ok": False, "backend": backend, "error": f"Trainer exe not found: {exe}"}
    game = trainer.get("game") or ""

    # wand-acs backend: delegate to the existing wand-acs CLI, which copies the
    # trainer into the AC Shadows prefix (with the .NET 4.8 shim) and launches
    # it there. This is the reliable path for AC Shadows trainers.
    if backend in ("wand", "acs"):
        import shutil
        wand = shutil.which("wand-acs") or "/home/aoitako/.local/bin/wand-acs"
        if not os.path.isfile(wand):
            return {"ok": False, "backend": backend, "error": "wand-acs not found"}
        log_dir = os.path.expanduser("~/.trainerdeck/launch")
        os.makedirs(log_dir, exist_ok=True)
        log_path = f"{log_dir}/wand-{os.getpid()}-{time.time()}.log"
        try:
            proc = subprocess.Popen(
                [wand, "--trainer", str(exe)],
                stdout=open(log_path, "ab"),
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
            time.sleep(2)
            alive = proc.poll() is None
            return {
                "ok": alive,
                "backend": backend,
                "pid": proc.pid,
                "cmd": [wand, "--trainer", str(exe)],
                "log": log_path,
                "error": None if alive else "trainer exited immediately",
            }
        except Exception as e:
            return {"ok": False, "backend": backend, "error": str(e)}
    log_dir = os.path.expanduser("~/.trainerdeck/launch")
    os.makedirs(log_dir, exist_ok=True)

    ctx = _resolve_backend_ctx(backend, game, trainer)
    wb = ctx.get("wine_bin")
    prefix = ctx.get("wine_prefix")
    ok = ctx.get("ok")
    err = ctx.get("error")

    if backend == "wine" and not wb:
        wb = "wine"

    if not ok or not wb or not prefix:
        return {"ok": False, "backend": backend, "error": err or f"Backend context failed: {backend}"}

    # Launch the trainer directly. (Auto-launching the game via raw wine is
    # unreliable — games often need Heroic/Steam's full env — so the user is
    # expected to have the game running first; the trainer then attaches.)
    trainer_log = f"{log_dir}/{backend}-{os.getpid()}-{time.time()}.log"
    return _spawn(wb, exe, prefix, backend, trainer_log)


def game_slug_safe(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
