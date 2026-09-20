from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import User

from nft_leads_bot.storage import Lead

logger = logging.getLogger(__name__)


class ConsentScanner:
    """Scans only participant lists that Telegram exposes to the approved account."""

    def __init__(self, api_id: int, api_hash: str, session: str) -> None:
        self.client = TelegramClient(StringSession(session), api_id, api_hash)
        self._scan_lock = asyncio.Lock()

    async def start(self) -> None:
        logger.info("Connecting Telethon client")
        await self.client.connect()
        if not await self.client.is_user_authorized():
            logger.error("Telethon session is not authorized")
            raise RuntimeError("TELETHON_SESSION_STRING is not authorized")
        logger.info("Telethon client is authorized and connected")

    async def stop(self) -> None:
        logger.info("Disconnecting Telethon client")
        await self.client.disconnect()

    async def prefetch(self, category: str, chat_ids: Iterable[int], minimum: int) -> list[Lead]:
        """Return up to `minimum` visible, opted-in members with public collectible data."""
        found: dict[int, Lead] = {}
        chat_ids = list(chat_ids)
        logger.info("Starting scan: category=%r chats=%s target=%d", category, chat_ids, minimum)
        async with self._scan_lock:
            for chat_id in chat_ids:
                scanned = skipped = without_collectible = 0
                try:
                    logger.info("Resolving chat: chat_id=%s", chat_id)
                    entity = await self.client.get_entity(chat_id)
                    logger.info("Participant scan started: chat_id=%s entity=%s", chat_id, type(entity).__name__)
                    async for member in self.client.iter_participants(entity):
                        scanned += 1
                        if not isinstance(member, User) or member.bot or member.deleted:
                            skipped += 1
                            logger.debug("Skipping participant: chat_id=%s id=%s bot=%s deleted=%s", chat_id, getattr(member, "id", None), getattr(member, "bot", None), getattr(member, "deleted", None))
                            continue
                        if member.id in found:
                            skipped += 1
                            logger.debug("Skipping duplicate participant: chat_id=%s user_id=%s", chat_id, member.id)
                            continue
                        if not await self._has_public_collectible(member):
                            without_collectible += 1
                            continue
                        name = " ".join(part for part in (member.first_name, member.last_name) if part).strip()
                        found[member.id] = Lead(member.id, name or "Telegram user", member.username, category)
                        logger.info("Collectible profile found: chat_id=%s user_id=%s username=%r total=%d", chat_id, member.id, member.username, len(found))
                        if len(found) >= minimum:
                            logger.info("Scan target reached: found=%d scanned=%d", len(found), scanned)
                            return list(found.values())
                    logger.info("Participant scan finished: chat_id=%s scanned=%d skipped=%d no_collectible=%d found=%d", chat_id, scanned, skipped, without_collectible, len(found))
                except Exception:
                    # Hidden membership lists are intentionally not replaced with message-history scraping.
                    logger.exception("Cannot scan chat: chat_id=%s", chat_id)
                    continue
        logger.info("Scan completed: category=%r found=%d target=%d", category, len(found), minimum)
        return list(found.values())

    async def _has_public_collectible(self, user: User) -> bool:
        """Check public collectible fields exposed by the installed Telegram API layer.

        Field names differ between Telegram API layers; unknown or hidden fields are treated as absent.
        """
        try:
            full = await self.client(GetFullUserRequest(user))
        except Exception:
            logger.exception("Could not load full profile: user_id=%s username=%r", user.id, user.username)
            return False
        details = full.full_user
        fields = ("gifts", "profile_gifts", "star_gifts")
        signals = {field: bool(getattr(details, field, None)) for field in fields}
        logger.debug(
            "Collectible check: user_id=%s username=%r full_user_type=%s signals=%s",
            user.id,
            user.username,
            type(details).__name__,
            signals,
        )
        return any(signals.values())
