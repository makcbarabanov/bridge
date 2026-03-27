#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Анализ содержания ответов
"""

import json

with open('responses_full.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("🔍 Анализ содержания ответов:")
print("=" * 60)

# Анализируем несколько ключевых вопросов
key_questions = [1, 3, 7, 11, 15]

for q_num in key_questions:
    q_answers = [r for r in data if r.get('question_number') == q_num and r.get('answer')]
    if not q_answers:
        continue
    
    q_text = q_answers[0]['question_text']
    print(f"\n❓ Вопрос {q_num}: {q_text[:70]}...")
    print("-" * 60)
    
    for ans in q_answers:
        user = ans.get('user_name', 'Unknown')
        answer_text = ans.get('answer', '')
        if answer_text:
            # Показываем первые 150 символов
            preview = answer_text[:150].replace('\n', ' ')
            print(f"  {user}: {preview}...")
    print()

print("=" * 60)
print("\n💭 Мои мысли об ответах:\n")

