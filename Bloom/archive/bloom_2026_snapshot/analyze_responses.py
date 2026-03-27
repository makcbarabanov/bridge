#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Анализ ответов из опросника BLOOM
"""

import requests
import json
from collections import defaultdict

API_URL = 'https://marabot.tw1.ru'

print("📊 Анализ ответов из опросника BLOOM...")
print("=" * 60)

# Получаем данные
response = requests.get(f'{API_URL}/tables/bloom_questionnaire_responses')
if response.status_code != 200:
    print(f"❌ Ошибка: {response.status_code}")
    exit(1)

data = response.json()
rows = data.get('rows', [])

print(f"\n📈 Всего ответов: {len(rows)}")

# Группируем по пользователям
users = defaultdict(list)
for row in rows:
    user_name = row.get('user_name', 'Unknown')
    users[user_name].append(row)

print(f"👥 Пользователей: {len(users)}")

# Статистика по пользователям
print("\n" + "=" * 60)
print("📋 Статистика по пользователям:")
print("=" * 60)

for name, answers in sorted(users.items()):
    print(f"\n{name}:")
    print(f"  • Ответов: {len(answers)}")
    
    # Уникальные вопросы
    questions = set()
    for ans in answers:
        q = ans.get('question_text', '')
        if q:
            questions.add(q)
    print(f"  • Уникальных вопросов: {len(questions)}")
    
    # Время
    total_time = sum(ans.get('time_spent_seconds', 0) for ans in answers)
    avg_time = total_time / len(answers) if answers else 0
    print(f"  • Среднее время на ответ: {avg_time:.1f} сек")

# Группируем по вопросам
questions_stats = defaultdict(list)
for row in rows:
    q_text = row.get('question_text', '')
    q_num = row.get('question_number', 0)
    if q_text:
        questions_stats[q_num].append({
            'text': q_text,
            'user': row.get('user_name', 'Unknown'),
            'answer': row.get('answer', ''),
            'time': row.get('time_spent_seconds', 0)
        })

print("\n" + "=" * 60)
print("❓ Статистика по вопросам:")
print("=" * 60)

for q_num in sorted(questions_stats.keys()):
    q_data = questions_stats[q_num]
    if q_data:
        q_text = q_data[0]['text']
        print(f"\nВопрос {q_num}: {q_text[:60]}...")
        print(f"  • Ответов: {len(q_data)}")
        avg_time = sum(d['time'] for d in q_data) / len(q_data) if q_data else 0
        print(f"  • Среднее время: {avg_time:.1f} сек")
        
        # Показываю первых респондентов
        users_answered = [d['user'] for d in q_data]
        print(f"  • Ответили: {', '.join(set(users_answered))}")

# Сохраняем полные данные для детального анализа
with open('responses_full.json', 'w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 60)
print("💾 Полные данные сохранены в responses_full.json")
print("=" * 60)

