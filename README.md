# TrainerDeck

PC trainer library + launcher for Linux. Sources trainers from FLiNG Trainer,
artwork from SteamGridDB, launches through Wine/Proton backends.

## Run

```sh
cd /home/aoitako/trainerdeck
python3 -m uvicorn app:app --host 127.0.0.1 --port 8850
```

Open http://127.0.0.1:8850

## Endpoints

- `GET /api/health` - health
- `GET /api/backends` - available launch backends (wine, steam, heroic, lutris, faugus)
- `GET /api/games?q=...&limit=...` - SteamGridDB autocomplete + artwork
- `GET /api/games/{sgdb_id}/art` - artwork for a game id
- `POST /api/trainers/find` {game: "..."} - find FLiNG trainer
- `POST /api/trainers/download` {game: "..."} - download + register trainer
- `GET /api/library` - list downloaded trainers
- `DELETE /api/library/{id}` - remove trainer
- `POST /api/library/{id}/launch` {backend: "auto"|"steam"|"heroic"|"lutris"|"faugus"|"wine"}

## Data

- Trainers stored in `~/.trainerdeck/trainers/<game>/`
- Library DB: `~/.trainerdeck/library.db`
- Launch logs: `~/.trainerdeck/launch/`

## Config

- SteamGridDB API key: env `SGDB_API_KEY` or default in `core/sgdb.py`
- Launch backends:
  - steam: `~/.steam/steam/steamapps/compatdata/<appid>/pfx` + proton
  - heroic: `~/.config/heroic/GamesConfig/*.json` winePrefix
  - lutris: `~/.local/share/lutris`
  - faugus: `/home/aoitako/Faugus/default`
  - wine: WINEPREFIX env / default
