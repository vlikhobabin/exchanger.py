# Решение проблемы зависания bash процессов в Cursor IDE

## Описание проблемы

При работе с Cursor IDE на Ubuntu серверах (особенно с ограниченными ресурсами) возникает проблема зависания bash процессов. Процессы `/usr/bin/bash` начинают потреблять 100% CPU и не завершаются автоматически.

## Реализованное решение

### 1. Workaround в .bashrc

В файле `/root/.bashrc` добавлены проверки для предотвращения зависаний:

```bash
# CURSOR IDE WORKAROUND - Prevent hanging bash processes
if [[ "$PAGER" == "head -n 10000 | cat" || "$COMPOSER_NO_INTERACTION" == "1" ]]; then
  return
fi

# Alternative check for Cursor/VSCode terminal integration
if [[ "$TERM_PROGRAM" == "vscode" || "$TERM_PROGRAM" == "cursor" ]]; then
  export PS1='\u@\h:\w\$ '
  return
fi

# Check for Cursor shell integration script in command line
if [[ "$0" == *"shellIntegration-bash.sh"* ]]; then
  return
fi
```

### 2. Автоматический мониторинг процессов

Создан systemd сервис `cursor-bash-monitor` который:
- Мониторит bash процессы каждые 15 секунд
- Завершает процессы с CPU > 50% связанные с Cursor
- Завершает старые bash процессы (>10 минут) с высоким CPU
- Ведет детальные логи в `/var/log/cursor-bash-monitor.log`

## Управление сервисом

Используйте скрипт `cursor-monitor-control.sh`:

```bash
# Показать статус
./cursor-monitor-control.sh status

# Просмотреть логи
./cursor-monitor-control.sh logs

# Перезапустить сервис
./cursor-monitor-control.sh restart

# Остановить сервис
./cursor-monitor-control.sh stop

# Запустить сервис
./cursor-monitor-control.sh start

# Включить автозапуск
./cursor-monitor-control.sh enable

# Отключить автозапуск
./cursor-monitor-control.sh disable
```

## Файлы решения

1. `/root/.bashrc` - содержит workaround для предотвращения зависаний
2. `/opt/exchanger.py/kill-cursor-bash.sh` - скрипт мониторинга процессов
3. `/etc/systemd/system/cursor-bash-monitor.service` - systemd сервис
4. `/opt/exchanger.py/cursor-monitor-control.sh` - скрипт управления сервисом
5. `/var/log/cursor-bash-monitor.log` - лог файл мониторинга

## Проверка работы

```bash
# Проверить статус сервиса
systemctl status cursor-bash-monitor

# Проверить активные bash процессы
ps aux | grep bash | grep -v grep

# Просмотреть логи мониторинга
tail -f /var/log/cursor-bash-monitor.log
```

## Безопасность

Сервис настроен с ограничениями:
- Максимум 50MB памяти
- Максимум 10% CPU
- Изолированная файловая система
- Ограниченные права доступа

## Автоматический запуск

Сервис настроен на автоматический запуск при загрузке системы и автоматический перезапуск при сбоях.

---

**Дата создания:** $(date)
**Статус:** Активно, протестировано
**Автор:** AI Assistant
