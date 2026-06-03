import os
import sqlite3
from typing import Optional


def _db_path() -> str:
    return os.environ.get("ARIVENTO_DB_PATH") or os.path.join(
        os.path.dirname(__file__), "arivento.sqlite3"
    )


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    # If the DB is locked (e.g. a second instance mid-write), wait up to 5s then
    # raise instead of hanging the request forever.
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
    owns = conn is None
    if conn is None:
        conn = get_conn()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS ledger_txs (
              tx_hash TEXT PRIMARY KEY,
              event_label TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at_ms INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ledger_blocks (
              block_hash TEXT PRIMARY KEY,
              prev_hash TEXT NOT NULL,
              tx_hash TEXT NOT NULL,
              nonce TEXT NOT NULL,
              block_ts_ms INTEGER NOT NULL,
              block_number INTEGER NOT NULL,
              event_label TEXT NOT NULL,
              ts_str TEXT NOT NULL,
              created_at_ms INTEGER NOT NULL,
              FOREIGN KEY (tx_hash) REFERENCES ledger_txs (tx_hash)
            );

            CREATE INDEX IF NOT EXISTS idx_ledger_blocks_number ON ledger_blocks(block_number DESC);
            CREATE INDEX IF NOT EXISTS idx_ledger_blocks_txhash ON ledger_blocks(tx_hash);

            CREATE TABLE IF NOT EXISTS doc_anchors (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              doc_type TEXT NOT NULL,
              file TEXT NOT NULL,
              file_hash TEXT NOT NULL,
              tx_hash TEXT NOT NULL,
              block_hash TEXT NOT NULL,
              block_number INTEGER NOT NULL,
              shipment_ref TEXT,
              lot TEXT,
              conf INTEGER,
              verdict_class TEXT,
              ts_str TEXT,
              record_json TEXT NOT NULL,
              created_at_ms INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_doc_anchors_blocknum ON doc_anchors(block_number DESC);
            """
        )
        conn.commit()
    finally:
        if owns:
            conn.close()
