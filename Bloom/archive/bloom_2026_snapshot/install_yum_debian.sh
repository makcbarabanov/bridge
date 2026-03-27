#!/bin/bash
# Скрипт для установки yum на Debian (не рекомендуется, используй apt)

echo "⚠️ ВНИМАНИЕ: На Debian рекомендуется использовать 'apt' вместо 'yum'"
echo ""
echo "Но если тебе ОЧЕНЬ нужно yum, можно попробовать:"
echo ""
echo "Вариант 1: Через snap (если snap установлен)"
echo "sudo snap install yum"
echo ""
echo "Вариант 2: Компиляция из исходников (сложно и не рекомендуется)"
echo ""
echo "Вариант 3: Использовать Docker с CentOS/Fedora контейнером"
echo ""
echo "✅ РЕКОМЕНДАЦИЯ: Используй 'apt' вместо 'yum'"
echo ""
echo "Примеры использования apt:"
echo "  sudo apt update                    # обновить список пакетов"
echo "  sudo apt install <пакет>           # установить пакет"
echo "  sudo apt upgrade                   # обновить установленные пакеты"
echo "  sudo apt search <название>         # поиск пакета"
echo "  sudo apt remove <пакет>            # удалить пакет"

