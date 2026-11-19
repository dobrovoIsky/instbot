"""Keyboard builders for the bot."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Main reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Инструкция"), KeyboardButton(text="📦 Загрузить архив")],
            [KeyboardButton(text="📊 Последний результат"), KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
    )


def results_keyboard() -> InlineKeyboardMarkup:
    """Inline keyboard for viewing analysis results."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="😤 Не подписаны в ответ", callback_data="list:not_following_back:0"),
        ],
        [
            InlineKeyboardButton(text="👤 Ты не подписан в ответ", callback_data="list:not_followed_back:0"),
        ],
        [
            InlineKeyboardButton(text="🤝 Взаимные подписки", callback_data="list:mutual:0"),
        ],
        [
            InlineKeyboardButton(text="🔍 Поиск", callback_data="search:start"),
            InlineKeyboardButton(text="📄 Экспорт TXT", callback_data="export:txt"),
        ],
        [
            InlineKeyboardButton(text="🖼 Карточка статистики", callback_data="card:generate"),
        ],
    ])


def pagination_keyboard(list_type: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Pagination for lists."""
    buttons = []

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"list:{list_type}:{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"list:{list_type}:{page + 1}"))

    buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="🔙 Назад к результатам", callback_data="back:results")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_to_results_keyboard() -> InlineKeyboardMarkup:
    """Single back button."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад к результатам", callback_data="back:results")],
    ])
