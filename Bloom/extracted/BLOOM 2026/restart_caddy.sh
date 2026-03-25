#!/bin/bash
# Перезапуск Caddy после обновления bloom.html

echo "🔄 Перезапускаю Caddy..."
ssh root@marabot.tw1.ru "docker restart api_server-caddy-1"
echo "✅ Готово! Проверь страницу: https://marabot.tw1.ru/bloom.html"
echo "💡 Если изменения не видны, очисти кеш браузера (Ctrl+Shift+R)"

