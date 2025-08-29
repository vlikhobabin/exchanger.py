#!/bin/bash
set -e

# Скрипт для удаления systemd-сервисов Exchanger.py

echo ">>> Stopping services..."
sudo systemctl stop exchanger-camunda-worker.service || true
sudo systemctl stop exchanger-task-creator.service || true

echo ">>> Disabling services from starting on boot..."
sudo systemctl disable exchanger-camunda-worker.service || true
sudo systemctl disable exchanger-task-creator.service || true

echo ">>> Removing service files..."
sudo rm -f /etc/systemd/system/exchanger-camunda-worker.service
sudo rm -f /etc/systemd/system/exchanger-task-creator.service

echo ">>> Reloading systemd daemon..."
sudo systemctl daemon-reload

echo ">>> Uninstallation complete." 