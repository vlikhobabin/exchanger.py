#!/bin/bash
set -e

# Скрипт для создания systemd-сервисов для Exchanger.py

echo ">>> Creating systemd service for Camunda Worker..."

# Создаем файл сервиса для Camunda Worker
# Исполняться будет от имени текущего пользователя, который запускает скрипт
# Рабочая директория устанавливается в корень проекта
# Переменные окружения подгружаются из .env файла
sudo tee /etc/systemd/system/exchanger-camunda-worker.service > /dev/null <<EOF
[Unit]
Description=Exchanger.py - Camunda Worker
After=network.target

[Service]
User=$(whoami)
Group=$(whoami)
WorkingDirectory=/opt/exchanger.py
ExecStart=/opt/exchanger.py/venv/bin/python -u camunda-worker/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=exchanger-camunda-worker
EnvironmentFile=/opt/exchanger.py/.env

[Install]
WantedBy=multi-user.target
EOF

echo ">>> Creating systemd service for Task Creator..."

# Создаем файл сервиса для Task Creator
sudo tee /etc/systemd/system/exchanger-task-creator.service > /dev/null <<EOF
[Unit]
Description=Exchanger.py - Task Creator
After=network.target

[Service]
User=$(whoami)
Group=$(whoami)
WorkingDirectory=/opt/exchanger.py
ExecStart=/opt/exchanger.py/venv/bin/python -u task-creator/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=exchanger-task-creator
EnvironmentFile=/opt/exchanger.py/.env

[Install]
WantedBy=multi-user.target
EOF

echo ">>> Reloading systemd daemon..."
sudo systemctl daemon-reload

echo ">>> Enabling services to start on boot..."
sudo systemctl enable exchanger-camunda-worker.service
sudo systemctl enable exchanger-task-creator.service

echo ">>> Starting services..."
sudo systemctl start exchanger-camunda-worker.service
sudo systemctl start exchanger-task-creator.service

echo ">>> Installation complete. Check status with: sudo systemctl status exchanger-camunda-worker exchanger-task-creator" 