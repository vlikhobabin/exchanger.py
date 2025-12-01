# Camunda Worker

Camunda Worker для обработки External Tasks от Camunda через RabbitMQ с Stateless архитектурой.

## Описание

Camunda Worker - это независимый модуль для интеграции Camunda BPM с внешними системами через RabbitMQ. Реализует Stateless архитектуру с длительными блокировками задач.

### Основные возможности

- Мониторинг всех External Tasks от процессов Camunda
- **Camunda Multi-Tenancy** - изоляция задач по tenant ID (prod/dev)
- **Многопоточная обработка** - отдельный поток для каждого топика задач (параллельная обработка)
- **Извлечение BPMN метаданных** - Extension Properties, Field Injections, Input/Output Parameters, Process Properties
- **Автоматическое получение переменных процесса** через Camunda REST API
- **Автоматическое извлечение processDefinitionKey** из processDefinitionId при отсутствии
- Автоматическое определение целевой системы по топику задачи
- Отправка задач в соответствующие очереди RabbitMQ с полными метаданными
- Асинхронное завершение задач через интегрированный Response Handler
- Блокировка задач на длительный период (по умолчанию 1 год для Stateless режима)
- Интеллектуальное кэширование BPMN XML с lazy loading и LRU eviction
- Устойчивость к перезагрузкам и сбоям
- Автоматическое переподключение к RabbitMQ при разрыве соединения
- Детальное логирование и мониторинг с ротацией логов
- Обработка ошибок с повторными попытками и graceful degradation
- **Надёжная обработка ошибок** - ошибочные сообщения перемещаются в очередь ошибок вместо удаления

### Поддерживаемые системы

- **Bitrix24** - CRM и управление проектами
- **OpenProject** - управление проектами  
- **1C** - учетные системы
- **Python Services** - специализированные сервисы

## SSL Configuration

### Проблема SSL сертификатов

Библиотека `camunda-external-task-client-python3==4.5.0` не поддерживает настройку SSL параметров, что приводит к ошибкам:
```
SSLError(1, '[SSL: TLSV1_ALERT_DECODE_ERROR] tlsv1 alert decode error (_ssl.c:1000)')
```

### Решение

Проект использует **SSL Patch** - monkey patching библиотеки requests для автоматического добавления `verify=False` ко всем HTTP запросам к Camunda.

**Применение патча:**
- Автоматически применяется при импорте модуля `ssl_patch`
- Патч работает глобально для всех `requests` вызовов
- Отключает SSL warnings через `urllib3.disable_warnings()`

**⚠️ Предупреждение о безопасности:**
- `verify=False` отключает проверку SSL сертификатов
- Используйте только в доверенной сетевой среде
- Для production рекомендуется настроить валидные SSL сертификаты

## Архитектура

Camunda Worker использует **интегрированную архитектуру** где обработка External Tasks и Response Handling выполняются в едином процессе для максимальной эффективности.

### Camunda Multi-Tenancy

Worker поддерживает изоляцию задач по tenant ID для разделения production и development сред:

```
┌─────────────────────────────────────────────────────────────┐
│                    Camunda BPM Server                       │
│  ┌─────────────────────┐    ┌─────────────────────┐        │
│  │  Tenant: imenaProd  │    │  Tenant: imenaDev   │        │
│  │  (Production tasks) │    │  (Development tasks)│        │
│  └──────────┬──────────┘    └──────────┬──────────┘        │
└─────────────┼──────────────────────────┼───────────────────┘
              │                          │
              ▼                          ▼
┌─────────────────────────┐  ┌─────────────────────────┐
│  Camunda Worker [PROD]  │  │  Camunda Worker [DEV]   │
│  CAMUNDA_TENANT_ID=     │  │  CAMUNDA_TENANT_ID=     │
│       imenaProd         │  │       imenaDev          │
│  fetchAndLock:          │  │  fetchAndLock:          │
│  tenantIdIn:[imenaProd] │  │  tenantIdIn:[imenaDev]  │
└─────────────────────────┘  └─────────────────────────┘
```

**Реализация:**
- `TenantAwareExternalTaskClient` (`tenant_external_task_client.py`) — расширяет стандартный клиент
- Добавляет `tenantIdIn` в каждый topic при `fetchAndLock`
- Конфигурируется через `CAMUNDA_TENANT_ID` в `.env` файле

### Компоненты системы

1. **Camunda Worker** (`camunda_worker.py`) - получение задач из Camunda, отправка в RabbitMQ и обработка ответов
2. **Tenant-Aware Client** (`tenant_external_task_client.py`) - кастомный клиент с поддержкой multi-tenancy
3. **BPMN Metadata Cache** (`bpmn_metadata_cache.py`) - извлечение и кэширование метаданных из BPMN XML
4. **Интегрированный Response Handler** (встроен в `camunda_worker.py`) - обработка ответов из RabbitMQ и завершение задач в Camunda
5. **RabbitMQ Client** (`rabbitmq_client.py`) - взаимодействие с очередями сообщений
6. **Response Handler** (`response_handler.py`) - отдельный модуль для обработки ответов (опционально, для standalone режима)

### Workflow обработки

1. Worker получает External Task от Camunda (многопоточная обработка - отдельный поток для каждого топика)
2. Блокирует задачу на указанный период (по умолчанию 1 год для Stateless режима)
3. **Извлекает BPMN метаданные** из кэша или парсит XML (lazy loading)
4. **Получает переменные процесса** через Camunda REST API (`/process-instance/{id}/variables`)
5. Определяет целевую систему по топику
6. Отправляет задачу в соответствующую очередь RabbitMQ **с полными метаданными и переменными процесса**
7. Внешняя система обрабатывает задачу (может занимать длительное время)
8. Система отправляет результат в очередь `camunda.responses.queue`
9. **Интегрированный Response Handler** (в потоке мониторинга, каждые `HEARTBEAT_INTERVAL` секунд):
   - Проверяет очередь ответов
   - Обрабатывает сообщения (до 10 за раз)
   - Извлекает данные из ответа (включая `ufResultAnswer_text` для задач с `ufResultExpected=1`)
   - Создает переменные процесса (включая переменную с именем `activity_id`)
   - Завершает задачу в Camunda через REST API

### BPMN Метаданные

Worker автоматически извлекает из BPMN XML и передает в RabbitMQ:

- **Extension Properties** - кастомные свойства элементов (включая `assigneeId`)
- **Field Injections** - инъекции полей в Java Delegates
- **Input Parameters** - входные параметры элементов
- **Output Parameters** - выходные параметры элементов
- **Process Properties** - свойства уровня процесса (из extensionElements процесса)

**Ключевая особенность - прямое использование assigneeId:**
- Значение `assigneeId` из BPMN extensionProperties напрямую используется как `responsible_id` в целевых системах
- Отсутствует необходимость в маппинге ролей через внешние файлы
- Упрощенная конфигурация и повышенная надежность

**Process Properties:**
- Свойства уровня процесса извлекаются из `<bpmn:process><bpmn:extensionElements><camunda:properties>`
- Доступны во всех задачах процесса через `metadata.processProperties`
- Используются для глобальных настроек процесса

**Преимущества кэширования:**
- **Lazy Loading** - XML загружается только при первой задаче процесса
- **TTL**: 24 часа (конфигурируется)
- **LRU Eviction** - автоматическая очистка старых записей
- **Thread-safe** операции
- **Производительность**: 6x ускорение после первой загрузки

### Организация очередей RabbitMQ

**Исходящие задачи (Exchange: camunda.external.tasks)**
- `bitrix24.queue` - задачи для Bitrix24 (routing key: `bitrix24.*`)
- `openproject.queue` - задачи для OpenProject (routing key: `openproject.*`)
- `1c.queue` - задачи для 1C (routing key: `1c.*`)
- `python-services.queue` - задачи для Python сервисов (routing keys: `python.*`, `email.*`, `telegram.*`, `yandex.*`, `user.*`, `file.*`, `data.*`)
- `default.queue` - неопознанные задачи через Alternate Exchange
- `errors.camunda_tasks.queue` - ошибки обработки задач и ответов

**Alternate Exchange (camunda.unrouted.tasks)**
- Автоматически перенаправляет неопознанные сообщения в `default.queue`
- Используется для обработки задач с неизвестными топиками

**Ответные сообщения (Exchange: camunda.task.responses)**
- `camunda.responses.queue` - ответы от всех систем (routing key: `camunda.responses.queue`)

### Обработка ошибок при завершении задач

При ошибке завершения задачи в Camunda (например, ошибка в BPMN диаграмме, недоступность Camunda), 
сообщение **не удаляется**, а перемещается в очередь `errors.camunda_tasks.queue` для последующего анализа.

**Сценарии обработки:**

| Сценарий | Действие |
|----------|----------|
| Успешное завершение в Camunda | ACK сообщения |
| Ошибка Camunda (500, timeout) | → `errors.camunda_tasks.queue` → ACK |
| Ошибка публикации в errors.queue | NACK + requeue (повторная попытка) |
| Критическая ошибка обработки | → `errors.camunda_tasks.queue` → ACK |

**Формат сообщения в очереди ошибок:**

```json
{
  "error_info": {
    "type": "camunda_internal_error",
    "message": "Internal server error from Camunda",
    "camunda_error_type": "ProcessEngineException",
    "camunda_error_message": "Unknown property used in expression: ${Activity_xxx != \"ok\"}",
    "http_status_code": 500,
    "timestamp": "2025-12-01T16:37:07",
    "source_queue": "camunda.responses.queue"
  },
  "original_message": {
    "original_message": { "task_id": "...", "activity_id": "..." },
    "response_data": { "result": { "task": {...} } },
    "processing_status": "completed_by_tracker"
  },
  "task_id": "b512fa46-cece-11f0-9207-00b436387543",
  "activity_id": "Activity_0xmi3rr",
  "error_timestamp": 1764607027000
}
```

**Типы ошибок:**
- `camunda_internal_error` - ошибка 500 от Camunda (например, ошибка в BPMN expression)
- `timeout_error` - таймаут запроса к Camunda
- `connection_error` - ошибка соединения с Camunda
- `request_error` - ошибка HTTP запроса
- `unexpected_http_status` - неожиданный код ответа
- `processing_exception` - исключение при обработке сообщения
- `json_parse_error` - ошибка парсинга JSON

## Установка

### Требования

- Python 3.8+
- RabbitMQ
- Camunda BPM Platform
- Доступ к REST API Camunda

### Быстрая установка

```bash
cd camunda-worker
pip install camunda-external-task-client-python3 pika pydantic pydantic-settings python-dotenv requests loguru lxml
```

### Конфигурация

Проект использует раздельные файлы конфигурации: `.env.prod` и `.env.dev`

```bash
# Camunda настройки
CAMUNDA_BASE_URL=https://your-camunda-server.com/engine-rest
CAMUNDA_WORKER_ID=universal-worker
CAMUNDA_MAX_TASKS=10
CAMUNDA_LOCK_DURATION=31536000000
CAMUNDA_AUTH_USERNAME=your_username
CAMUNDA_AUTH_PASSWORD=your_password

# Camunda Multi-Tenancy
CAMUNDA_TENANT_ID=imenaProd          # для production
# CAMUNDA_TENANT_ID=imenaDev         # для development

# RabbitMQ настройки  
RABBITMQ_HOST=your-rabbitmq-host.com
RABBITMQ_USERNAME=your_username
RABBITMQ_PASSWORD=your_password

# BPMN Metadata Cache
BPMN_CACHE_TTL_HOURS=24
BPMN_CACHE_MAX_SIZE=150

# Логирование
LOG_LEVEL=INFO
```

## Запуск

### Основные команды

```bash
# Запуск интегрированного Worker (рекомендуется)
python main.py

# Запуск только Worker (без обработки ответов)
python camunda_worker.py

# Управление процессами Camunda
python tools/process_manager.py list
python tools/process_manager.py start ProcessKey --variables '{"key": "value"}'

# Мониторинг очередей RabbitMQ
python tools/check_queues.py

# Диагностика системы
python tools/worker_diagnostics.py

# Разблокировка зависших задач
python tools/unlock_task.py --task-id <task-id>
```

### Как сервис

В проекте используются systemd сервисы: `exchanger-worker.service` и `exchanger-creator.service`.

Для управления сервисом:
```bash
sudo systemctl status exchanger-worker
sudo systemctl restart exchanger-worker
sudo journalctl -u exchanger-worker -f
```

## Конфигурация

### Основные параметры

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `CAMUNDA_BASE_URL` | URL REST API Camunda | `https://camunda.example.com/engine-rest` |
| `CAMUNDA_WORKER_ID` | Идентификатор Worker | `universal-worker` |
| `CAMUNDA_MAX_TASKS` | Максимум задач за запрос | `10` |
| `CAMUNDA_LOCK_DURATION` | Время блокировки (мс) | `31536000000` (1 год) |
| `CAMUNDA_TENANT_ID` | Tenant ID для multi-tenancy | `None` (все tenant'ы) |
| `RABBITMQ_HOST` | Хост RabbitMQ | `localhost` |
| `RABBITMQ_PORT` | Порт RabbitMQ | `5672` |
| `BPMN_CACHE_TTL_HOURS` | TTL кэша метаданных (часы) | `24` |
| `BPMN_CACHE_MAX_SIZE` | Максимум процессов в кэше | `150` |
| `HEARTBEAT_INTERVAL` | Интервал проверки ответов (сек) | `60` |
| `RESPONSE_HANDLER_ENABLED` | Включить обработку ответов | `true` |
| `RESPONSE_PROCESSING_INTERVAL` | Интервал обработки ответов (сек) | `5` |
| `DEBUG_SAVE_RESPONSE_MESSAGES` | Сохранять отладочные сообщения | `false` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |

### Маппинг топиков

Worker автоматически определяет целевую систему по названию топика:

```python
# Примеры маппинга
"bitrix_create_task" → bitrix24.queue
"op_create_project" → openproject.queue  
"1c_sync_data" → 1c.queue
"send_email" → python-services.queue
```

Полный список маппингов определен в `config.py` в классе `RoutingConfig`.

## Мониторинг

### Логи

Система ведет несколько типов логов:

- **Основные логи**: `logs/camunda_worker.log`
- **Логи ошибок**: `logs/camunda_worker_errors.log`
- **Системные логи**: через `journalctl -u exchanger-worker`

### Статистика

Worker выводит статистику каждые 30 секунд:

```
Monitor - Uptime: 3600s | Обработано: 150 | Успешно: 147 | Ошибки: 3 | Ответов: 25 | Завершено: 24
BPMN Cache - Hits: 142 | Misses: 8 | Hit Rate: 94.7% | Size: 12/150 (0.18 MB)
```

### Мониторинг BPMN кэша

Детальная статистика доступна через API:

```json
{
  "metadata_cache": {
    "cache_hits": 142,
    "cache_misses": 8,
    "hit_rate_percent": 94.67,
    "cache_size": 12,
    "cache_size_mb": 0.18,
    "avg_parse_time_ms": 1.3,
    "avg_cache_access_time_ms": 0.2
  }
}
```

### Проверка состояния

Используйте сервисные скрипты из каталога `tools/`:

```bash
# Статус очередей RabbitMQ
python tools/check_queues.py

# Информация о процессах Camunda
python tools/camunda_processes.py --stats

# Диагностика Worker
python tools/worker_diagnostics.py

# Тестирование обработки ответов
python tools/test_response_processing.py
```

## API для внешних систем

### Формат ответного сообщения

### Переменные возвращаемые в Camunda

После завершения задачи Worker автоматически передает в процесс Camunda следующие переменные:

**Переменная для условных выражений (conditionExpression):**
- `{activity_id}` - переменная с именем равным `activity_id` задачи
  - Значение `"ok"` - если задача не требует ответа (`ufResultExpected != "1"`) или ответ "ДА"
  - Значение `"no"` - если ответ "НЕТ" или отсутствует
  - Используется в BPMN: `${Activity_177u7c0 != "ok"}` для условных переходов

**Данные задачи Bitrix24 (если применимо):**
- `bitrix_task_id` - ID задачи в Bitrix24
- `bitrix_task_title` - заголовок задачи
- `bitrix_task_description` - описание задачи
- `bitrix_task_status` - статус задачи
- `bitrix_task_priority` - приоритет задачи
- `bitrix_task_created_date` - дата создания
- `bitrix_task_changed_date` - дата изменения
- `bitrix_task_deadline` - срок выполнения
- `bitrix_task_created_by` - ID создателя
- `bitrix_task_responsible_id` - ID ответственного
- `bitrix_task_group_id` - ID группы
- `bitrix_task_parent_id` - ID родительской задачи

**Исходные переменные:** Все переменные из исходной задачи возвращаются обратно в процесс.

**Логика обработки ответов:**
1. Если `ufResultExpected == "1"` (задача требует ответа):
   - Извлекается `ufResultAnswer_text` из ответа
   - Конвертируется: "ДА" → "ok", "НЕТ" → "no"
   - Создается переменная `{activity_id}` = конвертированное значение
2. Если `ufResultExpected != "1"` (задача не требует ответа):
   - Создается переменная `{activity_id}` = "ok" по умолчанию

## Формат сообщений

### Исходящие задачи

Внешние системы получают задачи с полными метаданными в очередях RabbitMQ:

```json
{
  "id": "task-uuid",
  "topic": "bitrix_create_task",
  "variables": {
    "projectId": {"value": "123", "type": "String"}
  },
  "metadata": {
    "extensionProperties": {
      "assigneeId": "3",
      "customProperty": "customValue"
    },
    "fieldInjections": {
      "serviceUrl": "https://api.example.com"
    },
    "inputParameters": {
      "inputData": "processedValue"
    },
    "outputParameters": {
      "resultMapping": "responseField"
    },
    "processProperties": {
      "globalProperty": "globalValue"
    },
    "processVariables": {
      "processVar1": {"value": "value1", "type": "String"}
    }
  },
  "process_variables": {
    "processVar1": {"value": "value1", "type": "String"}
  },
  "processDefinitionKey": "ProcessKey",
  "activityId": "Activity_177u7c0"
}
```

**Ключевое поле `assigneeId`:**
- Значение `assigneeId` из BPMN напрямую используется как `responsible_id` в Bitrix24
- Пример: `assigneeId: "3"` → `responsible_id: 3` в создаваемой задаче

**Process Variables:**
- Переменные процесса уровня процесса извлекаются через Camunda REST API (`/process-instance/{id}/variables`)
- Доступны в сообщении через поле `process_variables`
- Также добавляются в `metadata.processVariables` для совместимости
- Используются для передачи глобальных данных процесса во внешние системы
- Извлекаются для каждой задачи автоматически

### Формат ответа от внешних систем

Внешние системы должны отправлять ответы в очередь `camunda.responses.queue`:

```json
{
  "original_message": {
    "task_id": "task-uuid",
    "activity_id": "Activity_177u7c0",
    "topic": "bitrix_create_task",
    "variables": {
      "projectId": {"value": "123", "type": "String"}
    }
  },
  "response_data": {
    "result": {
      "task": {
        "ID": "123",
        "TITLE": "Task Title",
        "DESCRIPTION": "Task Description",
        "STATUS": "3",
        "ufResultExpected": "1",
        "ufResultAnswer_text": "ДА"
      },
      "success": true
    }
  },
  "processing_status": "completed"
}
```

**Обязательные поля:**
- `original_message.task_id` - ID задачи в Camunda
- `original_message.activity_id` - ID активности (используется для создания переменной процесса)
- `processing_status` - статус обработки ("completed" или "completed_by_tracker")

**Поля для задач с ответами:**
- `response_data.result.task.ufResultExpected` - "1" если требуется ответ
- `response_data.result.task.ufResultAnswer_text` - "ДА" или "НЕТ"

### Типы ответов

- `complete` - успешное завершение задачи
- `failure` - ошибка с возможностью повтора
- `bpmn_error` - BPMN ошибка для обработки в процессе

## Разработка

### Структура проекта

```
camunda-worker/
├── main.py                        # Точка входа (интегрированный режим)
├── camunda_worker.py              # Основной Worker с интегрированным Response Handler
├── tenant_external_task_client.py # Кастомный клиент с поддержкой multi-tenancy
├── bpmn_metadata_cache.py         # Кэш BPMN метаданных с lazy loading
├── response_handler.py            # Отдельный обработчик ответов (опционально)
├── rabbitmq_client.py             # RabbitMQ клиент с Alternate Exchange
├── config.py                      # Конфигурация (Pydantic settings)
├── ssl_patch.py                   # SSL патч для camunda-external-task-client
├── tools/                         # Сервисные скрипты
│   ├── process_manager.py  # Управление процессами Camunda
│   ├── start_process.py   # Запуск процессов
│   ├── camunda_processes.py # Мониторинг процессов
│   ├── check_queues.py    # Проверка очередей RabbitMQ
│   ├── unlock_task.py     # Разблокировка задач
│   ├── worker_diagnostics.py # Диагностика системы
│   ├── status_check.py    # Проверка статуса
│   ├── queue_reader.py     # Чтение сообщений из очередей
│   ├── task_recovery.py   # Восстановление задач
│   ├── README.md          # Документация инструментов
│   └── YAML_CONFIG_README.md # Документация YAML конфигурации
└── logs/                  # Файлы логов
    ├── camunda-worker.log
    ├── camunda-worker-errors.log
    └── debug/             # Отладочные файлы (если включено)
```

Схема обработки ответа от внешних систем

```mermaid
graph TD
    A[Сообщение из camunda.responses.queue] --> B[Получение activity_id]
    B --> C{activity_id найден?}
    C -->|Нет| D[WARNING: activity_id отсутствует<br/>Устанавливаем activity_id = 'ok']
    C -->|Да| E[Извлечение task_data из response_data]
    E --> F[Проверка ufResultExpected]
    F --> G{ufResultExpected === '1'?}
    G -->|Да| H[Задача требует ответа от пользователя]
    G -->|Нет/Отсутствует| I[INFO: Задача не требует ответа<br/>Устанавливаем activity_id = 'ok']
    H --> J[Поиск ufResultAnswer_text]
    J --> K{ufResultAnswer_text найден?}
    K -->|Да| L[Конвертация ДА/НЕТ → ok/no]
    K -->|Нет| M[WARNING: ufResultAnswer_text отсутствует<br/>Устанавливаем activity_id = 'ok']
    L --> N[Создание переменной процесса:<br/>variables[activity_id] = значение]
    N --> O[Извлечение данных задачи Bitrix24]
    I --> O
    M --> O
    D --> O
    O --> P[Завершение External Task в Camunda<br/>через REST API /complete]
    
    style G fill:#fff3e0
    style I fill:#e8f5e8
    style H fill:#e3f2fd
    style M fill:#fff3e0
    style D fill:#fff3e0
    style P fill:#f3e5f5
    style N fill:#e1f5fe
```    

### Зависимости

- `camunda-external-task-client-python3` - клиент для Camunda External Tasks
- `pika` - клиент для RabbitMQ
- `pydantic` - валидация данных
- `pydantic-settings` - управление настройками из переменных окружения
- `python-dotenv` - загрузка переменных из .env файла
- `requests` - HTTP запросы к Camunda REST API
- `loguru` - расширенное логирование с ротацией
- `lxml` - парсинг BPMN XML

**Установка:**
```bash
pip install camunda-external-task-client-python3 pika pydantic pydantic-settings python-dotenv requests loguru lxml
```

## Troubleshooting

### Частые проблемы

1. **Задачи не обрабатываются**: Проверьте подключение к Camunda и маппинг топиков
2. **Ошибки RabbitMQ**: Убедитесь в корректности credentials и доступности сервера
3. **Задачи зависают**: Проверьте время блокировки и работу Response Handler
4. **Метаданные не извлекаются**: Проверьте доступ к Camunda REST API для загрузки BPMN XML
5. **Проблемы с кэшем**: Увеличьте `BPMN_CACHE_MAX_SIZE` или проверьте логи парсинга XML
6. **Ошибка "condition expression returns non-Boolean"**: BPMN процесс ожидает Boolean в условном выражении. Для диагностики:
   - Проверьте логи Worker - включено подробное логирование запросов к Camunda
   - Убедитесь что условные выражения в BPMN используют правильные переменные
   - Проверьте что переменная `{activity_id}` создается корректно (значение "ok" или "no")
   - Используйте `python tools/queue_reader.py camunda.responses.queue` для просмотра ответов
7. **Задачи не завершаются**: Проверьте работу Response Handler:
   - Убедитесь что `RESPONSE_HANDLER_ENABLED=true` (по умолчанию включено)
   - Проверьте очередь `camunda.responses.queue` на наличие сообщений
   - Проверьте логи на ошибки завершения задач (HTTP 500, 404)
8. **Метаданные не передаются**: Проверьте доступ к Camunda REST API:
   - Убедитесь что `/process-definition/{id}/xml` доступен
   - Проверьте логи кэша BPMN на ошибки парсинга
   - Используйте `python tools/worker_diagnostics.py` для диагностики
9. **Ошибка "Cannot resolve identifier" в Camunda**: Ошибка в BPMN диаграмме - ссылка на несуществующую переменную в conditionExpression:
   - Проверьте очередь ошибок `errors.camunda_tasks.queue` - там сохранено полное сообщение с деталями
   - Найдите в ошибке имя переменной (например, `Activity_xxx`)
   - Исправьте conditionExpression в BPMN диаграмме
   - После исправления можно переобработать сообщения из очереди ошибок

### Работа с очередью ошибок

При ошибках завершения задач в Camunda, сообщения сохраняются в `errors.camunda_tasks.queue`:

```bash
# Просмотр сообщений в очереди ошибок
python tools/queue_reader.py errors.camunda_tasks.queue

# Пример содержимого ошибки
{
  "error_info": {
    "type": "camunda_internal_error",
    "camunda_error_type": "ProcessEngineException",
    "camunda_error_message": "Unknown property used in expression: ${Activity_xxx != \"ok\"}"
  },
  "task_id": "b512fa46-...",
  "activity_id": "Activity_0xmi3rr"
}
```

**Типичные причины ошибок:**
- Ошибка в conditionExpression BPMN - ссылка на несуществующую переменную
- Таймаут соединения с Camunda
- Задача уже завершена другим процессом

### Диагностика

```bash
# Проверка подключений
python tools/worker_diagnostics.py

# Разблокировка зависших задач
python tools/unlock_task.py --task-id <task-id>

# Просмотр активных процессов
python tools/camunda_processes.py --instances

# Просмотр сообщений в очереди ответов
python tools/queue_reader.py camunda.responses.queue

# Просмотр ошибок обработки ответов
python tools/queue_reader.py errors.camunda_tasks.queue

# Восстановление задач
python tools/task_recovery.py

# Проверка статуса системы
python tools/status_check.py
```

## Лицензия

MIT License

---

## История изменений

### v2.4.0 - Надёжная обработка ошибок ответов
- ✅ **Очередь ошибок**: При неудачном завершении задачи в Camunda сообщение перемещается в `errors.camunda_tasks.queue`
- ✅ **Сохранение данных**: Полное оригинальное сообщение и детали ошибки сохраняются для анализа
- ✅ **Типизация ошибок**: Разные типы ошибок (timeout, connection, camunda_internal_error и др.)
- ✅ **Гарантия доставки**: Сообщение удаляется только после успешного перемещения в очередь ошибок
- ✅ **Документация**: Добавлен раздел по работе с очередью ошибок

### v2.3.0 - Camunda Multi-Tenancy
- ✅ **TenantAwareExternalTaskClient**: Кастомный клиент с фильтрацией по tenant ID
- ✅ **Параметр CAMUNDA_TENANT_ID**: Конфигурация tenant через переменные окружения
- ✅ **Изоляция задач**: Production и Development задачи обрабатываются независимо
- ✅ **Логирование tenant**: Отображение активного tenant при старте

### v2.2.0 - Разделение сред Production / Development
- ✅ **Раздельные конфигурации**: Поддержка `.env.prod` и `.env.dev`
- ✅ **Раздельные логи**: `logs/prod/` и `logs/dev/`
- ✅ **Метки среды**: `[PROD]` и `[DEV]` в логах