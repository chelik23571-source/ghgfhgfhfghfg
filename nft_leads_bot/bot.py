from __future__ import annotations

import logging
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from nft_leads_bot.config import Settings
from nft_leads_bot.scanner import ConsentScanner
from nft_leads_bot.storage import Lead, Storage

SEARCH = "🔎 Search"
HISTORY = "🕘 My history"
BACK = "⬅️ Back"
logger = logging.getLogger(__name__)


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=SEARCH), KeyboardButton(text=HISTORY)]],
        resize_keyboard=True,
        input_field_placeholder="Choose an action",
    )


def categories_keyboard(settings: Settings):
    builder = InlineKeyboardBuilder()
    for index, category in enumerate(settings.categories):
        builder.button(text=category, callback_data=f"category:{index}")
    builder.button(text=BACK, callback_data="back")
    builder.adjust(1)
    return builder.as_markup()


def next_keyboard(category_index: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="Next", callback_data=f"next:{category_index}")
    builder.button(text=BACK, callback_data="back")
    builder.adjust(1)
    return builder.as_markup()


def format_lead(lead: Lead) -> str:
    handle = f"@{escape(lead.username)}" if lead.username else "No public username"
    return (
        "<b>Public collectible profile found</b>\n"
        f"Name: {escape(lead.display_name)}\n"
        f"Username: {handle}\n"
        f"Telegram ID: <code>{lead.telegram_id}</code>\n"
        f"Category: {escape(lead.category)}"
    )


class LeadBot:
    def __init__(self, settings: Settings, storage: Storage, scanner: ConsentScanner) -> None:
        self.settings = settings
        self.storage = storage
        self.scanner = scanner
        self.dp = Dispatcher()
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.dp.message.register(self.welcome, CommandStart())
        self.dp.message.register(self.show_categories, F.text == SEARCH)
        self.dp.message.register(self.show_history, F.text == HISTORY)
        self.dp.callback_query.register(self.back, F.data == "back")
        self.dp.callback_query.register(self.select_category, F.data.startswith("category:"))
        self.dp.callback_query.register(self.next_lead, F.data.startswith("next:"))

    async def welcome(self, message: Message) -> None:
        logger.info("Start command: operator_id=%s", message.from_user.id)
        await message.answer("Choose **Search** to select an approved category.", reply_markup=main_menu(), parse_mode="Markdown")

    async def show_categories(self, message: Message) -> None:
        logger.info("Search menu requested: operator_id=%s", message.from_user.id)
        await message.answer("Select a category to search:", reply_markup=categories_keyboard(self.settings))

    async def back(self, query: CallbackQuery) -> None:
        logger.info("Back selected: operator_id=%s", query.from_user.id)
        await query.answer()
        await query.message.edit_text("Use the menu below to choose another action.")

    async def select_category(self, query: CallbackQuery) -> None:
        await query.answer("Preparing the next batch…")
        index = int(query.data.split(":", 1)[1])
        categories = list(self.settings.categories.items())
        if index not in range(len(categories)):
            await query.message.edit_text("Unknown category.")
            return
        category, chat_ids = categories[index]
        logger.info("Category selected: operator_id=%s category=%r chats=%s", query.from_user.id, category, chat_ids)
        await query.message.edit_text("Scanning approved visible participant lists and filling your queue…")
        candidates = await self.scanner.prefetch(category, chat_ids, self.settings.batch_size)
        logger.info("Prefetch complete: operator_id=%s category=%r candidates=%d", query.from_user.id, category, len(candidates))
        self.storage.save_candidates(candidates)
        await self._send_next(query, category, index, scanned=len(candidates))

    async def next_lead(self, query: CallbackQuery) -> None:
        logger.info("Next selected: operator_id=%s", query.from_user.id)
        await query.answer()
        index = int(query.data.split(":", 1)[1])
        categories = list(self.settings.categories)
        if index not in range(len(categories)):
            await query.message.edit_text("Unknown category.")
            return
        await self._send_next(query, categories[index], index)

    async def _send_next(self, query: CallbackQuery, category: str, index: int, scanned: int | None = None) -> None:
        lead = self.storage.next_undelivered(query.from_user.id, category)
        if lead is None:
            logger.info("No queued lead: operator_id=%s category=%r", query.from_user.id, category)
            suffix = " No new public collectible profiles were found." if scanned is not None else " The prefetched queue is empty; start a new search."
            await query.message.edit_text(f"No more results.{suffix}", reply_markup=categories_keyboard(self.settings))
            return
        self.storage.mark_delivered(query.from_user.id, lead.telegram_id)
        logger.info("Lead delivered: operator_id=%s user_id=%s category=%r", query.from_user.id, lead.telegram_id, category)
        await query.message.edit_text(format_lead(lead), reply_markup=next_keyboard(index), parse_mode="HTML")

    async def show_history(self, message: Message) -> None:
        logger.info("History requested: operator_id=%s", message.from_user.id)
        leads = self.storage.history(message.from_user.id)
        if not leads:
            await message.answer("Your history is empty.")
            return
        lines = ["<b>Your delivered profiles</b>"]
        for lead in leads:
            handle = f"@{escape(lead.username)}" if lead.username else f"ID {lead.telegram_id}"
            lines.append(f"• {escape(lead.display_name)} — {handle} ({escape(lead.category)})")
        await message.answer("\n".join(lines), parse_mode="HTML")

    async def run(self) -> None:
        logger.info("Starting bot polling")
        await self.scanner.start()
        bot = Bot(self.settings.bot_token)
        try:
            await self.dp.start_polling(bot)
        finally:
            logger.info("Stopping bot polling")
            await self.scanner.stop()
            await bot.session.close()
