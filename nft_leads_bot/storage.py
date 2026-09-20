from __future__ import annotations

import sqlite3
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Lead:
    telegram_id: int
    display_name: str
    username: str | None
    category: str


class Storage:
    def __init__(self, path: Path) -> None:
        logger.info("Opening SQLite storage: path=%s", path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS leads (
              telegram_id INTEGER PRIMARY KEY, display_name TEXT NOT NULL,
              username TEXT, category TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS deliveries (
              delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
              operator_id INTEGER NOT NULL, telegram_id INTEGER NOT NULL,
              delivered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              UNIQUE (operator_id, telegram_id),
              FOREIGN KEY (telegram_id) REFERENCES leads(telegram_id)
            );
            """
        )
        self.connection.commit()

    def save_candidates(self, leads: list[Lead]) -> None:
        logger.info("Saving scan candidates: count=%d", len(leads))
        self.connection.executemany(
            "INSERT INTO leads(telegram_id, display_name, username, category) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET display_name=excluded.display_name, "
            "username=excluded.username, category=excluded.category",
            [(lead.telegram_id, lead.display_name, lead.username, lead.category) for lead in leads],
        )
        self.connection.commit()

    def next_undelivered(self, operator_id: int, category: str) -> Lead | None:
        row = self.connection.execute(
            """SELECT l.telegram_id, l.display_name, l.username, l.category FROM leads l
               WHERE l.category = ? AND NOT EXISTS (
                 SELECT 1 FROM deliveries d WHERE d.operator_id = ? AND d.telegram_id = l.telegram_id
               ) ORDER BY l.created_at, l.telegram_id LIMIT 1""",
            (category, operator_id),
        ).fetchone()
        lead = Lead(*row) if row else None
        logger.debug("Next lead query: operator_id=%s category=%r result_user_id=%s", operator_id, category, lead.telegram_id if lead else None)
        return lead

    def mark_delivered(self, operator_id: int, telegram_id: int) -> None:
        logger.info("Marking delivery: operator_id=%s user_id=%s", operator_id, telegram_id)
        self.connection.execute(
            "INSERT OR IGNORE INTO deliveries(operator_id, telegram_id) VALUES (?, ?)",
            (operator_id, telegram_id),
        )
        self.connection.commit()

    def history(self, operator_id: int, limit: int = 25) -> list[Lead]:
        rows = self.connection.execute(
            """SELECT l.telegram_id, l.display_name, l.username, l.category FROM deliveries d
               JOIN leads l ON l.telegram_id = d.telegram_id WHERE d.operator_id = ?
               ORDER BY d.delivery_id DESC LIMIT ?""",
            (operator_id, limit),
        ).fetchall()
        leads = [Lead(*row) for row in rows]
        logger.debug("History query: operator_id=%s limit=%d count=%d", operator_id, limit, len(leads))
        return leads
