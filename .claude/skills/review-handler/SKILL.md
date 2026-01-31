---
name: review-handler
description: Специализированный code review обработчика (consumer handler)
user-invocable: true
argument: "[handler-path]"
---

# /review-handler — Code Review обработчика

## Задача

Провести специализированный code review consumer handler'а для проекта Exchanger.py.

## Аргумент

- `[handler-path]` — путь к файлу handler.py (например: `task-creator/consumers/bitrix/handler.py`)

Если не указан — спроси у пользователя или найди все handler.py в `task-creator/consumers/`.

## Шаги выполнения

### 1. Контекст

Прочитай файлы для понимания паттерна:
- `task-creator/base_handler.py` — BaseMessageHandler API
- `task-creator/config.py` — регистрация обработчиков
- Указанный handler файл
- Соответствующие `config.py` и `tracker.py` в той же директории

### 2. Проверка соответствия BaseMessageHandler API

- [ ] Реализован `process_message(message_data, properties) -> bool`
- [ ] Реализован `_process_message_impl(message_data, properties) -> Optional[Dict]`
- [ ] Реализован `_get_original_queue_name() -> str`
- [ ] Реализован `get_stats() -> Dict`
- [ ] Реализован `cleanup()`
- [ ] Статистика корректно обновляется (total_messages, successful_tasks, failed_tasks)

### 3. Проверка ACK/NACK логики

- [ ] `process_message` возвращает `True` при успехе (ACK)
- [ ] `process_message` возвращает `False` при ошибке (NACK)
- [ ] Исключения перехватываются и не пробрасываются выше
- [ ] При ошибке сообщение не теряется (NACK или error queue)

### 4. Проверка retry и error handling

- [ ] Используется `_send_success_message_with_retry` для отправки в sent queue
- [ ] Корректная обработка timeout от внешнего API
- [ ] Обработка HTTP ошибок (4xx, 5xx)
- [ ] Логирование ошибок с достаточным контекстом (task_id, topic)

### 5. Проверка регистрации в config.py

- [ ] Handler зарегистрирован в `QUEUE_HANDLERS`
- [ ] Очередь добавлена в `SENT_QUEUES_MAPPING`
- [ ] Tracker зарегистрирован в `TRACKER_HANDLERS` (если есть tracker)
- [ ] Имена модулей и классов совпадают с реальными

### 6. Проверка безопасности

- [ ] Credentials не хардкожены (используется config/env)
- [ ] Нет SQL/Command injection в обработке данных
- [ ] SSL/TLS настройки корректны
- [ ] Нет утечки чувствительных данных в логи (пароли, токены)
- [ ] Request timeout установлен

### 7. Проверка качества кода

- [ ] Логирование через loguru с метками среды
- [ ] Type hints для параметров методов
- [ ] Graceful shutdown в cleanup()
- [ ] Нет утечек ресурсов (соединения закрываются)

### 8. Формат результата

Выведи результат review в формате:

```
## Code Review: {handler-path}

### Соответствие API: {OK|WARN|FAIL}
[детали]

### ACK/NACK логика: {OK|WARN|FAIL}
[детали]

### Error Handling: {OK|WARN|FAIL}
[детали]

### Регистрация: {OK|WARN|FAIL}
[детали]

### Безопасность: {OK|WARN|FAIL}
[детали]

### Рекомендации
1. ...
2. ...
```
