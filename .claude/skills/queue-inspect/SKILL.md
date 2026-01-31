---
name: queue-inspect
description: Инспекция RabbitMQ очередей — сообщения, consumers, dead letters
disable-model-invocation: true
user-invocable: true
argument: "[prod|dev] [queue-name|all]"
---

# /queue-inspect — Инспекция RabbitMQ очередей

## Задача

Показать детальную информацию о состоянии RabbitMQ очередей для Exchanger.py.

## Аргументы

- Первый аргумент (среда): `prod` или `dev` (default: `prod`)
- Второй аргумент (очередь): имя очереди или `all` (default: `all`)

## Известные очереди

- `bitrix24.queue` — входящие задачи для Bitrix24
- `bitrix24.sent.queue` — отправленные задачи для трекинга
- `openproject.queue` — входящие задачи для OpenProject
- `1c.queue` — входящие задачи для 1C
- `python-services.queue` — входящие задачи для Python-сервисов
- `camunda.responses.queue` — ответы для Camunda
- `errors.camunda_tasks.queue` — ошибки обработки (Dead Letter Queue)
- `default.queue` — очередь по умолчанию

## Шаги выполнения

### 1. Проверка через скрипт check_queues.py

```bash
source /opt/exchanger.py/venv/bin/activate
EXCHANGER_ENV={env} python /opt/exchanger.py/camunda-worker/tools/check_queues.py
```

### 2. Детальная информация через RabbitMQ Management API

Прочитай конфигурацию RabbitMQ из `.env.{env}` и выполни запросы к Management API:

```bash
source /opt/exchanger.py/venv/bin/activate
python -c "
import requests
from dotenv import load_dotenv
import os

load_dotenv('/opt/exchanger.py/.env.{env}')
host = os.getenv('RABBITMQ_HOST')
mgmt_port = os.getenv('RABBITMQ_MANAGEMENT_PORT', '15672')
user = os.getenv('RABBITMQ_USER')
password = os.getenv('RABBITMQ_PASSWORD')
vhost = os.getenv('RABBITMQ_VIRTUAL_HOST', '/{env}')

import urllib.parse
vhost_encoded = urllib.parse.quote(vhost, safe='')
url = f'http://{host}:{mgmt_port}/api/queues/{vhost_encoded}'
resp = requests.get(url, auth=(user, password))
for q in resp.json():
    print(f\"{q['name']}: messages={q.get('messages',0)}, consumers={q.get('consumers',0)}, unacked={q.get('messages_unacknowledged',0)}\")
"
```

### 3. Формат вывода

```
## RabbitMQ Queues [{env}]

| Очередь | Messages | Consumers | Unacked | Ready | DLX |
|---------|----------|-----------|---------|-------|-----|
| bitrix24.queue | 0 | 1 | 0 | 0 | errors.camunda_tasks.queue |
| bitrix24.sent.queue | 5 | 1 | 2 | 3 | - |
| errors.camunda_tasks.queue | 12 | 0 | 0 | 12 | - |
```

### 4. Предупреждения

Выдели красным/жирным:
- Очереди без consumers (кроме error queue)
- Очереди с большим количеством unacked сообщений (>10)
- Error queue с сообщениями
- Sent queue с сообщениями, если нет tracker consumer

### 5. Для конкретной очереди

Если указана конкретная очередь, дополнительно покажи:
- Bindings (exchanges)
- Arguments (DLX, TTL)
- Message rates (publish, deliver, ack)
- Если есть сообщения — предложи прочитать через `camunda-worker/tools/queue_reader.py`
