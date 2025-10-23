# Синхронизация процессов Camunda с Bitrix24

## Обзор

Добавлена функциональность автоматической синхронизации процессов Camunda с Bitrix24 после успешного создания задач.

## Реализованные изменения

### 1. Новый метод синхронизации

**Файл:** `consumers/bitrix/handler.py`

Добавлен метод `_send_sync_request()` для отправки POST запросов в Bitrix24:

```python
def _send_sync_request(self, message_data: Dict[str, Any]) -> bool:
    """
    Отправка запроса синхронизации в Bitrix24 после успешного создания задачи
    
    Args:
        message_data: Данные сообщения с processInstanceId и processDefinitionId
        
    Returns:
        True если синхронизация успешна, False иначе
    """
```

**Функциональность:**
- Извлекает `processInstanceId` и `processDefinitionKey` напрямую из сообщения
- **ОПТИМИЗАЦИЯ:** `processDefinitionKey` передается напрямую из Camunda API
- Отправляет POST запрос на `{webhook_url}/imena.camunda.sync`
- Обрабатывает ответ и ведет статистику

### 2. Интеграция в основной поток

**Место:** После успешной отправки в очередь `bitrix24.sent.queue`

```python
# Отправка запроса синхронизации в Bitrix24
sync_success = self._send_sync_request(message_data)
if sync_success:
    logger.info(f"Синхронизация выполнена успешно для задачи {task_id}")
else:
    logger.warning(f"Не удалось выполнить синхронизацию для задачи {task_id}")
```

### 3. Статистика синхронизации

**Добавлены новые метрики:**
- `sync_requests_sent` - количество успешных запросов синхронизации
- `sync_requests_failed` - количество неудачных запросов синхронизации
- `sync_success_rate` - процент успешных синхронизаций

### 4. Обработка ошибок

**Логика обработки:**
- При отсутствии `processInstanceId` или `processDefinitionId` синхронизация пропускается
- Ошибки синхронизации логируются, но не влияют на создание задачи
- Статистика ошибок ведется отдельно от основной статистики

## Формат запроса

**URL:** `{BITRIX_WEBHOOK_URL}/imena.camunda.sync`

**Метод:** POST

**Заголовки:**
```
Content-Type: application/json
```

**Тело запроса:**
```json
{
  "processDefinitionKey": "Process_qunad56t0",
  "processInstanceId": "49b3b068-aff0-11f0-b47d-00b436387543"
}
```

**Ожидаемый ответ:**
```json
{
  "result": {
    "success": true,
    "message": "Webhook received",
    "processInstanceId": "49b3b068-aff0-11f0-b47d-00b436387543",
    "processDefinitionKey": "Process_qunad56t0",
    "timestamp": "2025-10-23 08:08:57"
  }
}
```

## Тестирование

**Создан тест:** `test_sync_functionality.py`

**Проверяет:**
- Извлечение `processDefinitionKey` из `processDefinitionId`
- Подготовку данных синхронизации
- Формирование URL синхронизации
- Наличие метода синхронизации
- Статистику синхронизации

**Запуск теста:**
```bash
cd /opt/exchanger.py/task-creator
python3 test_sync_functionality.py
```

## Документация

**Обновлен:** `README.md`

**Добавлен раздел:** "Синхронизация процессов Camunda"

**Содержит:**
- Принцип работы синхронизации
- Формат запроса и ответа
- Статистику синхронизации
- Обработку ошибок

## Конфигурация

**Использует существующие настройки:**
- `BITRIX_WEBHOOK_URL` - базовый URL webhook'а
- `BITRIX_REQUEST_TIMEOUT` - таймаут запросов

**Новые настройки не требуются** - используется существующая конфигурация Bitrix24.

## Обратная совместимость

✅ **Полная обратная совместимость**

- Существующая функциональность не изменена
- Синхронизация добавляется как дополнительный шаг
- При ошибках синхронизации создание задачи не прерывается
- Статистика синхронизации ведется отдельно

## Логирование

**Добавлены новые сообщения логов:**

```
INFO: Отправка запроса синхронизации в Bitrix24: {...}
INFO: Синхронизация успешна: processInstanceId=..., processDefinitionKey=...
WARNING: processInstanceId не найден в сообщении, пропускаем синхронизацию
ERROR: Ошибка синхронизации: ...
```

## Оптимизация

### ✅ Улучшения производительности

**Проблема:** Изначально `processDefinitionKey` извлекался из `processDefinitionId` путем парсинга строки.

**Решение:** Добавлена передача `processDefinitionKey` напрямую из Camunda API.

**Изменения:**
1. **Camunda Worker** (`camunda_worker.py`):
   - Добавлено поле `processDefinitionKey` в `task_payload`
   - Поле извлекается из `task_data.get("processDefinitionKey")`

2. **RabbitMQ Client** (`rabbitmq_client.py`):
   - Добавлено поле `process_definition_key` в сообщение
   - Передается в task-creator без изменений

3. **Bitrix24 Handler** (`handler.py`):
   - Убрана логика извлечения ключа из `processDefinitionId`
   - Используется `processDefinitionKey` напрямую из сообщения

**Преимущества:**
- ✅ Убрана необходимость парсинга строк
- ✅ Улучшена производительность
- ✅ Упрощен код
- ✅ Повышена надежность (нет риска ошибок парсинга)
- ✅ Сохранена обратная совместимость

## Статус

✅ **Готово к использованию**

- Код реализован и протестирован
- **ОПТИМИЗИРОВАН** для лучшей производительности
- Документация обновлена
- Обратная совместимость обеспечена
- Готово к развертыванию в production
