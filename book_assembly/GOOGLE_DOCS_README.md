# Google Docs API — когда будет биллинг / OAuth

ТЗ Атласа требует документ **через API**. Сейчас в проекте **нет** `credentials.json` / `token.json`, ранее на бесплатном тире GCP были блокировки.

## Что сделать позже

1. GCP: проект, биллинг, включить **Google Docs API**.
2. OAuth **Desktop** → скачать `credentials.json` в `book_assembly/secrets/` (папку добавить в `.gitignore`).
3. Один раз локально: `python oauth_setup_docs.py` (создать по образцу ниже) → получить `token.json`.
4. Скопировать `credentials.json` + `token.json` на сервер.

## Идея скрипта `upload_manuscript_to_docs.py` (не подключён)

- Читать `14-45_manuscript.html`.
- Конвертировать в запросы `documents.batchUpdate`: `insertText`, для цвета — `updateTextStyle` с `foregroundColor` (rgb для #000000 и #B85D19).
- Либо проще: вставить **plain text** одним блоком, цвета расставить вторым проходом по диапазонам (сложнее).

Пакеты: `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`.

## Обходной путь сейчас

1. Открыть `14-45_manuscript.html` в Chrome.
2. **Ctrl+A → Ctrl+C**.
3. В Google Docs: **Вставить** (обычно сохраняется часть форматирования).
4. Вручную выделить блоки Атласа и задать цвет **#B85D19** (Инструменты настройки цвета).

Это соответствует **Правилу №2** ТЗ с минимальной болью до появления API.
