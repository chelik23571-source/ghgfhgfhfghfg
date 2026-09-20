from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass

from telethon import TelegramClient, functions
from telethon.sessions import StringSession
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import User

from nft_leads_bot.storage import Lead

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanResult:
    candidates: list[Lead]
    checked_member_ids: set[int]
    participant_count: int
    skipped_known_count: int


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

    async def prefetch(
        self,
        category: str,
        chat_ids: Iterable[int],
        minimum: int,
        known_member_ids: set[int],
        profile_check_limit: int,
    ) -> ScanResult:
        """Check a new slice of visible members and return a prefetched candidate batch."""
        found: dict[int, Lead] = {}
        checked_member_ids: set[int] = set()
        chat_ids = list(chat_ids)
        participant_count = skipped_known_count = 0
        logger.info("Starting scan: category=%r chats=%s target=%d known=%d check_limit=%d", category, chat_ids, minimum, len(known_member_ids), profile_check_limit)
        async with self._scan_lock:
            for chat_id in chat_ids:
                scanned = skipped = without_collectible = 0
                try:
                    logger.info("Resolving chat: chat_id=%s", chat_id)
                    entity = await self.client.get_entity(chat_id)
                    logger.info("Participant scan started: chat_id=%s entity=%s", chat_id, type(entity).__name__)
                    async for member in self.client.iter_participants(entity):
                        scanned += 1
                        participant_count += 1
                        if not isinstance(member, User) or member.bot or member.deleted:
                            skipped += 1
                            logger.debug("Skipping participant: chat_id=%s id=%s bot=%s deleted=%s", chat_id, getattr(member, "id", None), getattr(member, "bot", None), getattr(member, "deleted", None))
                            continue
                        if member.id in known_member_ids or member.id in checked_member_ids:
                            skipped += 1
                            skipped_known_count += 1
                            logger.debug("Skipping previously checked participant: chat_id=%s user_id=%s", chat_id, member.id)
                            continue
                        checked_member_ids.add(member.id)
                        if not await self._has_public_collectible(member):
                            without_collectible += 1
                        else:
                            name = " ".join(part for part in (member.first_name, member.last_name) if part).strip()
                            found[member.id] = Lead(member.id, name or "Telegram user", member.username, category)
                            logger.info("Collectible profile found: chat_id=%s user_id=%s username=%r total=%d", chat_id, member.id, member.username, len(found))
                        if len(checked_member_ids) >= profile_check_limit:
                            logger.info("Profile check limit reached: checked=%d candidates=%d", len(checked_member_ids), len(found))
                            return ScanResult(list(found.values()), checked_member_ids, participant_count, skipped_known_count)
                    logger.info("Participant scan finished: chat_id=%s scanned=%d skipped=%d no_collectible=%d found=%d", chat_id, scanned, skipped, without_collectible, len(found))
                except Exception:
                    # Hidden membership lists are intentionally not replaced with message-history scraping.
                    logger.exception("Cannot scan chat: chat_id=%s", chat_id)
                    continue
        logger.info("Scan completed: category=%r participants=%d checked=%d known_skipped=%d candidates=%d", category, participant_count, len(checked_member_ids), skipped_known_count, len(found))
        return ScanResult(list(found.values()), checked_member_ids, participant_count, skipped_known_count)

    async def _has_public_collectible(self, user: User) -> bool:
        """Check public profile fields and Telegram's dedicated public-gifts method."""
        try:
            full = await self.client(GetFullUserRequest(user))
        except Exception:
            logger.exception("Could not load full profile: user_id=%s username=%r", user.id, user.username)
            details = None
        else:
            details = full.full_user
        fields = ("gifts", "profile_gifts", "star_gifts")
        signals = {field: bool(getattr(details, field, None)) for field in fields}
        star_gifts_count = await self._public_star_gifts_count(user)
        signals["get_user_star_gifts"] = star_gifts_count > 0
        logger.debug(
            "Collectible check: user_id=%s username=%r full_user_type=%s star_gifts_count=%d signals=%s",
            user.id,
            user.username,
            type(details).__name__ if details is not None else None,
            star_gifts_count,
            signals,
        )
        return any(signals.values())

    async def _public_star_gifts_count(self, user: User) -> int:
        """Return publicly displayed Star Gifts via Telegram's dedicated API endpoint.

        Gifts are not included in ``users.getFullUser`` on current Telegram API
        layers. The separate ``payments.getUserStarGifts`` request is therefore
        the authoritative public source for this check.
        """
        request_type = getattr(functions.payments, "GetUserStarGiftsRequest", None)
        if request_type is None:
            logger.warning(
                "Installed Telethon does not expose GetUserStarGiftsRequest; "
                "upgrade Telethon to detect public profile gifts"
            )
            return 0
        try:
            response = await self.client(request_type(user_id=user))
        except Exception:
            logger.exception("Could not load public Star Gifts: user_id=%s username=%r", user.id, user.username)
            return 0
        gifts = getattr(response, "gifts", ())
        count = len(gifts) if gifts is not None else 0
        logger.debug(
            "Public Star Gifts loaded: user_id=%s response_type=%s count=%d",
            user.id,
            type(response).__name__,
            count,
        )
        return count
