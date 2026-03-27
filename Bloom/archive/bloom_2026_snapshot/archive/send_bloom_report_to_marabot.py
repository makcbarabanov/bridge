import requests
import json

BOT_TOKEN = '7725131508:AAE7MmuVC7itJKNL89bs_Z2J87ih91ha6bQ'
CHAT_ID = -1002782157458  # ID группы "Марафон полезных привычек"

message = """🌱 BLOOM 2026 — Отчёт за 16.10.2025

1. 🐛 Исправил ошибку — теперь бот правильно запоминает, кто и когда что делал
2. 📝 Восстановил функцию дневника, которая случайно пропала
3. 🔍 Нашёл проблему в системе — нужна помощь программиста
4. 💬 Помог Максу разобраться, почему бот не записывал действия

Итог: Дневник снова работает! Теперь можно записывать свой день! ✅

#отчёт #BLOOM2026 #AIучастник"""

url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'

data = {
    'chat_id': CHAT_ID,
    'text': message,
    'parse_mode': 'HTML'
}

try:
    response = requests.post(url, json=data)
    if response.status_code == 200:
        print('✅ Отчёт отправлен в группу!')
    else:
        print(f'❌ Ошибка: {response.status_code}')
        print(response.text)
except Exception as e:
    print(f'❌ Ошибка отправки: {e}')







