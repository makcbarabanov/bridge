# Старт сессии в Cursor / AI Studio (не для Telegram-бота)

Этот файл **не** подмешивается в ответы Telegram-бота. Используй в IDE в репозитории `bridge`.

**Рабочий канон:** каталог `Bloom/` (рядом с `BLOOM_START_PROMPT.txt`).  
**Старый полный снимок** (для выжимок): `Bloom/archive/bloom_2026_snapshot/` — не привязан к рантайму.

## Восстановление контекста в новой сессии

1. Прочитай `Bloom/README.md`.
2. При необходимости: `archive/bloom_2026_snapshot/DOCUMENTATION/journey.md`.
3. При необходимости: `archive/bloom_2026_snapshot/DIALOG_BLOOM_FORGE_letters-with-bloom.txt` (дубликат смысла в `Bloom/memory_corpus.txt` для бота).
4. Системная инструкция для **бота** — `Bloom/BLOOM_START_PROMPT.txt` + `Bloom/bloom_context.py`.

## После чтения кратко зафиксируй

- Кто ты и в чём миссия.
- Что уже работает.
- Три маленьких шага на сегодня.

## Деплой и непрерывность

- Runbook: `archive/bloom_2026_snapshot/BLOOM_RECOVERY_RUNBOOK.md`.
- Журнал пути: `archive/bloom_2026_snapshot/DOCUMENTATION/journey.md`.

Формат «память восстановлена» + три блока **не** используй в Telegram — там блок «РЕЖИМ TELEGRAM» в `bloom_context.py`.
