from __future__ import annotations

import asyncio
from pathlib import Path

from .bot import LeadBot
from .config import Settings
from .scanner import ConsentScanner
from .storage import Storage

# Fill in these constants before running `python -m nft_leads_bot`.
# Do not share or commit a real session string or bot token.
BOT_TOKEN = "123456:replace-me"
TELETHON_API_ID = 12345
TELETHON_API_HASH = "replace-me"
TELETHON_SESSION_STRING = "replace-me"

# Add only chat IDs for communities you administer and whose members opted in.
CATEGORIES: dict[str, list[int]] = {
    "community_one": [-1001234567890],
    "community_two": [-1009876543210],
}
DATABASE_PATH = "data/leads.sqlite3"
BATCH_SIZE = 5


def main() -> None:
    settings = Settings(
        bot_token=BOT_TOKEN,
        telethon_api_id=TELETHON_API_ID,
        telethon_api_hash=TELETHON_API_HASH,
        telethon_session_string=TELETHON_SESSION_STRING,
        categories=CATEGORIES,
        database_path=Path(DATABASE_PATH),
        batch_size=BATCH_SIZE,
    )
    app = LeadBot(
        settings,
        Storage(settings.database_path),
        ConsentScanner(settings.telethon_api_id, settings.telethon_api_hash, settings.telethon_session_string),
    )
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
