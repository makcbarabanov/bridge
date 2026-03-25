# Bridge — Telegram-бот Bloom («Мост»)

## Назначение

Рантайм: **aiogram** + опционально **Gemini** / **Groq**, лог диалогов, участники марафона, дайджест мечт из **PostgreSQL**.

## Структура репозитория

```
bridge/
├── bridge_bot.py          # Точка входа бота, хендлеры, AI, фоновые задачи
├── dream_db.py            # Запросы к БД (мечты) — только то, что нужно боту
├── bridge_participants.py # Участники, user_profiles, хвост dialogy в промпт
├── bridge                 # Скрипт: systemctl --user для bridge-bot.service
├── Bloom/                 # Канон Блума: bloom_context, распакованный архив проекта
├── book_assembly/       # Книга «14:45» — см. book_assembly/README.md (отдельный трек)
├── user_profiles/       # Текстовые досье людей для бота (не путать с БД marabot)
├── dialogy/             # Логи переписок (локально на сервере, в .gitignore)
├── inbox/               # Временные файлы (в git только README)
├── _py_/                # Утилиты и разовые скрипты — см. _py_/README.md
├── .env.example
└── venv/                # не в git
```

## Принципы

1. **Корень** — только то, что нужно для **запуска** бота и общих модулей. Новые фичи бота — рядом с `bridge_bot.py` или отдельным модулем с понятным именем (`dream_db.py`), без свалки скриптов.
2. **`_py_/`** — всё, что запускается руками (список моделей, тестовая отправка в Telegram). Разовое — удалить после использования.
3. **`book_assembly/`** — автономный контур «книги»; не смешивать с логикой Telegram.
4. **Секреты** — только в `.env` (в git не попадает). Пример — `.env.example`.

## Запуск

```bash
source venv/bin/activate
python bridge_bot.py
# или через systemd: bridge start | restart | status | logs
```
