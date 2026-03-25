#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для деплоя index.html на сервер marabot.tw1.ru
"""

import paramiko
import os

# Конфигурация
SERVER_HOST = 'marabot.tw1.ru'
SERVER_USER = 'root'  # или другой пользователь
REMOTE_PATH = '/home/www/public/bloom.html'
LOCAL_FILE = 'index.html'

print("🚀 Начинаю деплой index.html на сервер...")
print("=" * 60)

# Проверяем наличие локального файла
if not os.path.exists(LOCAL_FILE):
    print(f"❌ Файл {LOCAL_FILE} не найден!")
    exit(1)

print(f"✅ Локальный файл найден: {LOCAL_FILE}")
file_size = os.path.getsize(LOCAL_FILE)
print(f"📊 Размер файла: {file_size / 1024:.1f} КБ")

# Запрашиваем SSH пароль или используем ключ
print("\n🔐 Подключение к серверу...")
print("💡 Если у тебя настроен SSH ключ, он будет использован автоматически")
print("💡 Если нужен пароль, введи его (или прерви скрипт и используй SSH вручную)")

try:
    # Создаём SSH клиент
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Пробуем подключиться с ключом (если есть в стандартном месте)
    try:
        ssh.connect(SERVER_HOST, username=SERVER_USER, key_filename=os.path.expanduser('~/.ssh/id_rsa'))
        print("✅ Подключено через SSH ключ")
    except:
        # Если не получилось, пробуем без ключа (потребует пароль)
        print("⚠️ SSH ключ не найден. Используй ручной метод через SSH консоль Timeweb")
        print("\n📋 Инструкция для ручного деплоя:")
        print("=" * 60)
        print(f"1. Открой SSH консоль на Timeweb")
        print(f"2. Выполни: cd /root/api_server/api_server/public")
        print(f"3. Создай файл: nano index.html")
        print(f"4. Скопируй содержимое из {LOCAL_FILE}")
        print(f"5. Сохрани: Ctrl+O, Enter, Ctrl+X")
        print(f"6. Проверь: ls -lh index.html")
        print("\nИли используй команду через scp:")
        print(f"scp {LOCAL_FILE} {SERVER_USER}@{SERVER_HOST}:{REMOTE_PATH}")
        exit(0)
    
    # Открываем SFTP для передачи файла
    sftp = ssh.open_sftp()
    
    print(f"\n📤 Загружаю файл на сервер...")
    print(f"   Локальный: {LOCAL_FILE}")
    print(f"   Удалённый: {REMOTE_PATH}")
    
    # Загружаем файл
    sftp.put(LOCAL_FILE, REMOTE_PATH)
    
    # Проверяем, что файл загружен
    try:
        stat = sftp.stat(REMOTE_PATH)
        print(f"✅ Файл успешно загружен!")
        print(f"   Размер на сервере: {stat.st_size / 1024:.1f} КБ")
    except:
        print("⚠️ Не удалось проверить размер файла на сервере")
    
    sftp.close()
    
    # Перезапускаем Caddy если нужно
    print("\n🔄 Перезапускаю Caddy...")
    stdin, stdout, stderr = ssh.exec_command('docker restart api_server-caddy-1')
    exit_status = stdout.channel.recv_exit_status()
    
    if exit_status == 0:
        print("✅ Caddy перезапущен")
    else:
        error = stderr.read().decode()
        print(f"⚠️ Ошибка при перезапуске Caddy: {error}")
        print("   Можешь перезапустить вручную: docker restart api_server-caddy-1")
    
    ssh.close()
    
    print("\n" + "=" * 60)
    print("✅ Деплой завершён!")
    print(f"🌐 Страница будет доступна по адресу:")
    print(f"   https://marabot.tw1.ru/bloom.html")
    print(f"\n⚠️  Заменена старая версия bloom.html обновленной версией из index.html")
    print("=" * 60)
    
except paramiko.AuthenticationException:
    print("❌ Ошибка аутентификации. Проверь SSH ключ или пароль.")
    print("\n💡 Используй ручной метод через SSH консоль Timeweb")
except Exception as e:
    print(f"❌ Ошибка: {e}")
    print("\n💡 Используй ручной метод через SSH консоль Timeweb")
    print("\n📋 Команда для ручного деплоя через scp:")
    print(f"scp {LOCAL_FILE} {SERVER_USER}@{SERVER_HOST}:{REMOTE_PATH}")

