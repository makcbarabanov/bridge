# Разовые и вспомогательные скрипты

Здесь лежит то, что **не** входит в рантайм бота. Запуск из корня репозитория:

```bash
cd /path/to/bridge
source venv/bin/activate
python _py_/list_models.py
python _py_/send_admin_dm.py          # опциональный текст аргументами
python _py_/send_test_message.py      # в чат из BROADCAST_CHAT_ID или MARATHON_GROUP_IDS
python _py_/send_group_personal_welcomes.py  # два приветствия в группу: Ксения (BE), Магда (HY)
```

Правило: скрипт **одноразовый** — после отладки **удали** файл из этой папки, если не планируешь повторять. То, что остаётся (например `list_models.py`), — осознанные утилиты, а не мусор в корне.

`.env` подхватывается из **родительской** папки (`bridge/.env`).
