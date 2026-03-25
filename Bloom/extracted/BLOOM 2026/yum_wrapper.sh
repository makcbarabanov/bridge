#!/bin/bash
# Простая обёртка yum -> apt для уроков Linux на Debian

# Создай этот скрипт на сервере:
# sudo nano /usr/local/bin/yum
# Скопируй сюда содержимое
# sudo chmod +x /usr/local/bin/yum

case "$1" in
    install)
        shift
        sudo apt install -y "$@"
        ;;
    update)
        if [ "$2" = "all" ] || [ -z "$2" ]; then
            sudo apt update && sudo apt upgrade -y
        else
            sudo apt update
        fi
        ;;
    upgrade)
        sudo apt upgrade -y
        ;;
    search)
        if [ $# -lt 2 ]; then
            echo "Error: No search term specified"
            echo "Usage: yum search <term>"
            exit 1
        fi
        shift
        apt search "$@"
        ;;
    list)
        if [ "$2" = "installed" ]; then
            apt list --installed
        else
            apt list "$@"
        fi
        ;;
    remove)
        shift
        sudo apt remove -y "$@"
        ;;
    info)
        shift
        apt show "$@"
        ;;
    clean)
        sudo apt clean
        sudo apt autoclean
        ;;
    --help)
        echo "yum wrapper for Debian (uses apt)"
        echo ""
        echo "Usage: yum <command> [options]"
        echo ""
        echo "Commands:"
        echo "  install <package>  - Install package (apt install)"
        echo "  update             - Update package lists and upgrade (apt update && apt upgrade)"
        echo "  upgrade            - Upgrade packages (apt upgrade)"
        echo "  search <package>   - Search for package (apt search)"
        echo "  list installed     - List installed packages (apt list --installed)"
        echo "  remove <package>   - Remove package (apt remove)"
        echo "  info <package>     - Show package info (apt show)"
        echo "  clean              - Clean cache (apt clean)"
        ;;
    *)
        echo "yum: command not found: $1"
        echo "Run 'yum --help' for usage"
        exit 1
        ;;
esac

