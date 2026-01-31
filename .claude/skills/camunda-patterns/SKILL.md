---
name: camunda-patterns
description: Фоновые знания о паттернах и архитектуре Exchanger.py
user-invocable: false
---

# Camunda Patterns — Фоновые знания

Этот скилл содержит паттерны и архитектурные знания проекта Exchanger.py для использования Claude при работе с кодом.

## Архитектура системы

### Поток данных
```
Camunda BPM → Camunda Worker → RabbitMQ → Task Creator → External System
                                                              ↓
Camunda BPM ← Response Handler ← RabbitMQ ← Task Tracker ← Sent Queue
```

### Multi-Tenancy
- `TenantAwareExternalTaskClient` в `camunda-worker/tenant_external_task_client.py` расширяет стандартный клиент
- Production tenant: `imenaProd`, Development tenant: `imenaDev`
- Tenant ID фильтрует задачи при fetch и используется при complete/failure

### SSL Patch
- `camunda-worker/ssl_patch.py` выполняет monkey patching библиотеки camunda-external-task-client-python3
- Добавляет `verify=False` ко всем requests вызовам
- Необходим из-за отсутствия поддержки SSL в библиотеке

### Stateless Architecture
- Задачи блокируются в Camunda на 1 год (`CAMUNDA_LOCK_DURATION=31536000000`)
- Нет локального состояния — всё через Camunda lock + RabbitMQ
- Ответы обрабатываются асинхронно через Response Handler

## Структура сообщений RabbitMQ

### Payload задачи (camunda.external.tasks → {system}.queue)
```json
{
  "task_id": "string",
  "process_instance_id": "string",
  "process_definition_id": "string",
  "process_definition_key": "string",
  "tenant_id": "string",
  "topic_name": "string",
  "worker_id": "string",
  "variables": {
    "var_name": {"value": "...", "type": "String|Integer|Boolean|Json"}
  },
  "bpmn_metadata": {
    "extension_properties": {},
    "field_injections": {},
    "io_parameters": {"input": {}, "output": {}}
  }
}
```

### Payload ответа ({system}.sent.queue → camunda.responses.queue)
```json
{
  "task_id": "string",
  "process_instance_id": "string",
  "worker_id": "string",
  "status": "complete|failure",
  "variables": {},
  "error_message": "string (optional)"
}
```

## Паттерн Handler / Tracker / Config

### BaseMessageHandler API
Каждый consumer должен реализовать:

```python
class {System}TaskHandler:
    def __init__(self):
        # Инициализация клиентов и сервисов
        self.publisher = RabbitMQPublisher()
        self.stats = {"total_messages": 0, "successful_tasks": 0, "failed_tasks": 0, ...}

    def process_message(self, message_data: Dict, properties: Any) -> bool:
        # Публичный метод — вызывается MessageProcessor
        # Обновляет статистику, вызывает _process_message_impl
        # Возвращает True (ACK) или False (NACK)

    def _process_message_impl(self, message_data: Dict, properties: Any) -> Optional[Dict]:
        # Абстрактный — основная бизнес-логика
        # Возвращает dict с результатом или None при ошибке

    def _get_original_queue_name(self) -> str:
        # Возвращает имя исходной очереди (например "bitrix24.queue")

    def get_stats(self) -> Dict:
        # Возвращает статистику обработки

    def cleanup(self):
        # Освобождение ресурсов (закрытие соединений)
```

### Tracker Pattern
```python
class {System}TaskTracker:
    source_queue = "{system}.sent.queue"    # Откуда читать
    target_queue = "camunda.responses.queue" # Куда отправлять ответ

    def check_task_status(self, task_data: Dict) -> Optional[str]:
        # Проверяет статус во внешней системе
        # Возвращает "complete", "failure", или None (ещё в работе)
```

### Config Pattern
```python
class {System}Config(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="{SYSTEM}_")
    api_url: str
    request_timeout: int = 30
    # ...специфичные настройки
```

## Конфигурация маршрутизации (task-creator/config.py)

### QUEUE_HANDLERS
Маппинг очереди → модуль + класс обработчика:
```python
QUEUE_HANDLERS = {
    "bitrix24.queue": {"module": "consumers.bitrix", "handler_class": "BitrixTaskHandler"},
    "openproject.queue": {"module": "consumers.openproject", "handler_class": "OpenProjectTaskHandler"},
    # ...
}
```

### SENT_QUEUES_MAPPING
Маппинг входной очереди → sent-очередь для трекинга:
```python
SENT_QUEUES_MAPPING = {
    "bitrix24.queue": "bitrix24.sent.queue",
    # ...
}
```

### TRACKER_HANDLERS
Маппинг sent-очереди → модуль + класс трекера:
```python
TRACKER_HANDLERS = {
    "bitrix24.sent.queue": {
        "module": "consumers.bitrix",
        "tracker_class": "BitrixTaskTracker",
        "target_queue": "camunda.responses.queue"
    },
    # ...
}
```

## BPMN Metadata Cache
- `camunda-worker/bpmn_metadata_cache.py` — LRU кэш с TTL
- Кэширует: extensionProperties, field injections, IO parameters
- Ключ: `process_definition_id` + `activity_id`
- Источник: Camunda REST API `/process-definition/{id}/xml`

## RabbitMQ Exchange/Queue Topology
- Exchange `camunda.external.tasks` (topic) — роутинг по topic_name
- Каждая система имеет свою пару очередей: `{system}.queue` + `{system}.sent.queue`
- Dead Letter Queue: `errors.camunda_tasks.queue`
- Ответы: `camunda.responses.queue` (direct)

## Разделение сред
- Среды изолированы через RabbitMQ Virtual Hosts (`/prod`, `/dev`)
- Конфигурация через `EXCHANGER_ENV` переменную
- Файлы конфигурации: `.env.prod`, `.env.dev`
- Логи: `logs/prod/`, `logs/dev/`
- Systemd сервисы: `*-prod`, `*-dev`
