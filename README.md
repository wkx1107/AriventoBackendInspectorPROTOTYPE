# Arivento Prototype Backend

A minimal **FastAPI + SQLite** service that persists the prototype's
blockchain-style ledger: the chained SHA-256 "blocks", the full JSON payloads
that were hashed, and the Import Doc Copilot anchor records.

The frontend (`index-v0.2.3.html`) hashes and chains entirely in-browser. This
backend is the optional **persistence + shared-state layer** — anchors survive a
page reload and can be shared across devices/users instead of living only in the
tab's memory.

---

## What it stores

| Table | Holds |
|---|---|
| `ledger_txs` | Each transaction: `tx_hash`, `event_label`, the full canonical `payload_json`, timestamp |
| `ledger_blocks` | The chain: `block_hash`, `prev_hash`, `tx_hash`, `nonce`, `block_number`, timestamps |
| `doc_anchors` | Import Doc Copilot records the DPP/Ledger UI reads back |

**Hash chaining** (identical scheme to the in-browser version):

```
tx_hash    = sha256( compact-JSON(tx) )
block_hash = "0x" + sha256( prev_hash + tx_hash + nonce + block_ts_ms )
```

`nonce` is a fresh 128-bit value (`secrets.token_hex(16)`) per block, so every
anchor is unique and the chain rolls forward from `prev_hash`.

---

## Prerequisites

- Python 3.9+ (`python3 --version`)
- The dependencies in `requirements.txt`: `fastapi`, `uvicorn`, `pydantic`

---

## Setup (one-time)

```bash
cd "/Users/kaixiwei/Desktop/Food SCM +AI + BCT/AI+BCT platform/backend"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the API

```bash
# Always cd into backend/ first — pip & uvicorn must see requirements.txt + app.py.
cd "/Users/kaixiwei/Desktop/Food SCM +AI + BCT/AI+BCT platform/backend"
source .venv/bin/activate
uvicorn app:app --reload --port 8001
```

You should see `Uvicorn running on http://127.0.0.1:8001`.
The SQLite file and tables are created automatically on startup — the FastAPI
`lifespan` handler runs `init_db` before the app accepts requests.

> **Use port 8001, not 8000.** Port 8000 is the static prototype
> (`python -m http.server 8000` serving the HTML + `passport.html`). Running the
> API on the same port causes `address already in use`.

### Check what the backend holds — visual inspector

Open **<http://localhost:8001/>** in a browser. It's a built-in read-only
dashboard (`dashboard.html`) that shows:

- live online/offline status + counts (blocks, txs, doc anchors)
- the ledger blocks newest-first — **click a row** to see the full JSON payload
  that was hashed
- automatic **hash-chain verification** (each block's `prev_hash` vs the
  previous block's `block_hash`) with a ✓/✗ per row
- the persisted Import Doc Copilot anchors
- auto-refreshes every 5s (toggle off in the header)

> **Need the Inspector on another device or over public WiFi?** `localhost` only
> works on this machine, and locked-down/public networks block device-to-device
> access and tunnels. Deploy the backend to a free cloud host for a permanent
> public URL that works anywhere — see **`DEPLOY-CLOUD.md`**.

### Other ways to inspect

```bash
curl http://localhost:8001/health                 # {"status":"ok"}
curl http://localhost:8001/api/ledger/blocks       # {"blocks":[...]}
```

- **Swagger UI** (interactive, call any endpoint): <http://localhost:8001/docs>
- **ReDoc** (read-only API reference): <http://localhost:8001/redoc>
- **SQLite directly**: `sqlite3 arivento.sqlite3 "SELECT * FROM ledger_blocks;"`

---

## API reference

### `GET /health`
Liveness check → `{ "status": "ok" }`

### `POST /api/ledger/anchor`
Hash a payload, append a chained block, persist both.

Request:
```json
{ "event_label": "Import-doc anchor · Invoice · INV-CDV-0058.txt",
  "tx": { "any": "json", "you": "want hashed" } }
```
Response:
```json
{ "block_hash": "0x…", "tx_hash": "…", "block_number": 3418001,
  "prev_hash": "0x…", "nonce": "…", "block_ts_ms": 1780121660500,
  "ts_str": "30 May 2026 07:14:20" }
```

### `GET /api/ledger/blocks?limit=200`
Most recent blocks first (`limit` 1–2000, default 200) →
`{ "blocks": [ { block_hash, prev_hash, tx_hash, nonce, block_ts_ms, block_number, event_label, ts_str }, … ] }`

### `GET /api/ledger/tx/{tx_hash}`
The original payload behind a tx → `{ tx_hash, event_label, payload, created_at_ms }`
(`404` if unknown).

### `POST /api/documents/anchors`
Store a Doc Copilot anchor record. Body fields:
`docType, file, fileHash, txHash, blockHash, blockNumber` (required) ·
`shipmentRef, lot, conf, verdictClass, ts` (optional) → `{ "ok": true }`

### `GET /api/documents/anchors?limit=200`
Doc anchor records, newest first → `{ "anchors": [ … ] }`

---

## Database

- **Engine:** SQLite (WAL mode, foreign keys on)
- **Location:** `backend/arivento.sqlite3` (override with `ARIVENTO_DB_PATH`)
- **Schema:** created idempotently at startup — safe to delete the `.sqlite3`
  file to reset; it's rebuilt empty on next launch.

Inspect it directly:
```bash
sqlite3 arivento.sqlite3 "SELECT block_number, event_label FROM ledger_blocks ORDER BY block_number DESC LIMIT 5;"
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ARIVENTO_DB_PATH` | `backend/arivento.sqlite3` | SQLite file location |
| `ARIVENTO_BLOCK_NUMBER_BASE` | `3418000` | Starting block number for an empty chain |

CORS is open (`allow_origins=["*"]`) so the static prototype on `:8000` can call
the API on `:8001` from the browser.

---

## Connect the frontend

In the prototype tab → DevTools → Console:

```js
localStorage.ARIVENTO_API_BASE = 'http://localhost:8001'
```

(Defaults to `http://localhost:8000` if unset — point it at `:8001` so calls hit
the API, not the static server. Reload the page after setting it.)

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Could not open requirements file …` | Wrong folder. `pwd`, then `cd` into `…/AI+BCT platform/backend`. |
| `address already in use` | Port busy. `lsof -nP -iTCP:8001 -sTCP:LISTEN` to see who, or use `--port 8002`. |
| `uvicorn: command not found` | venv not active → `source .venv/bin/activate`. |
| `ModuleNotFoundError: fastapi` | Deps not installed in this venv → `pip install -r requirements.txt`. |
| Frontend still shows old data | Set `localStorage.ARIVENTO_API_BASE` and reload the tab. |

### Stop the server
`Ctrl-C` in its terminal, or find and kill it:
```bash
lsof -nP -iTCP:8001 -sTCP:LISTEN          # note the PID
kill <PID>
```
