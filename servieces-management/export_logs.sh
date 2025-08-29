#!/bin/bash
set -e

# Скрипт для экспорта логов systemd в текстовые файлы

echo ">>> Exporting logs for Camunda Worker..."
journalctl -u exchanger-camunda-worker --no-pager > ~/exchanger-camunda-worker-logs.txt

echo ">>> Exporting logs for Task Creator..."
journalctl -u exchanger-task-creator --no-pager > ~/exchanger-task-creator-logs.txt

echo ">>> Logs exported successfully to your home directory (~/):"
echo "    - exchanger-camunda-worker-logs.txt"
echo "    - exchanger-task-creator-logs.txt" 