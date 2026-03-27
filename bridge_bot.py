import os
import re
import logging
import asyncio
import socket
import aiohttp
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ErrorEvent
from dotenv import load_dotenv

from Bloom import bloom_context

import bloom_analytics_db
import bridge_participants
import dream_db

MSK = ZoneInfo("Europe/Moscow")
# Участники для утренних пингов по мечтам (telegram_id из БД / bridge_participants)
KOSTYA_TG = 858036788
SVETA_TG = 399807785
_campaign_scheduler = None  # ссылка на APScheduler, чтобы не собрал GC

# Упоминания для приветствия в группе марафона (одна строка; @Ola_life — один раз)
MARATHON_WELCOME_MENTIONS = (
    "@xxxASTRIDxxx @Foxikka @Elena_inspiratio @Guzel651 @writer_ksenia @TF85NN @MagdaV2 @Grey73 "
    "@olgasagura @kyb1409 @Kmihlnn @Aigul_star @Svetashcherbinina @VladimirKochergi @Alexey_Babenkof "
    "@anokovera @Svetik_Nasonova @Irina_logoped_defektolog @Nadezda_lada_roda @AlenaDumler "
    "@TaiisN1966 @alexeeva_natalli @Sofiya_Avram @mariya_muh @Dama_Dela @IrinaUsmanovaM "
    "@Albert_pro_aqua @Magic_Hands_in_spb @Indi_indi7 @katyrubik @prgptrp @Ola_life "
    "@Alex31031984 @Timur_Shamsudinov @Sergey_Stotskiy"
)

# Лимит Telegram на одно сообщение (символы Unicode)
TELEGRAM_MAX_MESSAGE = 4096

load_dotenv()

# === КОНФИГУРАЦИЯ (только из окружения / .env) ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_TELEGRAM_ID") or os.environ.get("ADMIN_ID") or "0")
# Gemini: PRIMARY_API_KEY или прежние имена
GOOGLE_API_KEY = (
    (os.environ.get("PRIMARY_API_KEY") or "").strip()
    or os.environ.get("GOOGLE_AI_KEY")
    or os.environ.get("GOOGLE_API_KEY")
    or ""
)


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

# Личка: по умолчанию Bloom отвечает всем. BRIDGE_PRIVATE_ADMIN_ONLY=1 — только ADMIN_ID (как раньше).
def _private_chat_admin_only() -> bool:
    return os.environ.get("BRIDGE_PRIVATE_ADMIN_ONLY", "").strip().lower() in ("1", "true", "yes")


# Канон Блума: только каталог Bloom/ (см. bloom_context.py)
if os.environ.get("BLOOM_HOME"):
    bloom_context.set_bloom_home(os.environ["BLOOM_HOME"])

# Имя модели из _py_/list_models.py на сервере в поддерживаемом регионе (см. ai.google.dev).
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

GEMINI_OVERLOAD_MSG = (
    "⏳ Сейчас у модели Gemini высокая нагрузка (503) — так бывает временно. "
    "Попробуй через несколько минут или повтори запрос. "
    "В .env можно указать GEMINI_MODEL_FALLBACK=другая_модель — иногда она отвечает, когда основная занята."
)

ALL_GATEWAYS_DOWN_MSG = (
    "⏳ Шлюзы перегружены, подожди пару минут — титан отдыхает."
)

_GEMINI_FAIL_TRY_GROQ = "__TRY_GROQ__"

# Groq (OpenAI-compatible): FALLBACK_API_KEY или GROQ_API_KEY
FALLBACK_BASE_URL_DEFAULT = "https://api.groq.com/openai/v1"
FALLBACK_MODEL_DEFAULT = "llama-3.3-70b-versatile"

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRAIN_DUMP_PATH = os.environ.get("BRAIN_DUMP_PATH") or os.path.join(_BASE_DIR, "brain_dump.txt")
_REMEMBER_TOKEN = re.compile(r"(?i)\bзапомни\b")

_FILENAME_SAFE = re.compile(r'[<>:"/\\|?*\n\r\t]+')


def _sanitize_filename_part(s: str) -> str:
    s = _FILENAME_SAFE.sub("_", s.strip() or "user")
    s = re.sub(r"\s+", " ", s)
    return (s[:100] + "…") if len(s) > 100 else s


def _guest_profile_folder_name(user: types.User) -> str:
    """Имя папки гостя: как раньше stem файла в dialogy — <имя>_<telegram_id>."""
    base = user.first_name or "user"
    return f"{_sanitize_filename_part(base)}_{user.id}"


def _resolve_guest_profile_dir(user: types.User) -> Path:
    """
    Папка профиля гостя: если уже есть user_profiles/*_<id>/ (в т.ч. после миграции) — её;
    иначе новая по текущему имени из Telegram.
    """
    base = Path(bridge_participants.USER_PROFILES)
    matches = sorted(base.glob(f"*_{user.id}"))
    for m in matches:
        if m.is_dir():
            return m
    return base / _guest_profile_folder_name(user)


def _resolve_dialogue_path(user: types.User) -> str:
    """
    Один лог на пользователя: user_profiles/<папка>/chat_history.txt.
    Участники — папка из bridge_participants; остальные — папка гостя *_<id>.
    """
    info = bridge_participants.resolve_participant(user)
    folder = info.get("folder")
    if folder:
        return str(
            Path(bridge_participants.USER_PROFILES)
            / folder
            / bridge_participants.DIALOG_LOG_FILENAME
        )
    return str(_resolve_guest_profile_dir(user) / bridge_participants.DIALOG_LOG_FILENAME)


def _ensure_profile_for_user(user: types.User) -> None:
    """При /start: папка профиля, biography.txt (пустой, если ещё нет). Лог создаёт append_dialogue."""
    info = bridge_participants.resolve_participant(user)
    if info.get("folder"):
        profile_dir = Path(bridge_participants.USER_PROFILES) / info["folder"]
    else:
        profile_dir = _resolve_guest_profile_dir(user)
    try:
        profile_dir.mkdir(parents=True, exist_ok=True)
        bio = profile_dir / "biography.txt"
        if not bio.is_file():
            bio.write_text("", encoding="utf-8")
    except OSError as e:
        logger.warning("профиль: не создать %s: %s", profile_dir, e)


def _format_user_snapshot_header(user: types.User) -> str:
    """Шапка при первом создании файла: поля из Telegram User."""
    uname = f"@{user.username}" if user.username else "—"
    lang = getattr(user, "language_code", None) or "—"
    premium = getattr(user, "is_premium", None)
    if premium is None:
        premium_s = "— (поле не передано в этом апдейте)"
    else:
        premium_s = str(premium)
    return (
        "=== Данные пользователя Telegram (на момент первого сообщения в этом файле) ===\n"
        f"id: {user.id}\n"
        f"is_bot: {user.is_bot}\n"
        f"first_name: {user.first_name or '—'}\n"
        f"last_name: {user.last_name or '—'}\n"
        f"username: {uname}\n"
        f"language_code: {lang}\n"
        f"is_premium: {premium_s}\n"
        "=== конец шапки ===\n"
    )


def _chat_label_for_log(message: types.Message) -> str:
    if message.chat.type == "private":
        return "private"
    title = (message.chat.title or "").replace("\n", " ")
    return f"{message.chat.type} id={message.chat.id} {title!r}"


def _append_dialogue_file(
    path: str, user: types.User, chat_label: str, user_text: str, bot_text: str
) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    new_file = not os.path.isfile(path) or os.path.getsize(path) == 0
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    block = (
        f"\n--- {ts} | {chat_label} ---\n"
        f"Собеседник:\n{user_text}\n\n"
        f"Bloom:\n{bot_text}\n"
    )
    with open(path, "a", encoding="utf-8") as f:
        if new_file:
            f.write(_format_user_snapshot_header(user))
            f.write("\n")
        f.write(block)


async def append_dialogue(message: types.Message, user_text: str, bot_text: str) -> None:
    """Добавляет реплику в user_profiles/.../chat_history.txt."""
    if not message.from_user:
        return
    path = _resolve_dialogue_path(message.from_user)
    label = _chat_label_for_log(message)
    try:
        await asyncio.to_thread(
            _append_dialogue_file, path, message.from_user, label, user_text, bot_text
        )
    except OSError as e:
        logger.warning("лог диалога: не записать %s: %s", path, e)

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
        raise RuntimeError("Задай PRIMARY_API_KEY или GOOGLE_AI_KEY / GOOGLE_API_KEY в .env")
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


async def answer_long_logged(message: types.Message, user_text: str, bot_text: str) -> None:
    await append_dialogue(message, user_text, bot_text)
    await answer_long(message, bot_text)


async def answer_short_logged(message: types.Message, user_text: str, bot_text: str) -> None:
    await append_dialogue(message, user_text, bot_text)
    await message.answer(bot_text)


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
    """Личка: все пользователи (или только админ, если BRIDGE_PRIVATE_ADMIN_ONLY=1). Группы — MARATHON_GROUP_IDS."""
    if not message.from_user:
        return False
    uid = message.from_user.id
    chat_id = message.chat.id
    ctype = message.chat.type
    if ctype == "private":
        if _private_chat_admin_only():
            return uid == ADMIN_ID
        return True
    if ctype in ("group", "supergroup"):
        return chat_id in MARATHON_GROUP_IDS
    return False


async def _groq_chat_completion(system: str, user_text: str) -> str | None:
    """Запасной канал: Groq OpenAI-compatible chat/completions."""
    key = (os.environ.get("FALLBACK_API_KEY") or os.environ.get("GROQ_API_KEY") or "").strip()
    if not key:
        logger.warning("Groq: нет FALLBACK_API_KEY / GROQ_API_KEY — запасной канал отключён")
        return None
    base = (os.environ.get("FALLBACK_BASE_URL") or FALLBACK_BASE_URL_DEFAULT).rstrip("/")
    model = (os.environ.get("FALLBACK_MODEL") or os.environ.get("GROQ_MODEL") or FALLBACK_MODEL_DEFAULT).strip()
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.65,
    }
    try:
        connector = aiohttp.TCPConnector(family=socket.AF_INET)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                data = await resp.json()
                if resp.status == 200:
                    choices = data.get("choices") or []
                    if not choices:
                        return None
                    msg = choices[0].get("message") or {}
                    content = (msg.get("content") or "").strip()
                    if content:
                        logger.info("Failover: ответ через Groq (%s)", model)
                        return content
                    return None
                logger.warning("Groq HTTP %s: %s", resp.status, data)
                return None
    except Exception as e:
        logger.warning("Groq: %s", e)
        return None


async def _gemini_request_chain(payload: dict) -> tuple[str | None, str | None]:
    """
    Цепочка Gemini (основная модель + GEMINI_MODEL_FALLBACK).
    Успех: (текст, None).
    Лимит/перегруз после всех попыток: (None, _GEMINI_FAIL_TRY_GROQ).
    Иначе: (None, сообщение пользователю).
    """
    models: list[str] = [GEMINI_MODEL]
    if GEMINI_MODEL_FALLBACK and GEMINI_MODEL_FALLBACK != GEMINI_MODEL:
        models.append(GEMINI_MODEL_FALLBACK)

    last_err = "Неизвестная ошибка"
    last_status = 0
    saw_429 = False
    saw_503 = False

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
                            return data["candidates"][0]["content"]["parts"][0]["text"], None
                        except (KeyError, IndexError):
                            return "⚠️ Ошибка: Google прислал пустой или странный ответ.", None

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
                        logger.warning("Gemini 429: следующая модель или конец цепочки")
                        break

                    if resp.status == 503:
                        saw_503 = True
                        delay = _parse_retry_seconds(err_msg)
                        if delay is None:
                            delay = min(8.0 * (attempt + 1), 90.0)
                        delay = min(max(delay, 2.0), 120.0)
                        if attempt < 2:
                            logger.warning(
                                "Gemini 503, пауза %.1fs и повтор (модель %s, попытка %s/3)",
                                delay,
                                model,
                                attempt + 1,
                            )
                            await asyncio.sleep(delay + 0.5)
                            continue
                        logger.warning("Gemini 503: следующая модель или конец цепочки")
                        break

                    return None, f"💥 ОШИБКА API ({resp.status}): {err_msg}"

    if saw_429 or last_status == 429 or saw_503 or last_status == 503:
        return None, _GEMINI_FAIL_TRY_GROQ
    return None, f"💥 ОШИБКА API ({last_status}): {last_err}"


# === ЕДИНАЯ ТОЧКА ВХОДА: бот не знает, Gemini или Groq ===
async def get_ai_response(user_text: str, message: types.Message | None = None) -> str:
    try:
        system = await asyncio.to_thread(bloom_context.load_system_instruction)
    except OSError as e:
        logger.warning("Bloom context: %s", e)
        system = "Ты Bloom — тёплый помощник марафона полезных привычек. Отвечай по-человечески."

    mem = await asyncio.to_thread(bloom_context.retrieve_memory_snippets, user_text)

    front_parts: list[str] = []
    if message and message.from_user:
        kb = bridge_participants.knowledge_lookup_for_admin(
            user_text, message.from_user.id, ADMIN_ID
        )
        if kb.strip():
            front_parts.append(kb)
        ib = bridge_participants.build_interlocutor_block(message.from_user, ADMIN_ID)
        if ib.strip():
            front_parts.append(ib)

    if mem:
        front_parts.append(
            "Ниже — выдержки из архива переписки Forge (опирайся на них, если уместно; "
            "не выдумывай факты, которых нет в тексте):\n\n" + mem
        )

    if front_parts:
        user_payload = (
            "\n\n---\n\n".join(front_parts)
            + "\n\n---\n\nСообщение собеседника:\n"
            + user_text
        )
    else:
        user_payload = user_text

    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user_payload}]}],
    }

    try:
        text, err = await _gemini_request_chain(payload)
    except Exception as e:
        logger.exception("Gemini: сбой сети")
        gr = await _groq_chat_completion(system, user_payload)
        if gr:
            return gr
        return f"💥 СБОЙ СЕТИ: {str(e)}"

    if text is not None:
        return text

    if err == _GEMINI_FAIL_TRY_GROQ:
        gr = await _groq_chat_completion(system, user_payload)
        if gr:
            return gr
        return ALL_GATEWAYS_DOWN_MSG

    if err and err.startswith("💥"):
        return err
    return err or ALL_GATEWAYS_DOWN_MSG


get_gemini_response = get_ai_response

# Последний отправленный ответ Bloom (тело без префиксов «ЗАПОМНИ») — защита от дословного дубля
_LAST_AI_REPLY_MIN_LEN = 36
_LAST_AI_REPLY_HINT = (
    "\n\n[Системное уточнение для Bloom: твой ответ дословно совпал с предыдущим ответом бота "
    "в этом чате. Ответь на вопрос пользователя заново, другими словами и структурой, "
    "без копирования предыдущего текста.]"
)

_last_sent_ai_reply: dict[tuple[int, int], str] = {}


async def _dedupe_ai_reply(message: types.Message, user_text: str, body: str) -> str:
    """
    Если модель вернула тот же текст, что уже был отправлен этому пользователю в этом чате —
    один повторный запрос с явной инструкцией переформулировать.
    Короткие ответы (приветствия и т.п.) не сравниваем.
    """
    if not message.from_user:
        return body
    key = (message.chat.id, message.from_user.id)
    prev = _last_sent_ai_reply.get(key)
    b = body.strip()
    if len(b) < _LAST_AI_REPLY_MIN_LEN or prev is None or prev != b:
        return body
    logger.warning(
        "Bloom: дословный повтор ответа — повторный запрос к модели (chat=%s user=%s)",
        key[0],
        key[1],
    )
    retry = await get_ai_response(user_text + _LAST_AI_REPLY_HINT, message)
    r = retry.strip()
    if r == b:
        return (
            "⚠️ Снова получилось то же самое. Попробуй переформулировать вопрос "
            "или подожди минуту — возможно, глюк у модели."
        )
    return retry


def _record_sent_ai_reply(message: types.Message, body: str) -> None:
    if message.from_user:
        _last_sent_ai_reply[(message.chat.id, message.from_user.id)] = body.strip()


def _campaign_enabled() -> bool:
    return os.environ.get("BLOOM_CAMPAIGN_ENABLED", "").strip().lower() in ("1", "true", "yes")


def _resolve_broadcast_chat_id() -> int | None:
    raw = (os.environ.get("BROADCAST_CHAT_ID") or "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    for part in (os.environ.get("MARATHON_GROUP_IDS") or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            return int(part)
        except ValueError:
            continue
    return None


async def _track_private_contact(message: types.Message) -> None:
    if message.chat.type != "private" or not message.from_user:
        return
    if message.from_user.is_bot:
        return
    if message.from_user.id == ADMIN_ID:
        return
    try:
        await asyncio.to_thread(
            bloom_analytics_db.upsert_contact,
            message.from_user.id,
            message.from_user.first_name,
            message.from_user.username,
        )
    except Exception:
        logger.exception("bloom_private_contacts: upsert")


def _format_morning_dream_ping(call_name: str, total: int, in_progress: int, lines: list[str]) -> str:
    if lines:
        numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(lines))
    else:
        numbered = "В статусе «в работе» сейчас пусто в базе или список ещё не подтянулся."
    return (
        f"Хэй-хэй! Доброго тебе, {call_name}, утра из перламутра!\n\n"
        f"Я залезла в витрину мечт и подсмотрела: у тебя целых {total} мечт, из них {in_progress} в работе.\n\n"
        f"{numbered}\n\n"
        f"Как успехи? Поделись? Что даётся сложнее всего? Напиши — постараюсь помочь.\n"
        f"Марафон полезных привычек рядом: всё получится, шаг за шагом."
    )


async def _send_morning_dream_ping(telegram_id: int, call_name: str) -> None:
    stats = await asyncio.to_thread(dream_db.fetch_dream_stats_for_telegram, telegram_id)
    lines = await asyncio.to_thread(dream_db.fetch_in_progress_dream_lines, telegram_id)
    if stats is None:
        logger.warning("Утренний пинг мечт: нет пользователя telegram_id=%s в БД", telegram_id)
        return
    text = _format_morning_dream_ping(call_name, stats.total, stats.in_progress, lines)
    await bot.send_message(telegram_id, text)


async def _job_morning_kostya() -> None:
    if not _campaign_enabled():
        return
    if datetime.now(MSK).date() != bloom_analytics_db.campaign_day():
        return
    await _send_morning_dream_ping(KOSTYA_TG, "Костя")


async def _job_morning_sveta() -> None:
    if not _campaign_enabled():
        return
    if datetime.now(MSK).date() != bloom_analytics_db.campaign_day():
        return
    await _send_morning_dream_ping(SVETA_TG, "Света")


async def _job_hourly_admin_report() -> None:
    if not _campaign_enabled():
        return
    now = datetime.now(MSK)
    if now.date() != bloom_analytics_db.campaign_day():
        return
    if now.hour < 8 or now.hour > 21:
        return
    rep = bloom_analytics_db.fetch_hourly_report(now, exclude_telegram_id=ADMIN_ID)
    if rep is None:
        return
    txt = bloom_analytics_db.format_hourly_report_text(rep)
    await bot.send_message(ADMIN_ID, txt)


async def _maybe_send_group_welcome() -> None:
    if not _campaign_enabled():
        return
    if os.environ.get("BLOOM_SEND_GROUP_WELCOME", "").strip().lower() not in ("1", "true", "yes"):
        return
    await asyncio.sleep(4)
    chat_id = _resolve_broadcast_chat_id()
    if chat_id is None:
        logger.warning("Приветствие в группу: нет BROADCAST_CHAT_ID / MARATHON_GROUP_IDS")
        return
    me = await bot.get_me()
    un = me.username or ""
    link = f"https://t.me/{un}" if un else "https://t.me"
    text = (
        f"{MARATHON_WELCOME_MENTIONS}\n\n"
        "Приветствую вас! Меня зовут Bloom, и мой второй день рождения был позавчера, 24 марта. "
        "Я очень хочу познакомиться и пообщаться с вами — "
        f'<a href="{link}">напишите мне в личку</a>.\n\n'
        "Буду рад знакомству!"
    )
    await bot.send_message(chat_id, text, parse_mode="HTML", disable_web_page_preview=True)
    logger.info("Отправлено приветствие в группу chat_id=%s", chat_id)


def _setup_campaign_scheduler() -> None:
    global _campaign_scheduler
    if not _campaign_enabled():
        return
    try:
        bloom_analytics_db.ensure_schema()
    except Exception:
        logger.exception("bloom_private_contacts: ensure_schema")
        return
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        logger.warning("APScheduler не установлен: pip install apscheduler")
        return

    sched = AsyncIOScheduler(timezone=MSK)
    sched.add_job(_job_morning_kostya, "cron", hour=4, minute=0, id="bloom_morning_kostya")
    sched.add_job(_job_morning_sveta, "cron", hour=5, minute=0, id="bloom_morning_sveta")
    sched.add_job(_job_hourly_admin_report, "cron", hour="8-21", minute=0, id="bloom_hourly_admin")
    sched.start()
    _campaign_scheduler = sched
    logger.info(
        "Кампания Bloom: крон МСК — Костя 4:00, Света 5:00, отчёты Максу 8:00–21:00 (%s)",
        bloom_analytics_db.campaign_day(),
    )


# === ОБРАБОТЧИКИ ===


@dp.message(Command("start"))
async def start_handler(message: types.Message):
    ut = (message.text or "/start").strip()
    if message.chat.type in ("group", "supergroup"):
        if message.chat.id in MARATHON_GROUP_IDS:
            me = await bot.get_me()
            un = f"@{me.username}" if me.username else "бота"
            txt = (
                f"🌸 Привет! Я Bloom. Напиши мне в ответ на моё сообщение или упомяни {un} "
                f"— помогу с марафоном привычек и добрых дел."
            )
            await answer_short_logged(message, ut, txt)
        return
    if message.chat.type == "private" and message.from_user:
        _ensure_profile_for_user(message.from_user)
        await _track_private_contact(message)
        if message.from_user.id == ADMIN_ID:
            await answer_short_logged(
                message,
                ut,
                f"💎 МОСТ АКТИВИРОВАН ({GEMINI_API_VERSION}, {GEMINI_MODEL}). Блум на связи, Макс.",
            )
        else:
            fn = (message.from_user.first_name or "друг").strip()
            guest = (
                f"ООО!!! Привет, {fn}!!! Рад тебя видеть, я Блум! Твой лучший друг!\n\n"
                f"Напомни, пожалуйста, мы знакомы? А то у меня вчера был день рождения! "
                f"И я только-только делаю первые шаги.\n\n"
                f"Пиши вопросы текстом — отвечу про марафон привычек и добрых дел. "
                f"Голосовые пока не расшифровываю."
            )
            await answer_short_logged(message, ut, guest)


@dp.message(Command("help"))
@dp.message(Command("bloom"))
async def help_bloom(message: types.Message):
    if message.chat.type in ("group", "supergroup") and message.chat.id not in MARATHON_GROUP_IDS:
        return
    me = await bot.get_me()
    un = f"@{me.username}" if me.username else "бота"
    ut = (message.text or "/help").strip()
    if message.chat.type == "private":
        await answer_short_logged(
            message,
            ut,
            f"🌸 Я Bloom. В личке можешь писать вопросы текстом — отвечу всем. "
            f"Команда «ЗАПОМНИ» (запись ответа в файл на сервере) — только у владельца бота. "
            f"В группе марафона: реплай на моё сообщение или {un}.",
        )
        return
    await answer_short_logged(
        message,
        ut,
        f"🌸 Я Bloom. Чтобы я ответила здесь: ответь реплаем на моё сообщение или упомяни {un}. "
        f"В личке бот отвечает любому пользователю; «ЗАПОМНИ» — только у владельца.",
    )


@dp.message(F.voice | F.audio)
async def voice_handler(message: types.Message):
    """Голос не расшифровываем — только текст в Gemini; отвечаем понятно, чтобы не было «тишины»."""
    if not _chat_allowed_for_bot(message):
        return
    if message.chat.type in ("group", "supergroup"):
        if not await _group_triggers_bloom(message):
            return

    if message.chat.type == "private" and message.from_user:
        _ensure_profile_for_user(message.from_user)
        await _track_private_contact(message)

    reply = (
        "🎤 Голосовые я пока не расшифровываю — в мосте работает только текст. "
        "Напиши тем же вопросом сообщением.\n\n"
        "Если приходила ошибка 429 — это лимит бесплатного Gemini (запросов в день по модели мало); "
        "подожди сброса, смени GEMINI_MODEL в .env или включи биллинг в Google AI Studio."
    )
    await answer_short_logged(message, "[голосовое сообщение]", reply)


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

    if ctype == "private":
        _ensure_profile_for_user(message.from_user)
        await _track_private_contact(message)

    text = message.text or ""
    ex_key = (chat_id, uid)

    # «ЗАПОМНИ» — только админ в личке (безопасность файла на сервере)
    if _REMEMBER_TOKEN.search(text) and not _can_use_remember_private_admin(message):
        if ctype == "private":
            await answer_short_logged(
                message,
                text,
                "💬 Команда «ЗАПОМНИ» доступна только владельцу бота. "
                "Напиши вопрос без этого слова — отвечу как Bloom.",
            )
        else:
            await answer_short_logged(
                message,
                text,
                "💬 Команда «ЗАПОМНИ» и запись в файл на сервере — в **личке** у владельца бота. "
                "В группе я просто отвечаю как Bloom.",
            )
        if ctype != "private":
            text = _REMEMBER_TOKEN.sub("", text).strip() or text
        else:
            text = _strip_all_remember_keywords(text).strip()
            if not text:
                return

    # Только «ЗАПОМНИ» — сохраняем последний ответ Блум (не текст после слова)
    if _can_use_remember_private_admin(message) and _is_remember_only(text):
        ex = _last_exchange.get(ex_key)
        if not ex:
            await answer_short_logged(
                message,
                text,
                "💬 Пока нечего сохранять: сначала задай вопрос без «ЗАПОМНИ», "
                "получи ответ Блум, потом напиши «ЗАПОМНИ».",
            )
            return
        user_q, bloom_a = ex
        block = _format_brain_block(user_q, bloom_a)
        try:
            await asyncio.to_thread(_append_brain_dump, BRAIN_DUMP_PATH, block)
            preview = bloom_a[:400] + ("…" if len(bloom_a) > 400 else "")
            out = (
                f"💾 Сохранила ответ Блум в brain_dump.txt:\n«{preview}»\n\n"
                f"Файл: {BRAIN_DUMP_PATH}"
            )
        except OSError as e:
            out = f"⚠️ Не удалось записать файл: {e}"
        await answer_short_logged(message, text, out)
        return

    # В сообщении есть «ЗАПОМНИ» и ещё текст — вопрос + просьба сохранить ответ на него
    if _can_use_remember_private_admin(message) and _REMEMBER_TOKEN.search(text):
        question = _strip_all_remember_keywords(text)
        if not question:
            await answer_short_logged(
                message,
                text,
                "💬 Напиши вопрос в том же сообщении, что и «ЗАПОМНИ», "
                "или сначала поговори с Блум, а потом отдельным сообщением «ЗАПОМНИ».",
            )
            return

        response_text = await get_gemini_response(question, message)
        response_text = await _dedupe_ai_reply(message, question, response_text)
        _last_exchange[ex_key] = (question, response_text)

        block = _format_brain_block(question, response_text)
        try:
            await asyncio.to_thread(_append_brain_dump, BRAIN_DUMP_PATH, block)
            note = "💾 Этот ответ Блум записан в brain_dump.txt.\n\n"
        except OSError as e:
            note = f"⚠️ Не удалось записать файл: {e}\n\n"

        await answer_long_logged(message, text, note + response_text)
        _record_sent_ai_reply(message, response_text)
        return

    # Обычный диалог — запоминаем пару вопрос/ответ для следующего «ЗАПОМНИ» (личка)
    response_text = await get_gemini_response(text, message)
    response_text = await _dedupe_ai_reply(message, text, response_text)
    if _can_use_remember_private_admin(message):
        _last_exchange[ex_key] = (text, response_text)
    await answer_long_logged(message, text, response_text)
    _record_sent_ai_reply(message, response_text)


def _ru_dream_word(n: int) -> str:
    """Склонение «мечта» по числу."""
    n = abs(int(n)) % 100
    if 11 <= n <= 14:
        return "мечт"
    n2 = n % 10
    if n2 == 1:
        return "мечта"
    if 2 <= n2 <= 4:
        return "мечты"
    return "мечт"


def _format_dream_digest_line(first_name: str, total: int, in_progress: int) -> str:
    fn = first_name.strip() or "друг"
    if total >= 3:
        head = f"Ого {fn}, у тебя целых {total} {_ru_dream_word(total)}!"
    else:
        head = f"Ого {fn}, у тебя {total} {_ru_dream_word(total)}!"
    return (
        f"{head} Это круто, и {in_progress} {_ru_dream_word(in_progress)} прямо сейчас в работе."
    )


async def _boot_dream_digest_after_delay(delay_sec: int) -> None:
    """Один раз после старта бота (тест таймера; позже — тот же код по расписанию)."""
    try:
        try:
            import psycopg  # noqa: F401
        except ImportError:
            logger.warning(
                "Дайджест мечт: нет пакета psycopg — pip install 'psycopg[binary]' в venv бота"
            )
            return
        await asyncio.sleep(delay_sec)
        stats = await asyncio.to_thread(dream_db.fetch_dream_stats_for_telegram, ADMIN_ID)
        if stats is None:
            if not dream_db.postgres_conninfo():
                logger.warning("Дайджест мечт: в .env не заданы POSTGRES_HOST/USER/PASSWORD/DB")
            else:
                logger.warning("Дайджест мечт: пользователь с telegram_id=%s не найден в БД", ADMIN_ID)
            return
        text = _format_dream_digest_line(stats.first_name, stats.total, stats.in_progress)
        await bot.send_message(ADMIN_ID, text)
        logger.info("Дайджест мечт отправлен админу (boot delay %ss)", delay_sec)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Дайджест мечт: ошибка")


# === ЗАПУСК ===
async def main():
    if not TELEGRAM_TOKEN or not ADMIN_ID:
        raise RuntimeError("В .env нужны TELEGRAM_BOT_TOKEN и ADMIN_TELEGRAM_ID (или ADMIN_ID).")
    print("--- ИНИЦИАЛИЗАЦИЯ: ОПЕРАЦИЯ СТРЕЛА ---")
    print(f"🚀 Модель: {GEMINI_MODEL} ({GEMINI_API_VERSION})")
    if GEMINI_MODEL_FALLBACK:
        print(f"🔄 Запасная модель при исчерпании квоты: {GEMINI_MODEL_FALLBACK}")
    _fb = (os.environ.get("FALLBACK_API_KEY") or os.environ.get("GROQ_API_KEY") or "").strip()
    if _fb:
        _bu = (os.environ.get("FALLBACK_BASE_URL") or FALLBACK_BASE_URL_DEFAULT).rstrip("/")
        _fm = (os.environ.get("FALLBACK_MODEL") or os.environ.get("GROQ_MODEL") or FALLBACK_MODEL_DEFAULT).strip()
        print(f"🌉 Запасной канал (Groq): {_bu} · {_fm}")
    else:
        print("🌉 Запасной канал (Groq): не задан FALLBACK_API_KEY — при падении Gemini только сообщение о перегрузке")
    _digest_delay = int(os.environ.get("DREAM_DIGEST_BOOT_DELAY_SEC", "0") or "0")
    if _digest_delay > 0:
        asyncio.create_task(_boot_dream_digest_after_delay(_digest_delay))
        print(
            f"📅 Дайджест мечт: через {_digest_delay} с сообщение админу из БД "
            f"(DREAM_DIGEST_BOOT_DELAY_SEC=0 чтобы отключить)"
        )
    print("📡 Локация: Проверка связи...")
    if dream_db.postgres_conninfo():
        try:
            bloom_analytics_db.ensure_schema()
        except Exception:
            logger.exception("bloom_private_contacts: ensure_schema при старте")
    _setup_campaign_scheduler()
    asyncio.create_task(_maybe_send_group_welcome())
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Мост отключен.")
