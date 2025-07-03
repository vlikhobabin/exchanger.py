#!/bin/bash

# Exchanger.py - Universal Integration Platform
# Скрипт установки и настройки всего проекта

set -e  # Остановка при ошибках

echo "========================================"
echo "Exchanger.py - Installation Script"
echo "Universal Integration Platform"
echo "========================================"

# Функция логирования
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Проверка версии Python
log "🐍 Проверка версии Python..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Установите Python 3.8 или выше."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
log "✅ Python версия: $PYTHON_VERSION"

# Создание виртуального окружения
log "📦 Создание виртуального окружения..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    log "✅ Виртуальное окружение создано"
else
    log "📦 Виртуальное окружение уже существует"
fi

# Активация виртуального окружения
log "🔧 Активация виртуального окружения..."
source venv/bin/activate

# Обновление pip
log "⬆️ Обновление pip..."
pip install --upgrade pip

# Установка зависимостей
log "📦 Установка зависимостей..."
pip install -r requirements.txt

# Создание конфигурационного файла
log "⚙️ Настройка конфигурации..."
if [ ! -f ".env" ]; then
    cp config.env.example .env
    log "✅ Создан файл конфигурации: .env"
    log "⚠️  ВАЖНО: Отредактируйте файл .env с вашими настройками!"
else
    log "📝 Файл конфигурации .env уже существует"
fi

# Создание директорий для логов
log "📁 Создание директорий..."
mkdir -p logs
mkdir -p universal-worker.py/logs
mkdir -p task-creator.py/logs

# Инициализация git репозитория (если еще не инициализирован)
if [ ! -d ".git" ]; then
    log "🔄 Инициализация git репозитория..."
    git init
    git add .
    git commit -m "Initial commit: Exchanger.py Universal Integration Platform"
    
    # Добавление remote origin (если указан)
    if [ "$1" != "" ]; then
        git remote add origin "$1"
        log "✅ Добавлен remote origin: $1"
    else
        log "💡 Для добавления remote origin выполните:"
        log "   git remote add origin git@github.com:vlikhobabin/exchanger.py.git"
    fi
else
    log "📝 Git репозиторий уже инициализирован"
fi

# Создание скриптов управления
log "📜 Создание скриптов управления..."

# Скрипт запуска Universal Worker
cat > start-universal-worker.sh << 'EOF'
#!/bin/bash
echo "🚀 Запуск Universal Worker..."
cd universal-worker.py
source ../venv/bin/activate
python main.py
EOF

# Скрипт запуска Task Creator
cat > start-task-creator.sh << 'EOF'
#!/bin/bash
echo "🚀 Запуск Task Creator..."
cd task-creator.py
source ../venv/bin/activate
python main.py
EOF

# Скрипт запуска всех сервисов
cat > start-all.sh << 'EOF'
#!/bin/bash
echo "🚀 Запуск всех сервисов Exchanger.py..."

# Активация виртуального окружения
source venv/bin/activate

# Запуск Universal Worker в фоне
echo "🔄 Запуск Universal Worker..."
cd universal-worker.py
python main.py &
UNIVERSAL_WORKER_PID=$!
cd ..

# Небольшая пауза
sleep 2

# Запуск Task Creator в фоне
echo "📨 Запуск Task Creator..."
cd task-creator.py
python main.py &
TASK_CREATOR_PID=$!
cd ..

echo "✅ Все сервисы запущены!"
echo "Universal Worker PID: $UNIVERSAL_WORKER_PID"
echo "Task Creator PID: $TASK_CREATOR_PID"
echo ""
echo "Для остановки нажмите Ctrl+C или выполните: ./stop-all.sh"

# Ожидание сигнала завершения
trap 'echo "Завершение всех сервисов..."; kill $UNIVERSAL_WORKER_PID $TASK_CREATOR_PID; wait' SIGTERM SIGINT

wait
EOF

# Скрипт остановки всех сервисов
cat > stop-all.sh << 'EOF'
#!/bin/bash
echo "⏹️ Остановка всех сервисов Exchanger.py..."

# Остановка процессов Python
pkill -f "python main.py"

echo "✅ Все сервисы остановлены"
EOF

# Скрипт статуса
cat > status.sh << 'EOF'
#!/bin/bash
echo "📊 Статус сервисов Exchanger.py"
echo "================================"

source venv/bin/activate

echo ""
echo "🔄 Universal Worker:"
if pgrep -f "universal-worker.py/main.py" > /dev/null; then
    echo "  ✅ Запущен (PID: $(pgrep -f 'universal-worker.py/main.py'))"
    cd universal-worker.py
    python tools/worker_diagnostics.py 2>/dev/null || echo "  ⚠️ Диагностика недоступна"
    cd ..
else
    echo "  ❌ Остановлен"
fi

echo ""
echo "📨 Task Creator:"
if pgrep -f "task-creator.py/main.py" > /dev/null; then
    echo "  ✅ Запущен (PID: $(pgrep -f 'task-creator.py/main.py'))"
else
    echo "  ❌ Остановлен"
fi

echo ""
echo "🐰 RabbitMQ Queues:"
cd universal-worker.py
python tools/check_queues.py 2>/dev/null || echo "  ⚠️ Проверка очередей недоступна"
cd ..
EOF

# Скрипт тестирования
cat > test.sh << 'EOF'
#!/bin/bash
echo "🧪 Тестирование Exchanger.py..."

source venv/bin/activate

echo ""
echo "🔄 Тестирование Universal Worker..."
cd universal-worker.py
python tools/status_check.py
cd ..

echo ""
echo "📨 Тестирование Task Creator..."
cd task-creator.py
python simple_test.py
cd ..

echo ""
echo "✅ Тестирование завершено"
EOF

# Установка прав выполнения на скрипты
chmod +x *.sh

log "✅ Скрипты управления созданы:"
log "   ./start-universal-worker.sh - запуск Universal Worker"
log "   ./start-task-creator.sh     - запуск Task Creator"
log "   ./start-all.sh              - запуск всех сервисов"
log "   ./stop-all.sh               - остановка всех сервисов"
log "   ./status.sh                 - статус сервисов"
log "   ./test.sh                   - тестирование"

echo ""
echo "========================================"
echo "✅ УСТАНОВКА ЗАВЕРШЕНА!"
echo "========================================"
echo ""
echo "📂 Структура проекта:"
echo "  📁 universal-worker.py/     - Camunda ↔ RabbitMQ интеграция"
echo "  📁 task-creator.py/         - RabbitMQ ↔ External Systems интеграция"
echo "  📁 task-tracker.py/         - планируется (мониторинг задач)"
echo ""
echo "🔧 СЛЕДУЮЩИЕ ШАГИ:"
echo "1. Отредактируйте файл .env с вашими настройками"
echo "2. Протестируйте подключения: ./test.sh"
echo "3. Запустите сервисы: ./start-all.sh"
echo "4. Проверьте статус: ./status.sh"
echo ""
echo "📚 Документация:"
echo "  README.md                    - обзор платформы"
echo "  universal-worker.py/README.md - детали Universal Worker"
echo "  task-creator.py/README.md     - детали Task Creator"
echo ""
echo "🔗 Git репозиторий:"
if [ "$1" != "" ]; then
    echo "  git remote add origin $1"
    echo "  git push -u origin main"
else
    echo "  git remote add origin git@github.com:vlikhobabin/exchanger.py.git"
    echo "  git push -u origin main"
fi
echo ""
echo "========================================" 