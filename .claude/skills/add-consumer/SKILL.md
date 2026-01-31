---
name: add-consumer
description: Scaffold нового consumer для Task Creator
disable-model-invocation: true
user-invocable: true
argument: "[system-name]"
---

# /add-consumer — Scaffold нового consumer

## Задача

Создать структуру нового consumer для интеграции с внешней системой по шаблону существующего Bitrix24 consumer.

## Аргумент

- `[system-name]` — имя системы (например: `openproject`, `1c`, `python`) (обязательный)

Если аргумент не указан — спроси у пользователя имя системы.

## Шаги выполнения

### 1. Изучи существующий шаблон

Прочитай файлы consumer Bitrix24 для понимания паттерна:
- `task-creator/consumers/bitrix/handler.py`
- `task-creator/consumers/bitrix/config.py`
- `task-creator/consumers/bitrix/tracker.py`
- `task-creator/consumers/bitrix/__init__.py`

Также прочитай:
- `task-creator/base_handler.py` — базовый класс BaseMessageHandler
- `task-creator/config.py` — текущие QUEUE_HANDLERS, TRACKER_HANDLERS, SENT_QUEUES_MAPPING

### 2. Создай файлы consumer

Создай директорию `task-creator/consumers/{system-name}/` и файлы:

#### `__init__.py`
```python
from .handler import {SystemName}TaskHandler
from .config import {system_name}_config
```

#### `config.py`
- Класс `{SystemName}Config(BaseSettings)` с базовыми настройками
- Переменные окружения с префиксом `{SYSTEM_NAME}_`
- Как минимум: `api_url`, `request_timeout`, `supported_topics`

#### `handler.py`
- Класс `{SystemName}TaskHandler` — наследник паттерна BitrixTaskHandler
- Методы: `process_message()`, `_process_message_impl()`, `_get_original_queue_name()`, `get_stats()`, `cleanup()`
- TODO-комментарии для реализации бизнес-логики

#### `tracker.py`
- Класс `{SystemName}TaskTracker` — по шаблону BitrixTaskTracker
- Атрибуты: `source_queue`, `target_queue`, `stats`
- TODO-комментарии для реализации трекинга

### 3. Зарегистрируй в config.py

Обнови файл `task-creator/config.py`:

- **QUEUE_HANDLERS:** Добавь запись `"{system-name}.queue"` с модулем `"consumers.{system-name}"` и классом `"{SystemName}TaskHandler"`
- **SENT_QUEUES_MAPPING:** Добавь `"{system-name}.queue": "{system-name}.sent.queue"`
- **TRACKER_HANDLERS:** Добавь запись `"{system-name}.sent.queue"` с модулем `"consumers.{system-name}"`, трекером `"{SystemName}TaskTracker"` и `target_queue: "camunda.responses.queue"`

### 4. Покажи результат

Выведи список созданных файлов и изменений в config.py. Укажи что нужно реализовать (TODO).
