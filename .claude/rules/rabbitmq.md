---
paths:
  - "camunda-worker/**/*.py"
  - "task-creator/**/*.py"
---

# RabbitMQ Conventions

## Naming
- Очереди: `{system}.queue` (входящие), `{system}.sent.queue` (на трекинг)
- Exchange: `camunda.external.tasks` (topic), роутинг по `topic_name`
- Ответы: `camunda.responses.queue` (direct)
- Ошибки: `errors.camunda_tasks.queue` (Dead Letter Queue)

## ACK/NACK
- `process_message()` возвращает `True` → ACK (сообщение обработано)
- `process_message()` возвращает `False` → NACK (сообщение вернётся в очередь)
- Исключения НИКОГДА не должны пробрасываться выше `process_message()` — ловить и возвращать `False`

## Среды
- Production vhost: `/prod`
- Development vhost: `/dev`
- Среды полностью изолированы через Virtual Hosts

## Подключения
- Используй `pika` для RabbitMQ
- Всегда закрывай соединение в `cleanup()`
- Retry-логика: `_send_success_message_with_retry()` — 5 попыток, exponential backoff
