from __future__ import annotations

import asyncio
from collections.abc import Iterable

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import User

from .storage import Lead


class ConsentScanner:
    """Scans only participant lists that Telegram exposes to the approved account."""

    def __init__(self, api_id: int, api_hash: str, session: str) -> None:
        self.client = TelegramClient(StringSession(session), api_id, api_hash)
        self._scan_lock = asyncio.Lock()

    async def start(self) -> None:
        await self.client.connect()
        if not await self.client.is_user_authorized():
            raise RuntimeError("TELETHON_SESSION_STRING is not authorized")

    async def stop(self) -> None:
        await self.client.disconnect()

    async def prefetch(self, category: str, chat_ids: Iterable[int], minimum: int) -> list[Lead]:
        """Return up to `minimum` visible, opted-in members with public collectible data."""
        found: dict[int, Lead] = {}
        async with self._scan_lock:
            for chat_id in chat_ids:
                try:
                    entity = await self.client.get_entity(chat_id)
                    async for member in self.client.iter_participants(entity):
                        if not isinstance(member, User) or member.bot or member.deleted:
                            continue
                        if member.id in found or not await self._has_public_collectible(member):
                            continue
                        name = " ".join(part for part in (member.first_name, member.last_name) if part).strip()
                        found[member.id] = Lead(member.id, name or "Telegram user", member.username, category)
                        if len(found) >= minimum:
                            return list(found.values())
                except (ValueError, PermissionError):
                    # Hidden membership lists are intentionally not replaced with message-history scraping.
                    continue
        return list(found.values())

    async def _has_public_collectible(self, user: User) -> bool:
        """Check public collectible fields exposed by the installed Telegram API layer.

        Field names differ between Telegram API layers; unknown or hidden fields are treated as absent.
        """
        try:
            full = await self.client(GetFullUserRequest(user))
        except (ValueError, PermissionError):
            return False
        details = full.full_user
        return any(bool(getattr(details, field, None)) for field in ("gifts", "profile_gifts", "star_gifts"))
