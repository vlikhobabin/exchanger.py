#!/bin/bash

# Universal Camunda Worker - Installation Script
# Скрипт для установки и настройки на VPS

set -e  # Остановка при ошибках

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="camunda-worker"
SERVICE_USER="camunda"
INSTALL_DIR="/opt/camunda-worker"
LOG_DIR="/var/log/camunda-worker"

echo "========================================"
echo "Universal Camunda Worker - Installation"
echo "========================================"

# Проверка прав root
if [[ $EUID -ne 0 ]]; then
   echo "❌ Этот скрипт должен быть запущен от имени root"
   exit 1
fi

# Функция логирования
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Обновление системы
log "🔄 Обновление системы..."
apt update && apt upgrade -y

# Установка зависимостей
log "📦 Установка системных зависимостей..."
apt install -y python3 python3-pip python3-venv supervisor nginx git curl wget

# Создание пользователя для сервиса
log "👤 Создание пользователя $SERVICE_USER..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -s /bin/false -m -d /home/$SERVICE_USER $SERVICE_USER
fi

# Создание директорий
log "📁 Создание директорий..."
mkdir -p $INSTALL_DIR
mkdir -p $LOG_DIR
chown $SERVICE_USER:$SERVICE_USER $LOG_DIR

# Копирование файлов
log "📋 Копирование файлов приложения..."
cp -r $SCRIPT_DIR/* $INSTALL_DIR/
chown -R $SERVICE_USER:$SERVICE_USER $INSTALL_DIR

# Создание виртуального окружения
log "🐍 Создание Python виртуального окружения..."
cd $INSTALL_DIR
sudo -u $SERVICE_USER python3 -m venv venv
sudo -u $SERVICE_USER ./venv/bin/pip install --upgrade pip

# Установка зависимостей Python
log "📦 Установка Python зависимостей..."
sudo -u $SERVICE_USER ./venv/bin/pip install -r requirements.txt

# Создание конфигурационного файла
log "⚙️  Создание конфигурационного файла..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
    cp $INSTALL_DIR/config.env.example $INSTALL_DIR/.env
    chown $SERVICE_USER:$SERVICE_USER $INSTALL_DIR/.env
    log "✅ Создан файл конфигурации: $INSTALL_DIR/.env"
    log "⚠️  ВАЖНО: Отредактируйте файл $INSTALL_DIR/.env с вашими настройками!"
fi

# Создание systemd сервиса
log "🔧 Создание systemd сервиса..."
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=Universal Camunda Worker
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin
ExecStart=$INSTALL_DIR/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# Настройки безопасности
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$LOG_DIR $INSTALL_DIR/logs

[Install]
WantedBy=multi-user.target
EOF

# Создание Supervisor конфигурации (альтернатива systemd)
log "🔧 Создание Supervisor конфигурации..."
cat > /etc/supervisor/conf.d/$SERVICE_NAME.conf << EOF
[program:$SERVICE_NAME]
command=$INSTALL_DIR/venv/bin/python main.py
directory=$INSTALL_DIR
user=$SERVICE_USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=$LOG_DIR/supervisor.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=5
environment=PATH="$INSTALL_DIR/venv/bin"
EOF

# Включение и запуск systemd сервиса
log "🚀 Настройка автозапуска сервиса..."
systemctl daemon-reload
systemctl enable $SERVICE_NAME

# Обновление Supervisor
supervisorctl reread
supervisorctl update

# Создание скриптов управления
log "📜 Создание скриптов управления..."

# Скрипт запуска
cat > $INSTALL_DIR/start.sh << 'EOF'
#!/bin/bash
systemctl start camunda-worker
systemctl status camunda-worker
EOF

# Скрипт остановки
cat > $INSTALL_DIR/stop.sh << 'EOF'
#!/bin/bash
systemctl stop camunda-worker
EOF

# Скрипт перезапуска
cat > $INSTALL_DIR/restart.sh << 'EOF'
#!/bin/bash
systemctl restart camunda-worker
systemctl status camunda-worker
EOF

# Скрипт проверки статуса
cat > $INSTALL_DIR/status.sh << 'EOF'
#!/bin/bash
echo "=== SYSTEMD STATUS ==="
systemctl status camunda-worker

echo -e "\n=== APPLICATION STATUS ==="
cd /opt/camunda-worker
./venv/bin/python status_check.py

echo -e "\n=== RECENT LOGS ==="
journalctl -u camunda-worker -n 20 --no-pager
EOF

# Скрипт просмотра логов
cat > $INSTALL_DIR/logs.sh << 'EOF'
#!/bin/bash
if [ "$1" = "-f" ]; then
    journalctl -u camunda-worker -f
else
    journalctl -u camunda-worker -n 50 --no-pager
fi
EOF

# Установка прав на скрипты
chmod +x $INSTALL_DIR/*.sh

# Создание логротейт конфигурации
log "📊 Настройка ротации логов..."
cat > /etc/logrotate.d/$SERVICE_NAME << EOF
$LOG_DIR/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 $SERVICE_USER $SERVICE_USER
    postrotate
        systemctl reload $SERVICE_NAME > /dev/null 2>&1 || true
    endscript
}
EOF

# Настройка файрвола (опционально)
if command -v ufw &> /dev/null; then
    log "🔥 Настройка файрвола..."
    # Разрешаем только необходимые порты
    # ufw allow 22/tcp  # SSH
    # ufw allow 80/tcp  # HTTP
    # ufw allow 443/tcp # HTTPS
fi

# Финальная проверка
log "✅ Проверка установки..."
if systemctl is-enabled $SERVICE_NAME &>/dev/null; then
    log "✅ Сервис включен в автозапуск"
else
    log "❌ Сервис не включен в автозапуск"
fi

echo ""
echo "========================================"
echo "✅ УСТАНОВКА ЗАВЕРШЕНА!"
echo "========================================"
echo ""
echo "📂 Директория установки: $INSTALL_DIR"
echo "📋 Файл конфигурации: $INSTALL_DIR/.env" 
echo "📊 Директория логов: $LOG_DIR"
echo ""
echo "🔧 КОМАНДЫ УПРАВЛЕНИЯ:"
echo "  Запуск:      systemctl start $SERVICE_NAME"
echo "  Остановка:   systemctl stop $SERVICE_NAME"
echo "  Перезапуск:  systemctl restart $SERVICE_NAME"
echo "  Статус:      systemctl status $SERVICE_NAME"
echo "  Логи:        journalctl -u $SERVICE_NAME -f"
echo ""
echo "📜 АЛЬТЕРНАТИВНЫЕ КОМАНДЫ:"
echo "  $INSTALL_DIR/start.sh     - запуск"
echo "  $INSTALL_DIR/stop.sh      - остановка"
echo "  $INSTALL_DIR/restart.sh   - перезапуск"
echo "  $INSTALL_DIR/status.sh    - статус"
echo "  $INSTALL_DIR/logs.sh      - логи"
echo ""
echo "⚠️  ВАЖНО:"
echo "1. Отредактируйте файл конфигурации: $INSTALL_DIR/.env"
echo "2. Проверьте подключение к Camunda и RabbitMQ: $INSTALL_DIR/status.sh"
echo "3. Запустите сервис: systemctl start $SERVICE_NAME"
echo ""
echo "========================================" 