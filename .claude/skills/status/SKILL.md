---
name: status
description: Диагностика системы Exchanger.py — проверка сервисов, очередей и ошибок
disable-model-invocation: true
user-invocable: true
argument: "[prod|dev|all] (default: all)"
---

# /status — Диагностика системы

## Задача

Выполнить комплексную проверку состояния системы Exchanger.py и показать результат пользователю.

## Аргумент

- `prod` — только Production среда
- `dev` — только Development среда
- `all` (или без аргумента) — обе среды

## Шаги выполнения

### 1. Проверка systemd-сервисов

Выполни `systemctl status` для соответствующих сервисов:

- **Production:** `exchanger-camunda-worker-prod`, `exchanger-task-creator-prod`
- **Development:** `exchanger-camunda-worker-dev`, `exchanger-task-creator-dev`

Покажи для каждого: active/inactive, uptime, memory usage.

### 2. Проверка RabbitMQ очередей

Запусти скрипт проверки очередей:

```bash
source /opt/exchanger.py/venv/bin/activate
EXCHANGER_ENV={env} python /opt/exchanger.py/camunda-worker/tools/check_queues.py
```

Если аргумент `all` — запусти для обеих сред (prod и dev).

### 3. Проверка последних ошибок в логах

Прочитай последние 20 строк из файлов ошибок:

- `logs/{env}/camunda-worker.log` — ищи строки с `ERROR` или `CRITICAL`
- `logs/{env}/task-creator.log` — ищи строки с `ERROR` или `CRITICAL`

Используй `grep -i "ERROR\|CRITICAL" logs/{env}/*.log | tail -20` для каждой среды.

### 4. Формат вывода

Выведи результат в виде таблицы:

```
## Статус системы [{env}]

### Сервисы
| Сервис | Статус | Uptime | Memory |
|--------|--------|--------|--------|
| camunda-worker-{env} | active | 3d 5h | 120MB |
| task-creator-{env}   | active | 3d 5h | 85MB  |

### Очереди RabbitMQ
[вывод check_queues.py]

### Последние ошибки (последние 20)
[ошибки из логов или "Ошибок не найдено"]
```
