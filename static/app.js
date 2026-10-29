const gameResults = document.getElementById("game-results");
const detail = document.getElementById("detail");
const detailArt = document.getElementById("detail-art");
const detailInfo = document.getElementById("detail-info");
const trainerFiles = document.getElementById("trainer-files");
const downloadBtn = document.getElementById("download-btn");
const downloadStatus = document.getElementById("download-status");
const libraryList = document.getElementById("library-list");
const backendStatus = document.getElementById("backend-status");
const searchInput = document.getElementById("game-search");

let selectedGame = null;

async function loadBackends() {
  const r = await fetch("/api/backends");
  const d = await r.json();
  const parts = [];
  for (const k of ["steam", "heroic", "lutris", "faugus", "wine"]) {
    parts.push(`${k}: ${d[k] ? "YES" : "no"}`);
  }
  backendStatus.textContent = parts.join("  ");
  backendStatus.className = d.wine ? "backend-status" : "backend-status bad";
}

function artUrl(url) {
  if (!url) return "";
  return url.startsWith("http") ? url : `https://www.steamgriddb.com${url}`;
}

async function searchGames() {
  const q = searchInput.value.trim();
  if (q.length < 2) {
    gameResults.innerHTML = "";
    return;
  }
  const r = await fetch(`/api/games?q=${encodeURIComponent(q)}&limit=8`);
  const d = await r.json();
  gameResults.innerHTML = "";
  for (const g of d.games || []) {
    const div = document.createElement("div");
    div.className = "game-card";
    div.onclick = () => selectGame(g);
    const img = document.createElement("img");
    img.src = artUrl(g.art);
    img.onerror = () => (img.style.display = "none");
    img.alt = g.name;
    const body = document.createElement("div");
    body.className = "name";
    body.innerHTML = `<div>${g.name}</div><div>release ${g.release_date ? new Date(g.release_date * 1000).toISOString().slice(0, 10) : ""}</div>`;
    div.appendChild(img);
    div.appendChild(body);
    gameResults.appendChild(div);
  }
}

let searchTimer;
searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => searchGames(), 400);
});

async function selectGame(g) {
  selectedGame = g;
  detail.classList.remove("hidden");
  detailArt.innerHTML = `<img src="${artUrl(g.art)}" alt="${g.name}" />`;
  detailInfo.innerHTML = `<h2>${g.name}</h2><div class="tag">SteamGridDB #${g.id}</div>`;
  trainerFiles.innerHTML = '<div class="download-status">Loading trainer...</div>';
  const r = await fetch("/api/trainers/find", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game: g.name }),
  });
  const t = await r.json();
  if (!t.found) {
    trainerFiles.innerHTML = `<div class="download-status">No FLiNG trainer found for ${g.name}</div>`;
    return;
  }
  trainerFiles.innerHTML = "";
  const tbl = document.createElement("table");
  tbl.innerHTML = `<thead><tr><th>Trainer file</th><th>Size</th><th></th></tr></thead><tbody></tbody>`;
  const tb = tbl.querySelector("tbody");
  for (const f of t.files || []) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${f.filename}</td><td>${f.size ? (f.size / 1024).toFixed(1) + " KB" : "?"}</td><td><button class="btn" data-url="${f.download_url}" data-name="${f.filename}">Download</button></td>`;
    tb.appendChild(tr);
  }
  trainerFiles.appendChild(tbl);
  trainerFiles.querySelectorAll("button").forEach((b) => {
    b.addEventListener("click", async () => {
      downloadStatus.textContent = "Downloading...";
      downloadBtn.disabled = true;
      const r2 = await fetch("/api/trainers/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game: g.name }),
      });
      const d = await r2.json();
      downloadStatus.textContent = d.ok ? `Downloaded OK -> ${d.path}` : `Error: ${d.detail || d.error || "unknown"}`;
      downloadBtn.disabled = false;
      await refreshLibrary();
    });
  });
}

downloadBtn.addEventListener("click", async () => {
  if (!selectedGame) return;
  downloadBtn.disabled = true;
  downloadStatus.textContent = "Downloading...";
  const r = await fetch("/api/trainers/download", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ game: selectedGame.name }),
  });
  const d = await r.json();
  downloadStatus.textContent = d.ok ? `Downloaded OK -> ${d.path}` : `Error: ${d.detail || d.error || "unknown"}`;
  downloadBtn.disabled = false;
  await refreshLibrary();
});

async function refreshLibrary() {
  const r = await fetch("/api/library");
  const d = await r.json();
  libraryList.innerHTML = "";
  const trainers = d.trainers || [];
  if (!trainers.length) {
    libraryList.innerHTML = '<div class="download-status">No trainers downloaded yet.</div>';
    return;
  }
  const tbl = document.createElement("table");
  tbl.innerHTML = `<thead><tr><th>ID</th><th>Game</th><th>File</th><th>Size</th><th>Launch</th><th></th></tr></thead><tbody></tbody>`;
  const tb = tbl.querySelector("tbody");
  for (const t of trainers) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${t.id}</td><td>${t.game}</td><td>${t.filename}</td><td>${t.size ? (t.size / 1024).toFixed(1) + " KB" : "?"}</td><td></td><td><button class="btn launch-del" data-id="${t.id}" data-del="1">Delete</button></td>`;
    const launchCell = tr.children[4];
    const backends = ["steam", "heroic", "lutris", "faugus", "wine"];
    for (const b of backends) {
      const btn = document.createElement("button");
      btn.className = "btn";
      btn.dataset.id = t.id;
      btn.dataset.backend = b;
      btn.textContent = b;
      btn.addEventListener("click", async () => {
        const r = await fetch(`/api/library/${t.id}/launch`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ backend: b }),
        });
        const d = await r.json();
        alert(JSON.stringify(d));
      });
      launchCell.appendChild(btn);
      launchCell.appendChild(document.createTextNode(" "));
    }
    launchCell.appendChild(document.createTextNode(" "));
    const autoBtn = document.createElement("button");
    autoBtn.className = "btn";
    autoBtn.dataset.id = t.id;
    autoBtn.dataset.backend = "auto";
    autoBtn.textContent = "auto";
    autoBtn.addEventListener("click", async () => {
      const r = await fetch(`/api/library/${t.id}/launch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ backend: "auto" }),
      });
      const d = await r.json();
      alert(JSON.stringify(d));
    });
    launchCell.appendChild(autoBtn);
    tb.appendChild(tr);
  }
  libraryList.appendChild(tbl);
}

document.getElementById("library").addEventListener("click", async (e) => {
  const b = e.target.closest(".launch-del");
  if (!b) return;
  const id = parseInt(b.dataset.id);
  await fetch(`/api/library/${id}`, { method: "DELETE" });
  await refreshLibrary();
});

async function init() {
  await loadBackends();
  await refreshLibrary();
  searchGames();
}
init();
