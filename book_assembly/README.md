# Книга «14:45» — отдельный проект внутри Bridge

Здесь лежат **источник** экспорта «Книга» (JSON), сборка HTML, ТЗ и заметки по Google Docs. Папку можно целиком перенести в другой репозиторий — бот Bloom на это не зависит.

| Что | Назначение |
|-----|------------|
| `Книга` | Экспорт из Google AI Studio (JSON), вход для `extract_fragments.py` |
| `extract_fragments.py` | Сборка `14-45_manuscript.html` и метаданных по якорям |
| `*.html`, `fragments_meta.json`, `extraction_log.txt` | Артефакты сборки |
| `ATLAS_TZ_14-45.md`, `FORGE_ACK.md`, `GOOGLE_DOCS_README.md` | Документация процесса |

Запуск из этой папки:

```bash
python extract_fragments.py
```
