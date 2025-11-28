#!/bin/bash
set -e

# ============================================================================
# Скрипт для удаления systemd-сервисов Exchanger.py
# ============================================================================

echo "============================================================"
echo "Exchanger.py - Services Uninstallation"
echo "============================================================"
echo ""

# Остановка всех сервисов
echo ">>> Stopping all services..."
sudo systemctl stop exchanger-camunda-worker-prod 2>/dev/null || true
sudo systemctl stop exchanger-task-creator-prod 2>/dev/null || true
sudo systemctl stop exchanger-camunda-worker-dev 2>/dev/null || true
sudo systemctl stop exchanger-task-creator-dev 2>/dev/null || true

# Отключение автозапуска
echo ">>> Disabling services..."
sudo systemctl disable exchanger-camunda-worker-prod 2>/dev/null || true
sudo systemctl disable exchanger-task-creator-prod 2>/dev/null || true
sudo systemctl disable exchanger-camunda-worker-dev 2>/dev/null || true
sudo systemctl disable exchanger-task-creator-dev 2>/dev/null || true

# Удаление unit-файлов
echo ">>> Removing service files..."
sudo rm -f /etc/systemd/system/exchanger-camunda-worker-prod.service
sudo rm -f /etc/systemd/system/exchanger-task-creator-prod.service
sudo rm -f /etc/systemd/system/exchanger-camunda-worker-dev.service
sudo rm -f /etc/systemd/system/exchanger-task-creator-dev.service

# Удаление старых сервисов (без суффикса)
sudo rm -f /etc/systemd/system/exchanger-camunda-worker.service
sudo rm -f /etc/systemd/system/exchanger-task-creator.service

# Перезагрузка systemd
echo ">>> Reloading systemd daemon..."
sudo systemctl daemon-reload
sudo systemctl reset-failed

echo ""
echo "============================================================"
echo "Uninstallation complete!"
echo "============================================================"
echo ""
echo "All Exchanger.py services have been removed."
echo ""
echo "Note: Log files were NOT removed. They are located at:"
echo "  - /opt/exchanger.py/logs/prod/"
echo "  - /opt/exchanger.py/logs/dev/"
echo ""
echo "To reinstall, run: ./install_services.sh"
