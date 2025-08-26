#!/bin/bash
set -e

# Скрипт для экспорта логов systemd в текстовые файлы

echo ">>> Exporting logs for Universal Worker..."
journalctl -u exchanger-worker --no-pager > ~/exchanger-worker-logs.txt

echo ">>> Exporting logs for Task Creator..."
journalctl -u exchanger-creator --no-pager > ~/exchanger-creator-logs.txt

echo ">>> Logs exported successfully to your home directory (~/):"
echo "    - exchanger-worker-logs.txt"
echo "    - exchanger-creator-logs.txt" 