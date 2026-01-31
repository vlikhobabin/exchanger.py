---
name: debug-task
description: Отладка задачи Camunda — полный путь через систему
disable-model-invocation: true
user-invocable: true
argument: "[task-id]"
---

# /debug-task — Отладка задачи Camunda

## Задача

Проследить полный путь задачи Camunda через все компоненты системы Exchanger.py.

## Аргумент

- `[task-id]` — ID задачи Camunda (обязательный)

Если аргумент не указан — спроси у пользователя.

## Шаги выполнения

### 1. Проверка задачи в Camunda REST API

Определи среду из конфигурации и выполни запрос к Camunda REST API:

```bash
source /opt/exchanger.py/venv/bin/activate
python -c "
import requests
from dotenv import load_dotenv
import os

load_dotenv('/opt/exchanger.py/.env.prod')
base_url = os.getenv('CAMUNDA_BASE_URL')
auth = (os.getenv('CAMUNDA_AUTH_USERNAME'), os.getenv('CAMUNDA_AUTH_PASSWORD'))

# Поиск external task
resp = requests.get(f'{base_url}/external-task/{task_id}', auth=auth, verify=False)
print(resp.json() if resp.ok else f'Not found: {resp.status_code}')
"
```

Покажи: статус задачи, worker ID, lock expiration, topic name, переменные.

### 2. Поиск в логах

Ищи task-id во всех логах обеих сред:

```bash
grep -r "{task-id}" /opt/exchanger.py/logs/ --include="*.log" | tail -30
```

Покажи найденные записи с временными метками.

### 3. Проверка RabbitMQ очередей

Используй скрипт проверки очередей для обеих сред:

```bash
source /opt/exchanger.py/venv/bin/activate
EXCHANGER_ENV=prod python /opt/exchanger.py/camunda-worker/tools/check_queues.py
EXCHANGER_ENV=dev python /opt/exchanger.py/camunda-worker/tools/check_queues.py
```

Проверь не застряло ли сообщение в одной из очередей.

### 4. Путь задачи

Восстанови и покажи путь задачи через систему:

```
1. Camunda External Task: [статус, topic, variables]
2. Camunda Worker: [найдено в логах? когда получена?]
3. RabbitMQ (camunda.external.tasks): [роутинг]
4. Task Creator: [найдено в логах? обработана?]
5. Внешняя система: [задача создана? ID во внешней системе?]
6. Sent Queue: [отправлена на трекинг?]
7. Response Queue: [ответ отправлен в Camunda?]
```

### 5. Диагноз

На основе собранной информации:
- Определи на каком этапе задача находится или застряла
- Предложи действия для разрешения проблемы
- Если задача заблокирована — предложи использовать `camunda-worker/tools/unlock_task.py`
