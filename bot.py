"""Instagram Analyzer Telegram Bot — main entry point."""

import asyncio
import logging
import os
import sys
import math

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, BufferedInputFile, FSInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
from dotenv import load_dotenv

from config import BOT_TOKEN, ADMIN_ID, MAX_ZIP_SIZE_BYTES, PAGE_SIZE, TEMP_DIR
from database import init_db, upsert_user, save_analysis, get_last_analysis, get_admin_stats
from instagram_parser import process_zip, cleanup_user_files, ParseError
from card_generator import generate_stats_card
from keyboards import (
    main_menu_keyboard, results_keyboard,
    pagination_keyboard, back_to_results_keyboard,
)
from texts import (
    START_MESSAGE, INSTRUCTION_MESSAGE, INSTRUCTION_IMAGE_NOTE,
    ANALYZING_MESSAGE, HELP_MESSAGE,
)

# Load .env
load_dotenv()

# Token lookup
_token = BOT_TOKEN if BOT_TOKEN else os.getenv("BOT_TOKEN", "")

if not _token:
    print("❌ BOT_TOKEN не задан. Создайте файл .env с BOT_TOKEN=ваш_токен")
    sys.exit(1)

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Bot & dispatcher
bot = Bot(token=_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# In-memory cache for last analysis per user
user_results: dict[int, dict] = {}


# FSM for search
class SearchState(StatesGroup):
    waiting_for_query = State()


# ─── Handlers ────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    await upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(START_MESSAGE, reply_markup=main_menu_keyboard())


@router.message(Command("help"))
@router.message(F.text.in_(["❓ Помощь", "❓ Допомога"]))
async def cmd_help(message: Message):
    await message.answer(HELP_MESSAGE)


@router.message(Command("instruction"))
@router.message(F.text.in_(["📋 Инструкция", "📋 Інструкція"]))
async def cmd_instruction(message: Message):
    await message.answer(INSTRUCTION_MESSAGE + INSTRUCTION_IMAGE_NOTE)


@router.message(F.text.in_(["📦 Загрузить архив", "📦 Завантажити архів"]))
async def cmd_upload(message: Message):
    await message.answer(
        "📦 <b>Отправь мне ZIP-архив</b> Instagram или отдельные файлы <code>.json</code> / <code>.html</code>.\n\n"
        "Я распакую данные и сразу покажу подробную статистику!",
    )


@router.message(Command("stats"))
@router.message(F.text.in_(["📊 Последний результат", "📊 Останній результат"]))
async def cmd_last_stats(message: Message):
    uid = message.from_user.id
    if uid in user_results:
        stats = user_results[uid]
        text = _format_stats_text(stats)
        await message.answer(text, reply_markup=results_keyboard())
    else:
        # Check database
        db_stat = await get_last_analysis(uid)
        if db_stat:
            stats = {
                "followers": db_stat["followers_count"],
                "following": db_stat["following_count"],
                "mutual": db_stat["mutual_count"],
                "not_following_back": db_stat["not_following_back_count"],
                "not_followed_back": db_stat["not_followed_back_count"],
            }
            text = _format_stats_text(stats)
            await message.answer(text, reply_markup=results_keyboard())
        else:
            await message.answer("У тебя еще нет сохраненных результатов. Отправь ZIP-архив Instagram!")


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if message.from_user.id != admin_id:
        return
    stats = await get_admin_stats()
    
    text_lines = [
        "📈 <b>Админ-статистика бота</b>\n",
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>",
        f"📊 Всего анализов: <b>{stats['total_analyses']}</b>",
        f"🟢 Активных за 7 дней: <b>{stats['active_last_7_days']}</b>\n",
    ]

    recent = stats.get("recent_users", [])
    if recent:
        text_lines.append("👤 <b>Последние пользователи:</b>")
        for idx, (uid, uname, fname, count) in enumerate(recent, start=1):
            name_display = f"@{uname}" if uname else (fname or f"ID {uid}")
            text_lines.append(f"{idx}. {name_display} — анализов: {count}")
    
    await message.answer("\n".join(text_lines))


# ─── In-memory storage for JSON/HTML individual files ────────────────────────
pending_json: dict[int, dict] = {}

TELEGRAM_DOWNLOAD_LIMIT = 20 * 1024 * 1024  # 20 MB


# ─── Document Handler ────────────────────────────────────────────────────────

@router.message(F.document)
async def handle_document(message: Message):
    doc = message.document
    fname = (doc.file_name or "").lower()

    # ── JSON / HTML single files ──
    if fname.endswith(".json") or fname.endswith(".html"):
        await _handle_single_file(message)
        return

    # ── ZIP archive ──
    if not fname.endswith(".zip"):
        await message.answer(
            "⚠️ Пожалуйста, отправь <b>ZIP-архив</b> или отдельные файлы <b>JSON / HTML</b> "
            "(например, <code>followers_1.json</code> или <code>followers.html</code>).\n\n"
            "Если не знаешь, как их получить — нажми <b>📋 Инструкция</b>."
        )
        return

    if doc.file_size and doc.file_size > MAX_ZIP_SIZE_BYTES:
        await message.answer(
            f"⚠️ Файл слишком большой (макс. {MAX_ZIP_SIZE_BYTES // (1024*1024)} МБ).\n"
            "Попробуй запросить архив только с разделом «Подписчики и подписки»."
        )
        return

    if doc.file_size and doc.file_size > TELEGRAM_DOWNLOAD_LIMIT:
        await message.answer(
            "⚠️ Файл больше <b>20 МБ</b> — это ограничение самого Telegram для ботов.\n\n"
            "🔧 <b>Есть два простых решения:</b>\n\n"
            "1️⃣ Запросить архив в Instagram <b>только с разделом «Подписчики и подписки»</b> "
            "— он будет весить меньше 1 МБ!\n\n"
            "2️⃣ Или распаковать этот ZIP на компьютере/телефоне, открыть папку "
            "<code>followers_and_following</code> и отправить мне файлы "
            "<b>followers_1.json</b> и <b>following.json</b> прямо сюда.\n\n"
            "📋 Нажми <b>📋 Инструкция</b> для подробностей."
        )
        return

    await _process_zip(message)


async def _handle_single_file(message: Message):
    """Handle individual JSON / HTML files."""
    doc = message.document
    fname = (doc.file_name or "").lower()
    uid = message.from_user.id

    is_followers = fname.startswith("followers") and not fname.startswith("following")
    is_following = fname.startswith("following")

    if not is_followers and not is_following:
        await message.answer(
            "⚠️ Не удалось определить тип этого файла.\n\n"
            "Мне нужны файлы из папки <code>followers_and_following</code>:\n"
            "• <b>followers_1.json</b> (или followers.html)\n"
            "• <b>following.json</b> (или following.html)"
        )
        return

    json_path = os.path.join(TEMP_DIR, f"{uid}_{fname}")
    try:
        await bot.download(doc, destination=json_path)

        from instagram_parser import parse_instagram_files
        usernames = parse_instagram_files([json_path])

        if not usernames:
            await message.answer(
                f"⚠️ В файле <b>{doc.file_name}</b> не найдено ни одного аккаунта.\n"
                "Убедись, что это файл из раздела «Подписчики и подписки»."
            )
            return

        if uid not in pending_json:
            pending_json[uid] = {"followers": [], "following": []}

        if is_followers:
            pending_json[uid]["followers"].extend(usernames)
            pending_json[uid]["followers"] = list(dict.fromkeys(pending_json[uid]["followers"]))
            followers_count = len(pending_json[uid]["followers"])
            following_count = len(pending_json[uid]["following"])

            msg = (
                f"✅ <b>{doc.file_name}</b> принят (+{len(usernames)} аккаунтов).\n"
                f"📊 Сейчас собрано: подписчиков — <b>{followers_count}</b>, подписок — <b>{following_count}</b>.\n\n"
            )
            if following_count == 0:
                msg += "👉 Теперь отправь <b>following.json</b> (или following.html)."
            else:
                msg += "💡 Если есть еще файлы <code>followers_2.json</code> — отправь их, или жми «Анализировать» 👇"

            await message.answer(
                msg,
                reply_markup=_analyze_json_keyboard() if following_count > 0 else None,
            )
        else:
            pending_json[uid]["following"].extend(usernames)
            pending_json[uid]["following"] = list(dict.fromkeys(pending_json[uid]["following"]))
            followers_count = len(pending_json[uid]["followers"])
            following_count = len(pending_json[uid]["following"])

            msg = (
                f"✅ <b>{doc.file_name}</b> принят (+{len(usernames)} аккаунтов).\n"
                f"📊 Сейчас собрано: подписчиков — <b>{followers_count}</b>, подписок — <b>{following_count}</b>.\n\n"
            )
            if followers_count == 0:
                msg += "👉 Теперь отправь <b>followers_1.json</b> (или followers.html)."
            else:
                msg += "💡 Если все файлы загружены — жми кнопку ниже 👇"

            await message.answer(
                msg,
                reply_markup=_analyze_json_keyboard() if followers_count > 0 else None,
            )

    except Exception as e:
        logger.exception("Error processing single file for user %s", uid)
        await message.answer("❌ Не удалось прочитать файл. Проверь корректность выгрузки Instagram.")
    finally:
        if os.path.exists(json_path):
            os.remove(json_path)


def _analyze_json_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Анализировать", callback_data="analyze:json")],
        [InlineKeyboardButton(text="📥 Добавить еще файл", callback_data="noop")],
    ])


@router.callback_query(F.data == "analyze:json")
async def handle_analyze_json(callback: CallbackQuery):
    uid = callback.from_user.id
    if uid not in pending_json or not pending_json[uid]["followers"] or not pending_json[uid]["following"]:
        await callback.answer("Сначала отправь файлы подписчиков и подписок.", show_alert=True)
        return

    await callback.answer("⏳ Анализирую...")

    from instagram_parser import analyze

    data = pending_json.pop(uid)
    result = analyze(data["followers"], data["following"])
    user_results[uid] = result

    await save_analysis(
        uid,
        {
            "followers": result["followers"],
            "following": result["following"],
            "mutual": result["mutual"],
            "not_following_back": result["not_following_back"],
            "not_followed_back": result["not_followed_back"],
        },
        result["followers_list"],
        result["following_list"],
    )

    text = _format_stats_text(result)
    await callback.message.answer(text, reply_markup=results_keyboard())


async def _process_zip(message: Message):
    """Process a ZIP file upload."""
    doc = message.document
    status_msg = await message.answer(ANALYZING_MESSAGE)

    uid = message.from_user.id
    zip_path = os.path.join(TEMP_DIR, f"{uid}.zip")

    try:
        await bot.download(doc, destination=zip_path)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, process_zip, zip_path, uid)

        user_results[uid] = result

        await save_analysis(
            uid,
            {
                "followers": result["followers"],
                "following": result["following"],
                "mutual": result["mutual"],
                "not_following_back": result["not_following_back"],
                "not_followed_back": result["not_followed_back"],
            },
            result["followers_list"],
            result["following_list"],
        )

        text = _format_stats_text(result)
        await status_msg.edit_text(text, reply_markup=results_keyboard())

    except ParseError as e:
        await status_msg.edit_text(str(e))
    except TelegramBadRequest as e:
        if "file is too big" in str(e).lower():
            await status_msg.edit_text(
                "⚠️ Файл больше <b>20 МБ</b> — ограничение Telegram.\n\n"
                "🔧 Распакуй ZIP и пришли мне файлы "
                "<b>followers_1.json</b> и <b>following.json</b> отдельно."
            )
        else:
            raise
    except Exception as e:
        logger.exception("Error processing ZIP for user %s", uid)
        await status_msg.edit_text(
            "❌ Произошла ошибка при обработке архива.\n"
            "Попробуй еще раз или проверь инструкцию."
        )
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
        cleanup_user_files(uid)


# ─── Callback Handlers ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("list:"))
async def handle_list_view(callback: CallbackQuery):
    uid = callback.from_user.id
    if uid not in user_results:
        await callback.answer("Результатов нет в памяти. Отправь архив еще раз.", show_alert=True)
        return

    parts = callback.data.split(":")
    list_type = parts[1]
    page = int(parts[2])

    result = user_results[uid]

    type_map = {
        "not_following_back": ("😤 Не подписаны в ответ", result["not_following_back_list"]),
        "not_followed_back": ("👤 Ты не подписан в ответ", result["not_followed_back_list"]),
        "mutual": ("🤝 Взаимные подписки", result["mutual_list"]),
    }

    if list_type not in type_map:
        await callback.answer("Неизвестный тип списка", show_alert=True)
        return

    title, items = type_map[list_type]
    total_pages = max(1, math.ceil(len(items) / PAGE_SIZE))
    page = min(page, total_pages - 1)

    start_idx = page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_items = items[start_idx:end_idx]

    if not items:
        text = f"<b>{title}</b>\n\n✅ Список пуст!"
    else:
        lines = [f"<b>{title}</b> ({len(items)} аккаунтов)\n"]
        for i, username in enumerate(page_items, start=start_idx + 1):
            lines.append(f"{i}. @{username}")
        text = "\n".join(lines)

    await callback.message.edit_text(
        text,
        reply_markup=pagination_keyboard(list_type, page, total_pages),
    )
    await callback.answer()


@router.callback_query(F.data == "back:results")
async def handle_back_to_results(callback: CallbackQuery):
    uid = callback.from_user.id
    if uid not in user_results:
        await callback.answer("Результаты не найдены.", show_alert=True)
        return

    text = _format_stats_text(user_results[uid])
    await callback.message.edit_text(text, reply_markup=results_keyboard())
    await callback.answer()


@router.callback_query(F.data == "card:generate")
async def handle_card_generate(callback: CallbackQuery):
    uid = callback.from_user.id
    if uid not in user_results:
        await callback.answer("Результаты не найдены.", show_alert=True)
        return

    await callback.answer("⏳ Генерирую карточку...")

    result = user_results[uid]
    
    # Get user username and bot username for personalization & branding
    user_name = callback.from_user.username or callback.from_user.first_name or "Instagram"
    try:
        bot_info = await bot.get_me()
        bot_uname = f"@{bot_info.username}" if bot_info.username else "@InstagramAnalyzerBot"
    except Exception:
        bot_uname = "@InstagramAnalyzerBot"

    card_buf = generate_stats_card(result, username=user_name, bot_username=bot_uname)
    photo = BufferedInputFile(card_buf.read(), filename="instagram_stats.png")
    await callback.message.answer_photo(
        photo,
        caption="🖼 <b>Твоя статистика Instagram</b>\nПоделись ею с друзьями или выложи в сторис!",
    )


@router.callback_query(F.data == "export:txt")
async def handle_export_txt(callback: CallbackQuery):
    uid = callback.from_user.id
    if uid not in user_results:
        await callback.answer("Результаты не найдены.", show_alert=True)
        return

    result = user_results[uid]
    lines = []
    lines.append("=== Instagram Analyzer — Результаты анализа ===\n")
    lines.append(f"Подписчики: {result['followers']}")
    lines.append(f"Подписки: {result['following']}")
    lines.append(f"Взаимные: {result['mutual']}")
    lines.append(f"Не подписаны в ответ: {result['not_following_back']}")
    lines.append(f"Ты не подписан в ответ: {result['not_followed_back']}")
    lines.append("")

    lines.append("\n--- НЕ ПОДПИСАНЫ В ОТВЕТ ---")
    for u in result["not_following_back_list"]:
        lines.append(f"@{u}")

    lines.append("\n--- ТЫ НЕ ПОДПИСАН В ОТВЕТ ---")
    for u in result["not_followed_back_list"]:
        lines.append(f"@{u}")

    lines.append("\n--- ВЗАИМНЫЕ ПОДПИСКИ ---")
    for u in result["mutual_list"]:
        lines.append(f"@{u}")

    content = "\n".join(lines)
    doc = BufferedInputFile(content.encode("utf-8"), filename="instagram_analysis.txt")
    await callback.message.answer_document(doc, caption="📄 Экспорт результатов в TXT")
    await callback.answer()


@router.callback_query(F.data == "search:start")
async def handle_search_start(callback: CallbackQuery, state: FSMContext):
    uid = callback.from_user.id
    if uid not in user_results:
        await callback.answer("Результатов нет.", show_alert=True)
        return

    await state.set_state(SearchState.waiting_for_query)
    await callback.message.answer(
        "🔍 Введи <b>username</b> для поиска среди результатов.\n"
        "Например: <code>johndoe</code>"
    )
    await callback.answer()


@router.message(SearchState.waiting_for_query)
async def handle_search_query(message: Message, state: FSMContext):
    uid = message.from_user.id
    if uid not in user_results:
        await message.answer("Результаты не найдены. Отправь архив снова.")
        await state.clear()
        return

    query = message.text.strip().lower().lstrip("@")
    result = user_results[uid]

    found_in = []
    if query in result.get("not_following_back_list", []):
        found_in.append("😤 Не подписан на тебя в ответ")
    if query in result.get("not_followed_back_list", []):
        found_in.append("👤 Ты не подписан в ответ")
    if query in result.get("mutual_list", []):
        found_in.append("🤝 Взаимная подписка")

    if found_in:
        text = f"🔍 <b>@{query}</b> найден:\n\n" + "\n".join(f"• {f}" for f in found_in)
    else:
        in_followers = query in [u.lower() for u in result.get("followers_list", [])]
        in_following = query in [u.lower() for u in result.get("following_list", [])]

        if in_followers or in_following:
            parts = []
            if in_followers:
                parts.append("подписан на тебя")
            if in_following:
                parts.append("ты подписан")
            text = f"🔍 <b>@{query}</b>: {', '.join(parts)}"
        else:
            text = f"🔍 <b>@{query}</b> не найден среди подписчиков и подписок."

    await message.answer(text, reply_markup=back_to_results_keyboard())
    await state.clear()


@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery):
    await callback.answer()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _format_stats_text(stats: dict) -> str:
    return (
        f"📊 <b>Результаты анализа Instagram</b>\n\n"
        f"👥 Подписчики: <b>{stats['followers']}</b>\n"
        f"📝 Подписки: <b>{stats['following']}</b>\n"
        f"🤝 Взаимные: <b>{stats['mutual']}</b>\n\n"
        f"😤 Не подписаны в ответ: <b>{stats['not_following_back']}</b>\n"
        f"👤 Ты не подписан в ответ: <b>{stats['not_followed_back']}</b>\n\n"
        f"Нажми кнопку ниже, чтобы посмотреть списки аккаунтов 👇"
    )


# ─── Web server & Keep-Alive ping for Render ─────────────────────────────────

async def health_check_handler(request):
    """Health check endpoint for Render Web Service."""
    return web.Response(text="Instagram Analyzer Bot is running OK!\n")


async def keep_alive_ping():
    """Periodically ping self to prevent Render Free tier from sleeping."""
    # Wait 60s after startup
    await asyncio.sleep(60)

    # Render automatically injects RENDER_EXTERNAL_URL (e.g. https://your-app.onrender.com)
    url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("PING_URL")
    if not url:
        logger.info("Keep-alive ping: RENDER_EXTERNAL_URL not set (not needed locally).")
        return

    target = f"{url.rstrip('/')}/health"
    logger.info("Keep-alive self-ping activated: %s (interval: 10 min)", target)

    import aiohttp
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(target, timeout=20) as resp:
                    logger.info("Keep-alive ping sent to %s [status: %s]", target, resp.status)
            except Exception as e:
                logger.warning("Keep-alive ping failed: %s", e)
            # Render sleeps after 15 min of inactivity; ping every 10 min (600s)
            await asyncio.sleep(600)


# ─── Main ────────────────────────────────────────────────────────────────────

async def main():
    await init_db()
    logger.info("Bot starting...")

    # If running on Render as a Web Service, bind to $PORT for health checks
    port_str = os.getenv("PORT")
    if port_str:
        try:
            port = int(port_str)
            app = web.Application()
            app.router.add_get("/", health_check_handler)
            app.router.add_get("/health", health_check_handler)
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", port)
            await site.start()
            logger.info("Health-check web server started on port %s", port)
        except Exception as e:
            logger.warning("Could not start web health-check server: %s", e)

    # Launch background keep-alive self-ping
    asyncio.create_task(keep_alive_ping())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
