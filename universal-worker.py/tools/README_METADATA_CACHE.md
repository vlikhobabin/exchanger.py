# BPMN Metadata Cache

## 📋 Описание

Система кэширования и извлечения метаданных из BPMN XML схем для External Tasks. Решает проблему отсутствия Extension Properties, Field Injections и Input/Output Parameters в стандартном Camunda External Task API.

## 🚀 Основные возможности

- **Lazy Loading** - загрузка XML только при первом обращении
- **Эффективное кэширование** с TTL и LRU стратегией очистки
- **Автоматический парсинг** Extension Properties, Field Injections, Input/Output Parameters
- **Thread-safe** операции с блокировками
- **Подробная статистика** работы кэша
- **Управление размером** кэша с автоматической очисткой

## 📊 Результаты тестирования

### Извлеченные метаданные из TestProcess.xml

Для активности `Activity_1u7kiry` успешно извлечены:

```json
{
  "extensionProperties": {
    "TestExtensionProperties": "TestValueExtensionProperties"
  },
  "fieldInjections": {
    "TestFieldInjections": "TestValueFieldInjections"
  },
  "inputParameters": {
    "Input_2khodeq": "TestInputValue"
  },
  "outputParameters": {
    "Output_11dfutm": "TestOutputValue"
  },
  "activityInfo": {
    "id": "Activity_1u7kiry",
    "name": "Выполнить задачу в Bitrix24",
    "type": "external",
    "topic": "bitrix_create_task"
  }
}
```

### Производительность

- **Парсинг XML**: ~0.0013s (первый раз)
- **Обращение к кэшу**: ~0.0002s
- **Ускорение**: 6x

## 🔧 Интеграция в Worker

Кэш автоматически интегрирован в `camunda_worker.py`:

```python
# В методе _process_task теперь добавляются метаданные
task_payload = {
    "id": task_id,
    "topic": topic,
    "variables": task.get_variables(),
    # ... остальные поля ...
    "metadata": metadata  # ← Добавлены метаданные BPMN
}
```

## 📈 Мониторинг

Статистика кэша доступна через `worker.get_status()`:

```json
{
  "metadata_cache": {
    "cache_hits": 10,
    "cache_misses": 3,
    "xml_requests": 3,
    "parse_operations": 3,
    "cache_evictions": 0,
    "cache_size": 3,
    "max_cache_size": 150,
    "cache_size_mb": 0.05,
    "hit_rate_percent": 76.92,
    "total_requests": 13
  }
}
```

## ⚙️ Конфигурация кэша

```python
cache = BPMNMetadataCache(
    base_url="https://camunda.eg-holding.ru/engine-rest",
    auth_username="username",
    auth_password="password",
    max_cache_size=150,  # Для ~100 процессов с запасом
    ttl_hours=24         # Время жизни записи в кэше
)
```

## 📝 Структура данных в RabbitMQ

Теперь в RabbitMQ отправляется расширенное сообщение:

```json
{
  "id": "task-id",
  "topic": "bitrix_create_task",
  "variables": { ... },
  "processInstanceId": "...",
  "processDefinitionId": "TestProcess:1:abc123",
  "activityId": "Activity_1u7kiry",
  "metadata": {
    "extensionProperties": {
      "TestExtensionProperties": "TestValueExtensionProperties"
    },
    "fieldInjections": {
      "TestFieldInjections": "TestValueFieldInjections"
    },
    "inputParameters": {
      "Input_2khodeq": "TestInputValue"
    },
    "outputParameters": {
      "Output_11dfutm": "TestOutputValue"
    },
    "activityInfo": {
      "id": "Activity_1u7kiry",
      "name": "Выполнить задачу в Bitrix24",
      "topic": "bitrix_create_task"
    }
  }
}
```

## 🔍 Тестирование

Запуск тестов:

```bash
python test_metadata_cache.py
```

Тесты проверяют:
- ✅ Корректность парсинга BPMN XML
- ✅ Работу кэша и производительность
- ✅ Управление размером кэша (LRU eviction)
- ✅ Извлечение всех типов метаданных

## 🏗️ Архитектура

```
External Task → Worker → BPMN Cache → XML Parser → Metadata
                 ↓
             RabbitMQ Message (с метаданными)
```

**Lazy Loading Strategy:**
1. Получение External Task
2. Проверка кэша по `processDefinitionId`
3. Если нет в кэше → загрузка XML из Camunda REST API
4. Парсинг XML и извлечение метаданных всех активностей
5. Сохранение в кэш
6. Возврат метаданных для конкретной активности

## 💡 Преимущества решения

1. **Нет изменений в Camunda** - работает через стандартный REST API
2. **Производительность** - кэширование исключает повторные запросы
3. **Масштабируемость** - поддержка до 100+ процессов
4. **Надежность** - обработка ошибок и fallback'ы
5. **Мониторинг** - подробная статистика работы

## 🎯 Результат

Теперь в RabbitMQ приходят **полные** метаданные BPMN процессов, включая:
- Extension Properties (`TestExtensionProperties`)
- Field Injections (`TestFieldInjections`) 
- Input Parameters (`Input_2khodeq`)
- Output Parameters (`Output_11dfutm`)

Это решает исходную проблему отсутствия метаданных в External Task API! 