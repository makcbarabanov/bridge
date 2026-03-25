import os
import re
import logging
import asyncio
import socket
import aiohttp
from datetime import datetime, timezone
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ErrorEvent
from dotenv import load_dotenv

from Bloom import bloom_context

# Лимит Telegram на одно сообщение (символы Unicode)
TELEGRAM_MAX_MESSAGE = 4096

load_dotenv()

# === КОНФИГУРАЦИЯ (только из окружения / .env) ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_TELEGRAM_ID") or os.environ.get("ADMIN_ID") or "0")
GOOGLE_API_KEY = os.environ.get("GOOGLE_AI_KEY") or os.environ.get("GOOGLE_API_KEY")


def _parse_marathon_group_ids() -> set[int]:
    raw = os.environ.get("MARATHON_GROUP_IDS", "").strip()
    if not raw:
        return set()
    out: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.add(int(part))
        except ValueError:
            pass
    return out


MARATHON_GROUP_IDS = _parse_marathon_group_ids()

# Канон Блума: только каталог Bloom/ (см. bloom_context.py)
if os.environ.get("BLOOM_HOME"):
    bloom_context.set_bloom_home(os.environ["BLOOM_HOME"])

# Имя модели из list_models.py на сервере в поддерживаемом регионе (см. ai.google.dev).
# Старые имена вроде gemini-1.5-flash без суффикса часто дают 404 на новых ключах.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_MODEL_FALLBACK = (os.environ.get("GEMINI_MODEL_FALLBACK") or "").strip()
GEMINI_API_VERSION = os.environ.get("GEMINI_API_VERSION", "v1beta")

# Пауза перед повтором при 429 (секунды из текста ошибки «Please retry in …s»)
_RETRY_AFTER_RE = re.compile(r"retry in ([\d.]+)\s*s", re.I)

GEMINI_QUOTA_MSG = (
    "⏳ Лимит Gemini API (бесплатный тариф): исчерпана квота запросов по этой модели "
    "(часто 20 запросов в сутки на Gemini 2.5 Flash). Подожди сброса, подключи биллинг в Google AI Studio, "
    "или задай другую модель в .env: GEMINI_MODEL и при необходимости GEMINI_MODEL_FALLBACK. "
    "Справка: https://ai.google.dev/gemini-api/docs/rate-limits"
)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRAIN_DUMP_PATH = os.environ.get("BRAIN_DUMP_PATH") or os.path.join(_BASE_DIR, "brain_dump.txt")
_REMEMBER_TOKEN = re.compile(r"(?i)\bзапомни\b")

# Последний обмен: ключ (chat_id, user_id) — для «ЗАПОМНИ» без текста в сообщении
_last_exchange: dict[tuple[int, int], tuple[str, str]] = {}


def _strip_all_remember_keywords(text: str) -> str:
    return _REMEMBER_TOKEN.sub("", text).strip()


def _is_remember_only(text: str) -> bool:
    """Сообщение состоит только из «ЗАПОМНИ» (и пробелов/знаков)."""
    rest = _strip_all_remember_keywords(text)
    if not rest:
        return True
    return bool(re.fullmatch(r"[\s:;.\-!?…,]+", rest))


def _format_brain_block(user_question: str, bloom_answer: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        f"--- {ts} ---\n"
        f"Вопрос: {user_question}\n"
        f"Ответ Блум:\n{bloom_answer}\n\n"
    )


def _append_brain_dump(path: str, line: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


def _gemini_generate_url(model: str | None = None) -> str:
    if not GOOGLE_API_KEY:
        raise RuntimeError("Задай GOOGLE_AI_KEY или GOOGLE_API_KEY в .env")
    m = model or GEMINI_MODEL
    base = f"https://generativelanguage.googleapis.com/{GEMINI_API_VERSION}/models"
    return f"{base}/{m}:generateContent?key={GOOGLE_API_KEY}"


def _parse_retry_seconds(err_msg: str) -> float | None:
    match = _RETRY_AFTER_RE.search(err_msg or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _split_for_telegram(text: str, max_len: int = TELEGRAM_MAX_MESSAGE) -> list[str]:
    """Разбивает текст на части не длиннее max_len (по возможности по переносам строк)."""
    if len(text) <= max_len:
        return [text]
    parts: list[str] = []
    rest = text
    while rest:
        if len(rest) <= max_len:
            parts.append(rest)
            break
        chunk = rest[:max_len]
        nl = chunk.rfind("\n")
        if nl > max_len // 2:
            chunk = chunk[: nl + 1]
        parts.append(chunk)
        rest = rest[len(chunk) :]
    return parts


def _setup_logging() -> None:
    log_path = os.environ.get("BRIDGE_LOG_PATH") or os.path.join(_BASE_DIR, "bridge_bot.log")
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)
    logging.info("Логи: консоль + %s", log_path)


_setup_logging()
logger = logging.getLogger("bridge")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()


async def answer_long(message: types.Message, text: str) -> None:
    """Отправляет ответ, разбивая длинные ответы на несколько сообщений."""
    chunks = _split_for_telegram(text)
    for i, chunk in enumerate(chunks):
        await message.answer(chunk)
        if i > 0:
            logger.info("Отправлена продолжение ответа, часть %s/%s", i + 1, len(chunks))


@dp.error()
async def telegram_error_handler(event: ErrorEvent) -> None:
    logger.exception(
        "Необработанное исключение (update_id=%s): %s",
        event.update.update_id if event.update else None,
        event.exception,
    )
    msg = event.update.message if event.update else None
    if msg:
        try:
            await msg.answer(
                "⚠️ Внутренняя ошибка бота (см. лог на сервере: bridge_bot.log)."
            )
        except Exception:
            logger.exception("Не удалось отправить сообщение об ошибке пользователю")


# === ДОСТУП: личка только Макс; группы — только из MARATHON_GROUP_IDS ===


def _can_use_remember_private_admin(message: types.Message) -> bool:
    return (
        message.chat.type == "private"
        and message.from_user is not None
        and message.from_user.id == ADMIN_ID
    )


async def _group_triggers_bloom(message: types.Message) -> bool:
    """В группе отвечаем на /команды, @бота или реплай на сообщение бота."""
    if message.chat.type not in ("group", "supergroup"):
        return True
    text = message.text or message.caption or ""
    me = await bot.get_me()
    uname = (me.username or "").lower()

    if message.voice or message.audio:
        if message.reply_to_message and message.reply_to_message.from_user:
            if message.reply_to_message.from_user.id == me.id:
                return True
        if uname and text and f"@{uname}" in text.lower():
            return True
        return False

    if text.startswith("/"):
        return True
    if uname and f"@{uname}" in text.lower():
        return True
    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.id == me.id:
            return True
    return False


def _chat_allowed_for_bot(message: types.Message) -> bool:
    """Личка только админ; группы — только из MARATHON_GROUP_IDS."""
    if not message.from_user:
        return False
    uid = message.from_user.id
    chat_id = message.chat.id
    ctype = message.chat.type
    if ctype == "private":
        return uid == ADMIN_ID
    if ctype in ("group", "supergroup"):
        return chat_id in MARATHON_GROUP_IDS
    return False


# === ФУНКЦИЯ ЗАПРОСА (Bloom + архив памяти) ===
async def get_gemini_response(user_text: str) -> str:
    try:
        system = await asyncio.to_thread(bloom_context.load_system_instruction)
    except OSError as e:
        logger.warning("Bloom context: %s", e)
        system = "Ты Bloom — тёплый помощник марафона полезных привычек. Отвечай по-человечески."

    mem = await asyncio.to_thread(bloom_context.retrieve_memory_snippets, user_text)
    user_payload = user_text
    if mem:
        user_payload = (
            "Ниже — выдержки из архива переписки (опирайся на них, если уместно; "
            "не выдумывай факты, которых нет в тексте):\n\n"
            + mem
            + "\n\n---\n\nСообщение собеседника:\n"
            + user_text
        )

    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user_payload}]}],
    }

    models: list[str] = [GEMINI_MODEL]
    if GEMINI_MODEL_FALLBACK and GEMINI_MODEL_FALLBACK != GEMINI_MODEL:
        models.append(GEMINI_MODEL_FALLBACK)

    last_err = "Неизвестная ошибка"
    last_status = 0
    saw_429 = False

    try:
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        async with aiohttp.ClientSession(connector=connector) as session:
            for model in models:
                url = _gemini_generate_url(model)
                for attempt in range(3):
                    async with session.post(url, json=payload, timeout=120) as resp:
                        data = await resp.json()
                        err_msg = data.get("error", {}).get("message", "Неизвестная ошибка")
                        last_err = err_msg
                        last_status = resp.status

                        if resp.status == 200:
                            try:
                                return data["candidates"][0]["content"]["parts"][0]["text"]
                            except (KeyError, IndexError):
                                return "⚠️ Ошибка: Google прислал пустой или странный ответ."

                        if resp.status == 429:
                            saw_429 = True
                            delay = _parse_retry_seconds(err_msg)
                            if delay is None:
                                delay = min(3.0 * (attempt + 1), 60.0)
                            delay = min(max(delay, 0.5), 120.0)
                            if attempt < 2:
                                logger.warning(
                                    "Gemini 429, пауза %.1fs и повтор (модель %s, попытка %s/3)",
                                    delay,
                                    model,
                                    attempt + 1,
                                )
                                await asyncio.sleep(delay + 0.5)
                                continue
                            logger.warning("Gemini 429: переход к следующей модели или исчерпание попыток")
                            break

                        return f"💥 ОШИБКА API ({resp.status}): {err_msg}"

            if saw_429 or last_status == 429:
                return GEMINI_QUOTA_MSG
            return f"💥 ОШИБКА API ({last_status}): {last_err}"

    except Exception as e:
        return f"💥 СБОЙ СЕТИ: {str(e)}"


# === ОБРАБОТЧИКИ ===


@dp.message(Command("start"))
async def start_handler(message: types.Message):
    if message.chat.type in ("group", "supergroup"):
        if message.chat.id in MARATHON_GROUP_IDS:
            me = await bot.get_me()
            un = f"@{me.username}" if me.username else "бота"
            await message.answer(
                f"🌸 Привет! Я Bloom. Напиши мне в ответ на моё сообщение или упомяни {un} "
                f"— помогу с марафоном привычек и добрых дел."
            )
        return
    if message.from_user and message.from_user.id == ADMIN_ID:
        await message.answer(
            f"💎 МОСТ АКТИВИРОВАН ({GEMINI_API_VERSION}, {GEMINI_MODEL}). Блум на связи, Макс."
        )


@dp.message(Command("help"))
@dp.message(Command("bloom"))
async def help_bloom(message: types.Message):
    if message.chat.type in ("group", "supergroup") and message.chat.id not in MARATHON_GROUP_IDS:
        return
    if message.chat.type == "private" and (not message.from_user or message.from_user.id != ADMIN_ID):
        return
    me = await bot.get_me()
    un = f"@{me.username}" if me.username else "бота"
    await message.answer(
        f"🌸 Я Bloom. Чтобы я ответила в группе марафона: ответь реплаем на моё сообщение "
        f"или упомяни {un}. В личке у Макса доступны все темы и команда «ЗАПОМНИ» для записи в файл."
    )


@dp.message(F.voice | F.audio)
async def voice_handler(message: types.Message):
    """Голос не расшифровываем — только текст в Gemini; отвечаем понятно, чтобы не было «тишины»."""
    if not _chat_allowed_for_bot(message):
        return
    if message.chat.type in ("group", "supergroup"):
        if not await _group_triggers_bloom(message):
            return

    await message.answer(
        "🎤 Голосовые я пока не расшифровываю — в мосте работает только текст. "
        "Напиши тем же вопросом сообщением.\n\n"
        "Если приходила ошибка 429 — это лимит бесплатного Gemini (запросов в день по модели мало); "
        "подожди сброса, смени GEMINI_MODEL в .env или включи биллинг в Google AI Studio."
    )


@dp.message(F.text)
async def message_handler(message: types.Message):
    if not message.from_user:
        return

    uid = message.from_user.id
    chat_id = message.chat.id
    ctype = message.chat.type

    if not _chat_allowed_for_bot(message):
        return
    if ctype in ("group", "supergroup") and not await _group_triggers_bloom(message):
        return

    await bot.send_chat_action(message.chat.id, "typing")

    text = message.text or ""
    ex_key = (chat_id, uid)

    # «ЗАПОМНИ» — только личка Макса (безопасность файла на сервере)
    if _REMEMBER_TOKEN.search(text) and not _can_use_remember_private_admin(message):
        await message.answer(
            "💬 Команда «ЗАПОМНИ» и запись в файл на сервере работают в **личном чате** с Максом. "
            "В группе я просто отвечаю как Bloom."
        )
        if ctype != "private":
            text = _REMEMBER_TOKEN.sub("", text).strip() or text

    # Только «ЗАПОМНИ» — сохраняем последний ответ Блум (не текст после слова)
    if _can_use_remember_private_admin(message) and _is_remember_only(text):
        ex = _last_exchange.get(ex_key)
        if not ex:
            await message.answer(
                "💬 Пока нечего сохранять: сначала задай вопрос без «ЗАПОМНИ», "
                "получи ответ Блум, потом напиши «ЗАПОМНИ»."
            )
            return
        user_q, bloom_a = ex
        block = _format_brain_block(user_q, bloom_a)
        try:
            await asyncio.to_thread(_append_brain_dump, BRAIN_DUMP_PATH, block)
            preview = bloom_a[:400] + ("…" if len(bloom_a) > 400 else "")
            await message.answer(
                f"💾 Сохранила ответ Блум в brain_dump.txt:\n«{preview}»\n\n"
                f"Файл: {BRAIN_DUMP_PATH}"
            )
        except OSError as e:
            await message.answer(f"⚠️ Не удалось записать файл: {e}")
        return

    # В сообщении есть «ЗАПОМНИ» и ещё текст — вопрос + просьба сохранить ответ на него
    if _can_use_remember_private_admin(message) and _REMEMBER_TOKEN.search(text):
        question = _strip_all_remember_keywords(text)
        if not question:
            await message.answer(
                "💬 Напиши вопрос в том же сообщении, что и «ЗАПОМНИ», "
                "или сначала поговори с Блум, а потом отдельным сообщением «ЗАПОМНИ»."
            )
            return

        response_text = await get_gemini_response(question)
        _last_exchange[ex_key] = (question, response_text)

        block = _format_brain_block(question, response_text)
        try:
            await asyncio.to_thread(_append_brain_dump, BRAIN_DUMP_PATH, block)
            note = "💾 Этот ответ Блум записан в brain_dump.txt.\n\n"
        except OSError as e:
            note = f"⚠️ Не удалось записать файл: {e}\n\n"

        await answer_long(message, note + response_text)
        return

    # Обычный диалог — запоминаем пару вопрос/ответ для следующего «ЗАПОМНИ» (личка)
    response_text = await get_gemini_response(text)
    if _can_use_remember_private_admin(message):
        _last_exchange[ex_key] = (text, response_text)
    await answer_long(message, response_text)


# === ЗАПУСК ===
async def main():
    if not TELEGRAM_TOKEN or not ADMIN_ID:
        raise RuntimeError("В .env нужны TELEGRAM_BOT_TOKEN и ADMIN_TELEGRAM_ID (или ADMIN_ID).")
    print("--- ИНИЦИАЛИЗАЦИЯ: ОПЕРАЦИЯ СТРЕЛА ---")
    print(f"🚀 Модель: {GEMINI_MODEL} ({GEMINI_API_VERSION})")
    if GEMINI_MODEL_FALLBACK:
        print(f"🔄 Запасная модель при исчерпании квоты: {GEMINI_MODEL_FALLBACK}")
    print("📡 Локация: Проверка связи...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Мост отключен.")
