#!/bin/bash
set -e

# ============================================================================
# Скрипт для создания systemd-сервисов для Exchanger.py
# Создает 4 сервиса: prod и dev версии для camunda-worker и task-creator
# ============================================================================

PROJECT_DIR="/opt/exchanger.py"
CURRENT_USER=$(whoami)

echo "============================================================"
echo "Exchanger.py - Services Installation"
echo "============================================================"
echo "Project directory: $PROJECT_DIR"
echo "Running as user: $CURRENT_USER"
echo ""

# ============================================================================
# PRODUCTION SERVICES
# ============================================================================

echo ">>> Creating systemd service for Camunda Worker [PROD]..."
sudo tee /etc/systemd/system/exchanger-camunda-worker-prod.service > /dev/null <<EOF
[Unit]
Description=Exchanger.py - Camunda Worker [PROD]
After=network.target
Documentation=https://github.com/vlikhobabin/exchanger.py

[Service]
Type=simple
User=${CURRENT_USER}
Group=${CURRENT_USER}
WorkingDirectory=${PROJECT_DIR}
Environment="EXCHANGER_ENV=prod"
ExecStart=${PROJECT_DIR}/venv/bin/python -u camunda-worker/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=exchanger-camunda-worker-prod

# Ограничения ресурсов (опционально)
# MemoryMax=1G
# CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF

echo ">>> Creating systemd service for Task Creator [PROD]..."
sudo tee /etc/systemd/system/exchanger-task-creator-prod.service > /dev/null <<EOF
[Unit]
Description=Exchanger.py - Task Creator [PROD]
After=network.target
Documentation=https://github.com/vlikhobabin/exchanger.py

[Service]
Type=simple
User=${CURRENT_USER}
Group=${CURRENT_USER}
WorkingDirectory=${PROJECT_DIR}
Environment="EXCHANGER_ENV=prod"
ExecStart=${PROJECT_DIR}/venv/bin/python -u task-creator/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=exchanger-task-creator-prod

[Install]
WantedBy=multi-user.target
EOF

# ============================================================================
# DEVELOPMENT SERVICES
# ============================================================================

echo ">>> Creating systemd service for Camunda Worker [DEV]..."
sudo tee /etc/systemd/system/exchanger-camunda-worker-dev.service > /dev/null <<EOF
[Unit]
Description=Exchanger.py - Camunda Worker [DEV]
After=network.target
Documentation=https://github.com/vlikhobabin/exchanger.py

[Service]
Type=simple
User=${CURRENT_USER}
Group=${CURRENT_USER}
WorkingDirectory=${PROJECT_DIR}
Environment="EXCHANGER_ENV=dev"
ExecStart=${PROJECT_DIR}/venv/bin/python -u camunda-worker/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=exchanger-camunda-worker-dev

[Install]
WantedBy=multi-user.target
EOF

echo ">>> Creating systemd service for Task Creator [DEV]..."
sudo tee /etc/systemd/system/exchanger-task-creator-dev.service > /dev/null <<EOF
[Unit]
Description=Exchanger.py - Task Creator [DEV]
After=network.target
Documentation=https://github.com/vlikhobabin/exchanger.py

[Service]
Type=simple
User=${CURRENT_USER}
Group=${CURRENT_USER}
WorkingDirectory=${PROJECT_DIR}
Environment="EXCHANGER_ENV=dev"
ExecStart=${PROJECT_DIR}/venv/bin/python -u task-creator/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=exchanger-task-creator-dev

[Install]
WantedBy=multi-user.target
EOF

# ============================================================================
# Создание директорий для логов
# ============================================================================

echo ">>> Creating log directories..."
mkdir -p ${PROJECT_DIR}/logs/prod
mkdir -p ${PROJECT_DIR}/logs/dev
mkdir -p ${PROJECT_DIR}/logs/prod/debug
mkdir -p ${PROJECT_DIR}/logs/dev/debug

# ============================================================================
# Перезагрузка systemd и включение сервисов
# ============================================================================

echo ">>> Reloading systemd daemon..."
sudo systemctl daemon-reload

echo ">>> Enabling PROD services to start on boot..."
sudo systemctl enable exchanger-camunda-worker-prod.service
sudo systemctl enable exchanger-task-creator-prod.service

echo ">>> DEV services will NOT auto-start on boot (manual start only)"
# Не включаем dev сервисы в автозапуск - это безопаснее

# ============================================================================
# Удаление старых сервисов (без суффикса -prod/-dev)
# ============================================================================

echo ">>> Checking for legacy services..."
if systemctl list-unit-files | grep -q "exchanger-camunda-worker.service"; then
    echo "   Stopping and disabling legacy exchanger-camunda-worker.service..."
    sudo systemctl stop exchanger-camunda-worker.service 2>/dev/null || true
    sudo systemctl disable exchanger-camunda-worker.service 2>/dev/null || true
    sudo rm -f /etc/systemd/system/exchanger-camunda-worker.service
fi

if systemctl list-unit-files | grep -q "exchanger-task-creator.service"; then
    echo "   Stopping and disabling legacy exchanger-task-creator.service..."
    sudo systemctl stop exchanger-task-creator.service 2>/dev/null || true
    sudo systemctl disable exchanger-task-creator.service 2>/dev/null || true
    sudo rm -f /etc/systemd/system/exchanger-task-creator.service
fi

sudo systemctl daemon-reload

# ============================================================================
# Запуск PROD сервисов
# ============================================================================

echo ">>> Starting PROD services..."
sudo systemctl start exchanger-camunda-worker-prod.service
sudo systemctl start exchanger-task-creator-prod.service

# ============================================================================
# Финальный отчет
# ============================================================================

echo ""
echo "============================================================"
echo "Installation complete!"
echo "============================================================"
echo ""
echo "Created services:"
echo "  PRODUCTION:"
echo "    - exchanger-camunda-worker-prod.service (enabled, started)"
echo "    - exchanger-task-creator-prod.service (enabled, started)"
echo "  DEVELOPMENT:"
echo "    - exchanger-camunda-worker-dev.service (disabled)"
echo "    - exchanger-task-creator-dev.service (disabled)"
echo ""
echo "Configuration files:"
echo "  - ${PROJECT_DIR}/.env.prod (production)"
echo "  - ${PROJECT_DIR}/.env.dev (development)"
echo ""
echo "Log directories:"
echo "  - ${PROJECT_DIR}/logs/prod/"
echo "  - ${PROJECT_DIR}/logs/dev/"
echo ""
echo "Usage:"
echo "  Start prod:    ./start_services.sh prod"
echo "  Start dev:     ./start_services.sh dev"
echo "  Stop prod:     ./stop_services.sh prod"
echo "  Stop dev:      ./stop_services.sh dev"
echo "  Restart prod:  ./restart_services.sh prod"
echo "  Status:        ./status_services.sh [prod|dev|all]"
echo ""
echo "Current PROD status:"
sudo systemctl status exchanger-camunda-worker-prod exchanger-task-creator-prod --no-pager -l | head -30
