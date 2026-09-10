"""SQLite persistence for File d'attente vacation events."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from utils.logger import get_logger
from utils.paths import VACATIONS_DB_FILE, VACATIONS_JSON_FILE, ensure_runtime_dirs

logger = get_logger("vacations_db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS vacation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_tag TEXT NOT NULL,
    ctl_index INTEGER,
    css_class TEXT,
    data_moment TEXT,
    title TEXT,
    arrivee_depart TEXT,
    personne TEXT,
    personne_id TEXT,
    personne_filtre_key TEXT,
    etablissement TEXT,
    etablissement_id TEXT,
    realise_par TEXT,
    lieu TEXT,
    is_canceled INTEGER NOT NULL DEFAULT 0,
    scraped_at TEXT NOT NULL,
    UNIQUE(event_tag)
);
"""


def default_db_path() -> Path:
    ensure_runtime_dirs()
    return VACATIONS_DB_FILE


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def upsert_events(
    records: Sequence[dict[str, Any]],
    db_path: Path | None = None,
) -> int:
    """Insert or replace vacation rows. Returns number of rows written."""
    if not records:
        return 0
    scraped_at = datetime.now(timezone.utc).isoformat()
    path = db_path or default_db_path()
    conn = connect(path)
    try:
        conn.executemany(
            """
            INSERT INTO vacation_events (
                event_tag, ctl_index, css_class, data_moment, title,
                arrivee_depart, personne, personne_id, personne_filtre_key,
                etablissement, etablissement_id, realise_par, lieu,
                is_canceled, scraped_at
            ) VALUES (
                :event_tag, :ctl_index, :css_class, :data_moment, :title,
                :arrivee_depart, :personne, :personne_id, :personne_filtre_key,
                :etablissement, :etablissement_id, :realise_par, :lieu,
                :is_canceled, :scraped_at
            )
            ON CONFLICT(event_tag) DO UPDATE SET
                ctl_index=excluded.ctl_index,
                css_class=excluded.css_class,
                data_moment=excluded.data_moment,
                title=excluded.title,
                arrivee_depart=excluded.arrivee_depart,
                personne=excluded.personne,
                personne_id=excluded.personne_id,
                personne_filtre_key=excluded.personne_filtre_key,
                etablissement=excluded.etablissement,
                etablissement_id=excluded.etablissement_id,
                realise_par=excluded.realise_par,
                lieu=excluded.lieu,
                is_canceled=excluded.is_canceled,
                scraped_at=excluded.scraped_at
            """,
            [{**row, "scraped_at": scraped_at} for row in records],
        )
        conn.commit()
        count = len(records)
        logger.info("Vacation events saved | path=%s count=%s", path, count)
        return count
    finally:
        conn.close()


def default_json_path() -> Path:
    ensure_runtime_dirs()
    return VACATIONS_JSON_FILE


def fetch_all_events(db_path: Path | None = None) -> list[dict[str, Any]]:
    """Read all vacation_events rows (newest scrape first by ctl_index)."""
    path = db_path or default_db_path()
    if not path.exists():
        return []
    conn = connect(path)
    try:
        rows = conn.execute(
            """
            SELECT
                event_tag, ctl_index, css_class, data_moment, title,
                arrivee_depart, personne, personne_id, personne_filtre_key,
                etablissement, etablissement_id, realise_par, lieu,
                is_canceled, scraped_at
            FROM vacation_events
            ORDER BY ctl_index ASC, id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def export_events_jsonl(
    records: Sequence[dict[str, Any]] | None = None,
    *,
    db_path: Path | None = None,
    json_path: Path | None = None,
) -> Path:
    """Write one JSON object per line (JSONL). Returns output path."""
    path = json_path or default_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(records) if records is not None else fetch_all_events(db_path)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    logger.info("Vacation events JSONL exported | path=%s count=%s", path, len(rows))
    return path
