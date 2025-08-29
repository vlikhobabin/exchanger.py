#!/bin/bash

# Безопасный запуск Cursor с ограничением ресурсов

echo "Запуск Cursor с оптимизированными настройками..."

# Установка переменных окружения для ограничения ресурсов
export ELECTRON_NO_ATTACH_CONSOLE=1
export ELECTRON_DISABLE_SECURITY_WARNINGS=true
export NODE_OPTIONS="--max-old-space-size=1024"

# Ограничение использования CPU и памяти через systemd-run (если доступно)
if command -v systemd-run &> /dev/null; then
    echo "Запуск через systemd-run с ограничениями..."
    systemd-run --user --scope -p MemoryMax=2G -p CPUQuota=80% cursor "$@"
else
    # Альтернативный запуск с nice и ionice
    echo "Запуск с пониженным приоритетом..."
    nice -n 5 ionice -c 2 -n 4 cursor "$@"
fi
