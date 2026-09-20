from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    bot_token: str
    telethon_api_id: int
    telethon_api_hash: str
    telethon_session_string: str
    categories: dict[str, list[int]]
    database_path: Path = Path("data/leads.sqlite3")
    batch_size: int = 5
