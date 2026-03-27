# Bloom в bridge_bot

## Где лежит канон

По умолчанию **`BLOOM_HOME`** = каталог **`Bloom/`** в репозитории (рядом с `BLOOM_START_PROMPT.txt`).

Переопределение: переменная окружения **`BLOOM_HOME`** — абсолютный путь к этому каталогу.

Полная схема файлов: **`STRUCTURE.md`** в этой папке.

## Что собирается в `systemInstruction` (Gemini / Groq)

Порядок в `bloom_context.load_system_instruction()`:

1. Блок **«РЕЖИМ TELEGRAM»** в `bloom_context.py`.
2. **`BLOOM_START_PROMPT.txt`**
3. **`bloom_biography.txt`** (фрагмент)
4. **`bloom_body.txt`** (хвост)
5. Начало **`README.md`**
6. Финальная строка

**Не** в бот: **`CURSOR_BOOTSTRAP.md`**, содержимое **`archive/`**.

## Поиск по памяти (`retrieve_memory_snippets`)

Читает только **`memory_corpus.txt`**, затем при отсутствии — **`DIALOG_2025-11-17.md`** (оба в корне `Bloom/`). Архив не используется.

## Профили пользователей

См. корневой `README.md` проекта: `user_profiles/`, `bloom_traits.txt`.

## Группа марафона

В `.env`: **`MARATHON_GROUP_IDS`**. Команда **«ЗАПОМНИ»** — только владельцу в личке.

## Кэш

После правок больших файлов — перезапуск бота или `bloom_context.invalidate_cache()`.
