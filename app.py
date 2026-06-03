import hashlib
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from db import get_conn, init_db


_DASHBOARD_HTML = os.path.join(os.path.dirname(__file__), "dashboard.html")


BLOCK_NUMBER_BASE = int(os.environ.get("ARIVENTO_BLOCK_NUMBER_BASE", "3418000"))


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _ts_str(ms: int) -> str:
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).astimezone()
    return dt.strftime("%d %b %Y %H:%M:%S")


class AnchorRequest(BaseModel):
    event_label: str = Field(..., min_length=1)
    tx: Dict[str, Any]


class AnchorResponse(BaseModel):
    block_hash: str
    tx_hash: str
    block_number: int
    prev_hash: str
    nonce: str
    block_ts_ms: int
    ts_str: str


class DocAnchorRecord(BaseModel):
    docType: str
    file: str
    fileHash: str
    txHash: str
    blockHash: str
    blockNumber: int
    shipmentRef: Optional[str] = None
    lot: Optional[str] = None
    conf: Optional[int] = None
    verdictClass: Optional[str] = None
    ts: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure the SQLite schema exists before serving requests.
    conn = get_conn()
    try:
        init_db(conn)
    finally:
        conn.close()
    yield
    # Shutdown: nothing to release (connections are opened per-request).


app = FastAPI(title="Arivento Prototype API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    # Human-friendly read-only inspector for the persisted ledger.
    return FileResponse(_DASHBOARD_HTML, media_type="text/html")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/ledger/anchor", response_model=AnchorResponse)
def anchor(req: AnchorRequest) -> AnchorResponse:
    created_at_ms = _now_ms()
    payload_json = json.dumps(req.tx, ensure_ascii=False, separators=(",", ":"))
    tx_hash = _sha256_hex(payload_json)

    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT block_hash, block_number FROM ledger_blocks ORDER BY block_number DESC LIMIT 1"
        )
        row = cur.fetchone()
        if row:
            prev_hash = row["block_hash"]
            block_number = int(row["block_number"]) + 1
        else:
            prev_hash = "0x" + ("0" * 64)
            block_number = BLOCK_NUMBER_BASE

        nonce = secrets.token_hex(16)
        block_ts_ms = _now_ms()
        block_hash = "0x" + _sha256_hex(prev_hash + tx_hash + nonce + str(block_ts_ms))
        ts_str = _ts_str(block_ts_ms)

        conn.execute(
            "INSERT OR REPLACE INTO ledger_txs(tx_hash, event_label, payload_json, created_at_ms) VALUES(?,?,?,?)",
            (tx_hash, req.event_label, payload_json, created_at_ms),
        )
        conn.execute(
            "INSERT INTO ledger_blocks(block_hash, prev_hash, tx_hash, nonce, block_ts_ms, block_number, event_label, ts_str, created_at_ms) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                block_hash,
                prev_hash,
                tx_hash,
                nonce,
                block_ts_ms,
                block_number,
                req.event_label,
                ts_str,
                created_at_ms,
            ),
        )
        conn.commit()

        return AnchorResponse(
            block_hash=block_hash,
            tx_hash=tx_hash,
            block_number=block_number,
            prev_hash=prev_hash,
            nonce=nonce,
            block_ts_ms=block_ts_ms,
            ts_str=ts_str,
        )
    finally:
        conn.close()


@app.get("/api/ledger/blocks")
def list_blocks(limit: int = 200) -> Dict[str, Any]:
    limit = max(1, min(limit, 2000))
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT block_hash, prev_hash, tx_hash, nonce, block_ts_ms, block_number, event_label, ts_str FROM ledger_blocks ORDER BY block_number DESC LIMIT ?",
            (limit,),
        )
        blocks = [
            {
                "block_hash": r["block_hash"],
                "prev_hash": r["prev_hash"],
                "tx_hash": r["tx_hash"],
                "nonce": r["nonce"],
                "block_ts_ms": r["block_ts_ms"],
                "block_number": r["block_number"],
                "event_label": r["event_label"],
                "ts_str": r["ts_str"],
            }
            for r in cur.fetchall()
        ]
        return {"blocks": blocks}
    finally:
        conn.close()


@app.get("/api/ledger/tx/{tx_hash}")
def get_tx(tx_hash: str) -> Dict[str, Any]:
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT tx_hash, event_label, payload_json, created_at_ms FROM ledger_txs WHERE tx_hash=?",
            (tx_hash,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="tx not found")
        return {
            "tx_hash": row["tx_hash"],
            "event_label": row["event_label"],
            "payload": json.loads(row["payload_json"]),
            "created_at_ms": row["created_at_ms"],
        }
    finally:
        conn.close()


@app.post("/api/documents/anchors")
def create_doc_anchor(rec: DocAnchorRecord) -> Dict[str, Any]:
    created_at_ms = _now_ms()
    record_json = rec.model_dump_json()
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO doc_anchors(
              doc_type, file, file_hash, tx_hash, block_hash, block_number,
              shipment_ref, lot, conf, verdict_class, ts_str, record_json, created_at_ms
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                rec.docType,
                rec.file,
                rec.fileHash,
                rec.txHash,
                rec.blockHash,
                rec.blockNumber,
                rec.shipmentRef,
                rec.lot,
                rec.conf,
                rec.verdictClass,
                rec.ts,
                record_json,
                created_at_ms,
            ),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.get("/api/documents/anchors")
def list_doc_anchors(limit: int = 200) -> Dict[str, Any]:
    limit = max(1, min(limit, 2000))
    conn = get_conn()
    try:
        cur = conn.execute(
            "SELECT record_json FROM doc_anchors ORDER BY block_number DESC, id DESC LIMIT ?",
            (limit,),
        )
        anchors: List[Dict[str, Any]] = []
        for r in cur.fetchall():
            try:
                anchors.append(json.loads(r["record_json"]))
            except Exception:
                continue
        return {"anchors": anchors}
    finally:
        conn.close()
