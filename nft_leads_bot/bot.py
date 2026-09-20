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

SEARCH = "🔎 Поиск"
HISTORY = "🕘 Моя история"
BACK = "⬅️ Назад"
logger = logging.getLogger(__name__)


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=SEARCH), KeyboardButton(text=HISTORY)]],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
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
    builder.button(text="Следующий", callback_data=f"next:{category_index}")
    builder.button(text=BACK, callback_data="back")
    builder.adjust(1)
    return builder.as_markup()


def format_lead(lead: Lead) -> str:
    handle = f"@{escape(lead.username)}"
    return (
        "<b>Найден профиль с NFT-подарком</b>\n"
        f"Имя: {escape(lead.display_name)}\n"
        f"Юзернейм: {handle}\n"
        f"Telegram ID: <code>{lead.telegram_id}</code>\n"
        f"Категория: {escape(lead.category)}"
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
        await message.answer("Выберите **🔎 Поиск**, затем категорию для поиска.", reply_markup=main_menu(), parse_mode="Markdown")

    async def show_categories(self, message: Message) -> None:
        logger.info("Search menu requested: operator_id=%s", message.from_user.id)
        await message.answer("Выберите категорию для поиска:", reply_markup=categories_keyboard(self.settings))

    async def back(self, query: CallbackQuery) -> None:
        logger.info("Back selected: operator_id=%s", query.from_user.id)
        await query.answer()
        await query.message.edit_text("Выберите действие в меню ниже.")

    async def select_category(self, query: CallbackQuery) -> None:
        await query.answer("Подготавливаю очередь…")
        index = int(query.data.split(":", 1)[1])
        categories = list(self.settings.categories.items())
        if index not in range(len(categories)):
            await query.message.edit_text("Неизвестная категория.")
            return
        category, chat_ids = categories[index]
        logger.info("Category selected: operator_id=%s category=%r chats=%s", query.from_user.id, category, chat_ids)
        await query.message.edit_text("Сканирую доступных участников и заполняю вашу очередь…")
        scan_state_category = f"{category}:{self.settings.scan_revision}"
        known_member_ids = self.storage.scanned_member_ids(query.from_user.id, scan_state_category)
        result = await self.scanner.prefetch(
            category,
            chat_ids,
            self.settings.batch_size,
            known_member_ids,
            self.settings.profile_check_limit,
        )
        self.storage.mark_members_scanned(query.from_user.id, scan_state_category, result.checked_member_ids)
        logger.info("Prefetch complete: operator_id=%s category=%r participants=%d new_checked=%d known_skipped=%d candidates=%d", query.from_user.id, category, result.participant_count, len(result.checked_member_ids), result.skipped_known_count, len(result.candidates))
        self.storage.save_candidates(query.from_user.id, result.candidates)
        await self._send_next(query, category, index, scanned=len(result.candidates))

    async def next_lead(self, query: CallbackQuery) -> None:
        logger.info("Next selected: operator_id=%s", query.from_user.id)
        await query.answer()
        index = int(query.data.split(":", 1)[1])
        categories = list(self.settings.categories)
        if index not in range(len(categories)):
            await query.message.edit_text("Неизвестная категория.")
            return
        await self._send_next(query, categories[index], index)

    async def _send_next(self, query: CallbackQuery, category: str, index: int, scanned: int | None = None) -> None:
        lead = self.storage.next_undelivered(query.from_user.id, category)
        if lead is None:
            logger.info("No queued lead: operator_id=%s category=%r", query.from_user.id, category)
            suffix = " Новых публичных профилей с NFT не найдено." if scanned is not None else " Очередь пуста — запустите новый поиск."
            await query.message.edit_text(f"Результаты закончились.{suffix}", reply_markup=categories_keyboard(self.settings))
            return
        self.storage.mark_delivered(query.from_user.id, lead.telegram_id)
        logger.info("Lead delivered: operator_id=%s user_id=%s category=%r", query.from_user.id, lead.telegram_id, category)
        await query.message.edit_text(format_lead(lead), reply_markup=next_keyboard(index), parse_mode="HTML")

    async def show_history(self, message: Message) -> None:
        logger.info("History requested: operator_id=%s", message.from_user.id)
        leads = self.storage.history(message.from_user.id)
        if not leads:
            await message.answer("История пока пуста.")
            return
        lines = ["<b>Выданные вам профили</b>"]
        for lead in leads:
            handle = f"@{escape(lead.username)}" if lead.username else "без юзернейма"
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
