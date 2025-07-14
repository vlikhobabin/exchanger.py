#!/bin/bash
set -e

# Скрипт для удаления systemd-сервисов Exchanger.py

echo ">>> Stopping services..."
sudo systemctl stop exchanger-worker.service || true
sudo systemctl stop exchanger-creator.service || true

echo ">>> Disabling services from starting on boot..."
sudo systemctl disable exchanger-worker.service || true
sudo systemctl disable exchanger-creator.service || true

echo ">>> Removing service files..."
sudo rm -f /etc/systemd/system/exchanger-worker.service
sudo rm -f /etc/systemd/system/exchanger-creator.service

echo ">>> Reloading systemd daemon..."
sudo systemctl daemon-reload

echo ">>> Uninstallation complete." 