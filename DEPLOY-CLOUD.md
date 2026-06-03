# Deploy the backend + Inspector to the cloud (works on any device, any network)

Goal: a permanent public HTTPS URL like `https://arivento-backend.onrender.com`
where the **Backend Inspector** (`/`) and the API work from **any device on any
network** — no localhost, no tunnel, no public-WiFi problems.

These files make it deploy-ready: `render.yaml`, `runtime.txt`, `.gitignore`,
plus the existing `app.py` / `db.py` / `requirements.txt`. Verified: the exact
Render start command (`uvicorn app:app --host 0.0.0.0 --port $PORT`) boots and
serves locally.

---

## Recommended: Render (free, no credit card)

### 1 · Put the `backend/` folder in a GitHub repo
Easiest is to make **`backend/` its own repo** (so the repo root has
`render.yaml`, `app.py`, `requirements.txt`).

```bash
cd "/Users/kaixiwei/Desktop/Food SCM +AI + BCT/AI+BCT platform/backend"
git init
git add .
git commit -m "Arivento backend + Inspector"
# create an empty repo on github.com first, then:
git remote add origin https://github.com/<you>/arivento-backend.git
git branch -M main
git push -u origin main
```
(`.gitignore` already excludes the venv and the local SQLite file.)

### 2 · Deploy on Render
1. Go to **https://render.com** → sign up (GitHub login, no card).
2. **New ▸ Blueprint** → pick your `arivento-backend` repo → Render reads
   `render.yaml` and pre-fills everything → **Apply**.
   *(Or **New ▸ Web Service** → pick the repo → Runtime **Python 3**, Build
   `pip install -r requirements.txt`, Start
   `uvicorn app:app --host 0.0.0.0 --port $PORT`, Instance **Free**.)*
3. Wait ~2–3 min for the first build. You get a URL like
   **`https://arivento-backend.onrender.com`**.

### 3 · Use it
- **Inspector (any device):** open `https://arivento-backend.onrender.com/`
- **Health:** `…/health` → `{"status":"ok"}`
- **API:** `…/api/ledger/blocks`

---

## Point the prototype app at the cloud backend
So anchors made in the app persist to the cloud and show in the cloud Inspector.

In the app tab → DevTools → Console:
```js
localStorage.ARIVENTO_API_BASE = 'https://arivento-backend.onrender.com'  // then reload
```
The app already reads this (CORS is open), so every anchor now writes to the
cloud — and you can open the Inspector on your phone to watch it appear.

---

## Good to know

- **Free tier sleeps after ~15 min idle** and the filesystem is **ephemeral** —
  the SQLite DB resets on restart/redeploy. Fine for a live demo (re-anchor and
  it reappears). For durable data, add a Render **Disk** and set
  `ARIVENTO_DB_PATH` to a path on it, or switch to Postgres.
- First request after sleep takes ~30s to wake (cold start).
- **Alternatives** (same idea): **Railway** (`railway up`, deploys a folder via
  CLI without GitHub) or **Fly.io** (`fly launch`). Render is the most
  beginner-friendly free option.

---

## Optional: also host the app itself
The prototype HTML is static. You can drop it on Netlify/Cloudflare Pages (see
`../dpp-public/README.md` for the pattern) and set its `ARIVENTO_API_BASE` to the
Render URL — then the whole thing runs from any device with nothing local.
