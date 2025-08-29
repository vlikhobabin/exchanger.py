#!/bin/bash

# Скрипт управления сервисом мониторинга Cursor bash процессов
# Использование: ./cursor-monitor-control.sh [start|stop|restart|status|enable|disable|logs]

SERVICE_NAME="cursor-bash-monitor"
LOG_FILE="/var/log/cursor-bash-monitor.log"

case "$1" in
    start)
        echo "Запуск сервиса мониторинга Cursor bash процессов..."
        systemctl start "$SERVICE_NAME"
        systemctl status "$SERVICE_NAME" --no-pager -l
        ;;
    stop)
        echo "Остановка сервиса мониторинга..."
        systemctl stop "$SERVICE_NAME"
        echo "Сервис остановлен"
        ;;
    restart)
        echo "Перезапуск сервиса мониторинга..."
        systemctl restart "$SERVICE_NAME"
        systemctl status "$SERVICE_NAME" --no-pager -l
        ;;
    status)
        systemctl status "$SERVICE_NAME" --no-pager -l
        ;;
    enable)
        echo "Включение автозапуска сервиса..."
        systemctl enable "$SERVICE_NAME"
        systemctl start "$SERVICE_NAME"
        echo "Сервис включен и запущен"
        ;;
    disable)
        echo "Отключение автозапуска сервиса..."
        systemctl disable "$SERVICE_NAME"
        systemctl stop "$SERVICE_NAME"
        echo "Сервис отключен и остановлен"
        ;;
    logs)
        echo "Просмотр логов сервиса (последние 50 строк):"
        echo "=================================="
        if [ -f "$LOG_FILE" ]; then
            tail -50 "$LOG_FILE"
        else
            echo "Лог файл не найден: $LOG_FILE"
        fi
        echo "=================================="
        echo "Системные логи:"
        journalctl -u "$SERVICE_NAME" -n 20 --no-pager
        ;;
    install)
        echo "Установка и настройка сервиса..."
        systemctl daemon-reload
        systemctl enable "$SERVICE_NAME"
        systemctl start "$SERVICE_NAME"
        echo "Сервис установлен и запущен"
        systemctl status "$SERVICE_NAME" --no-pager -l
        ;;
    *)
        echo "Использование: $0 {start|stop|restart|status|enable|disable|logs|install}"
        echo ""
        echo "Команды:"
        echo "  start    - Запустить сервис"
        echo "  stop     - Остановить сервис"
        echo "  restart  - Перезапустить сервис"
        echo "  status   - Показать статус сервиса"
        echo "  enable   - Включить автозапуск"
        echo "  disable  - Отключить автозапуск"
        echo "  logs     - Показать логи"
        echo "  install  - Установить и запустить сервис"
        exit 1
        ;;
esac