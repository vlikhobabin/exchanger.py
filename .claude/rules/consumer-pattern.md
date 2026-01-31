---
paths:
  - "task-creator/consumers/**/*.py"
  - "task-creator/config.py"
  - "task-creator/base_handler.py"
---

# Consumer Pattern (Handler / Tracker / Config)

## Структура consumer
Каждый consumer — директория `task-creator/consumers/{system}/` с файлами:
- `handler.py` — класс `{System}TaskHandler`
- `tracker.py` — класс `{System}TaskTracker`
- `config.py` — класс `{System}Config(BaseSettings)` с `env_prefix="{SYSTEM}_"`
- `__init__.py` — экспорт handler и config

## Handler API (обязательные методы)
```python
def process_message(self, message_data: Dict, properties: Any) -> bool
def _process_message_impl(self, message_data: Dict, properties: Any) -> Optional[Dict]
def _get_original_queue_name(self) -> str
def get_stats(self) -> Dict
def cleanup(self)
```

## Статистика (обязательные поля в self.stats)
`total_messages`, `successful_tasks`, `failed_tasks`, `sent_to_success_queue`, `failed_to_send_success`

## Регистрация в task-creator/config.py
Новый consumer ОБЯЗАН быть зарегистрирован в трёх местах:
1. `QUEUE_HANDLERS` — маппинг очереди → модуль + handler_class
2. `SENT_QUEUES_MAPPING` — маппинг входной очереди → sent-очередь
3. `TRACKER_HANDLERS` — маппинг sent-очереди → модуль + tracker_class

## Шаблон для нового consumer
Используй существующий `consumers/bitrix/` как эталонную реализацию.
