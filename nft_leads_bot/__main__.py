from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# Allow both `python -m nft_leads_bot` and a double-click/direct invocation of
# `nft_leads_bot/__main__.py` on Windows. Direct invocation adds the package
# directory, rather than its parent, to sys.path by default.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nft_leads_bot.bot import LeadBot
from nft_leads_bot.config import Settings
from nft_leads_bot.scanner import ConsentScanner
from nft_leads_bot.storage import Storage

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
# Number of matching profiles queued by one search, and maximum new profiles
# whose public collectible fields are checked during that search.
BATCH_SIZE = 25
PROFILE_CHECK_LIMIT = 1_000
SCAN_REVISION = "strict-star-gift-unique-v5"
LOG_FILE = "nft_leads_bot.log"
LOG_LEVEL = logging.DEBUG


def configure_logging() -> None:
    """Write detailed diagnostics to the terminal and a local log file."""
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding="utf-8")],
        force=True,
    )
    logging.getLogger("telethon").setLevel(logging.INFO)
    logging.getLogger(__name__).info("Logging started: level=%s, file=%s", logging.getLevelName(LOG_LEVEL), LOG_FILE)


def main() -> None:
    configure_logging()
    settings = Settings(
        bot_token=BOT_TOKEN,
        telethon_api_id=TELETHON_API_ID,
        telethon_api_hash=TELETHON_API_HASH,
        telethon_session_string=TELETHON_SESSION_STRING,
        categories=CATEGORIES,
        database_path=Path(DATABASE_PATH),
        batch_size=BATCH_SIZE,
        profile_check_limit=PROFILE_CHECK_LIMIT,
        scan_revision=SCAN_REVISION,
    )
    app = LeadBot(
        settings,
        Storage(settings.database_path),
        ConsentScanner(settings.telethon_api_id, settings.telethon_api_hash, settings.telethon_session_string),
    )
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
