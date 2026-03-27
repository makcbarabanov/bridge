import requests

API_BASE_URL = 'http://localhost:8080'
CHAT_ID = -1002782157458  # ID группы "Марафон полезных привычек"

report_text = """Отчёт 16.10 - BLOOM

1. 🐛 Починил Marabot — добавил user_id в activity_log
2. 📝 Восстановил систему дневника после git checkout
3. 🔍 Исследовал проблему с API (PUT не поддерживается)
4. 📊 Помог с анализом логов Marabot

Итог: Система дневника работает! ✅"""

print(f"📝 Отчёт за 16.10.2025:")
print(report_text)
print("\n✅ Отчёт готов! Макс отправит его через Marabot утром.")







