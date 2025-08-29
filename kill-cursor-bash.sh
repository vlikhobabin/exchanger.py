#!/bin/bash

# Скрипт для мониторинга и завершения зависших bash процессов от Cursor IDE
# Автор: AI Assistant
# Дата создания: $(date)

LOG_FILE="/var/log/cursor-bash-monitor.log"
PID_FILE="/var/run/cursor-bash-monitor.pid"

# Функция логирования
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Проверка, не запущен ли уже скрипт
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        log_message "Скрипт уже запущен с PID $OLD_PID"
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

# Записываем PID текущего процесса
echo $$ > "$PID_FILE"

log_message "Запуск мониторинга зависших bash процессов Cursor IDE"

# Функция очистки при завершении
cleanup() {
    log_message "Завершение мониторинга bash процессов"
    rm -f "$PID_FILE"
    exit 0
}

# Обработчики сигналов
trap cleanup SIGTERM SIGINT

# Основной цикл мониторинга
while true; do
    # Найти bash процессы с высоким CPU (>50%)
    HIGH_CPU_BASH=$(ps aux | awk '/\/usr\/bin\/bash/ && $3 > 50 && !/awk/ {print $2 ":" $3 ":" $11}')
    
    if [[ ! -z "$HIGH_CPU_BASH" ]]; then
        log_message "Обнаружены зависшие bash процессы:"
        echo "$HIGH_CPU_BASH" | while IFS=':' read -r pid cpu cmd; do
            log_message "  PID: $pid, CPU: ${cpu}%, CMD: $cmd"
            
            # Проверяем, связан ли процесс с Cursor/shellIntegration
            CMDLINE=$(cat "/proc/$pid/cmdline" 2>/dev/null | tr '\0' ' ')
            if [[ "$CMDLINE" == *"shellIntegration"* ]] || [[ "$CMDLINE" == *"cursor"* ]] || [[ "$cpu" -gt 80 ]]; then
                log_message "Завершаю зависший процесс PID $pid (CPU: ${cpu}%)"
                kill -9 "$pid" 2>/dev/null
                if [ $? -eq 0 ]; then
                    log_message "Процесс PID $pid успешно завершен"
                else
                    log_message "Не удалось завершить процесс PID $pid"
                fi
            fi
        done
    fi
    
    # Дополнительная проверка: процессы bash старше 10 минут с высоким CPU
    OLD_BASH=$(ps -eo pid,etime,pcpu,cmd | awk '/\/usr\/bin\/bash/ && $3 > 30 {
        split($2, time, ":");
        if (length(time) > 2 || (length(time) == 2 && time[1] > 10)) {
            print $1 ":" $3
        }
    }')
    
    if [[ ! -z "$OLD_BASH" ]]; then
        echo "$OLD_BASH" | while IFS=':' read -r pid cpu; do
            log_message "Завершаю старый зависший bash процесс PID $pid (CPU: ${cpu}%)"
            kill -9 "$pid" 2>/dev/null
        done
    fi
    
    # Проверка каждые 15 секунд
    sleep 15
done