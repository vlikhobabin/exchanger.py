# Exchanger.py - Universal Integration Platform

## О проекте

Exchanger.py — комплексная платформа интеграции **Camunda BPM** с внешними системами (Bitrix24, OpenProject, 1C) через **RabbitMQ**. Обеспечивает полный цикл обработки бизнес-процессов: получение задач из Camunda, обогащение метаданными BPMN, маршрутизация во внешние системы, отслеживание выполнения и возврат результатов.

**Версия:** 2.3.0
**Язык:** Python 3.12
**Архитектура:** Микросервисная, event-driven, stateless

## Структура проекта

```
/opt/exchanger.py/
├── camunda-worker/           # Получение External Tasks из Camunda
│   ├── main.py               # Точка входа
│   ├── camunda_worker.py     # Основной класс UniversalCamundaWorker
│   ├── config.py             # Конфигурация
│   ├── rabbitmq_client.py    # Клиент RabbitMQ
│   ├── response_handler.py   # Обработка ответов из RabbitMQ
│   ├── tenant_external_task_client.py  # Multi-tenancy клиент
│   ├── bpmn_metadata_cache.py          # Кэш BPMN метаданных
│   ├── ssl_patch.py          # Monkey patching для SSL
│   └── tools/                # Утилиты диагностики
│
├── task-creator/             # Создание задач во внешних системах
│   ├── main.py               # Точка входа
│   ├── config.py             # Конфигурация и маршрутизация
│   ├── message_processor.py  # Обработчик сообщений
│   ├── base_handler.py       # Базовый класс обработчиков
│   ├── rabbitmq_consumer.py  # Потребитель RabbitMQ
│   ├── rabbitmq_publisher.py # Издатель результатов
│   ├── instance_lock.py      # Файловая блокировка инстансов
│   └── consumers/
│       ├── bitrix/           # Bitrix24 интеграция (Production)
│       │   ├── handler.py    # Создание задач
│       │   ├── tracker.py    # Отслеживание статуса
│       │   └── config.py
│       ├── openproject/      # В планах
│       ├── 1c/               # В планах
│       └── python/           # В планах
│
├── camunda-sync/             # Синхронизация BPMN диаграмм StormBPMN ↔ Camunda
│   ├── main.py
│   ├── stormbpmn_client.py
│   ├── camunda_client.py
│   ├── bpmn_converter.py
│   └── tools/                # Скрипты деплоя
│
├── servieces-management/     # Управление systemd сервисами
│   ├── install_services.sh
│   ├── start_services.sh
│   ├── stop_services.sh
│   ├── restart_services.sh
│   └── status_services.sh
│
├── env_loader.py             # Определение среды (prod/dev)
├── requirements.txt          # Python зависимости
├── config.env.example        # Шаблон конфигурации
├── .env.prod                 # Production конфигурация
└── .env.dev                  # Development конфигурация
```

## Архитектура и поток данных

```
Camunda BPM
    ↓ (External Tasks + Variables)
Camunda Worker [UniversalCamundaWorker]
    ↓ (+ BPMN Metadata из кэша)
RabbitMQ (exchanges: camunda.external.tasks)
    ↓
Task Creator [MessageProcessor + Handlers]
    ↓
External Systems (Bitrix24, OpenProject, 1C)
    ↓
*.sent.queue (bitrix24.sent.queue и т.д.)
    ↓
Task Tracker [BitrixTaskTracker]
    ↓
camunda.responses.queue
    ↓
Response Handler (встроен в Camunda Worker)
    ↓
Camunda BPM (Complete Task)
```

## Разделение сред (Production / Development)

Проект поддерживает одновременную работу двух сред на одном сервере:

| Аспект | Production | Development |
|--------|------------|-------------|
| Переменная | `EXCHANGER_ENV=prod` | `EXCHANGER_ENV=dev` |
| Конфигурация | `.env.prod` | `.env.dev` |
| Логи | `logs/prod/` | `logs/dev/` |
| Camunda Tenant | `imenaProd` | `imenaDev` |
| RabbitMQ vhost | `/prod` | `/dev` |
| Автозапуск | Да | Нет |

## Ключевые технологии

- **Camunda BPM** — движок бизнес-процессов (REST API, External Tasks, Multi-Tenancy)
- **RabbitMQ** — message broker (Topic/Direct exchanges, Virtual Hosts, Dead Letter Queue)
- **Bitrix24** — CRM система (REST API, Custom Methods, User Fields)
- **StormBPMN** — облачная платформа для BPMN диаграмм
- **Python** — pika, requests, pydantic, loguru, lxml, aiohttp

## Запуск

### Через systemd (Production)
```bash
./servieces-management/start_services.sh prod
./servieces-management/status_services.sh summary
```

### Ручной запуск (Development/Debug)
```bash
source venv/bin/activate
EXCHANGER_ENV=dev python camunda-worker/main.py
EXCHANGER_ENV=dev python task-creator/main.py
```

## Важные особенности кода

### SSL Patch
Библиотека Camunda не поддерживает SSL настройки. Используется monkey patching в `ssl_patch.py` для добавления `verify=False`.

### Multi-Tenancy
`TenantAwareExternalTaskClient` расширяет стандартный клиент для фильтрации задач по tenant ID.

### BPMN Metadata Cache
LRU кэш с TTL для хранения BPMN метаданных (extensionProperties, field injections, IO parameters).

### Stateless Architecture
Задачи блокируются в Camunda на 1 год (`CAMUNDA_LOCK_DURATION=31536000000`). Ответы обрабатываются асинхронно через Response Handler.

### Динамическая загрузка обработчиков
`QUEUE_HANDLERS` в `task-creator/config.py` определяет модули для загрузки через `importlib`.

## RabbitMQ очереди

- `camunda.external.tasks` — exchange для маршрутизации задач
- `bitrix24.queue` — входящие задачи для Bitrix24
- `bitrix24.sent.queue` — отправленные задачи для трекинга
- `camunda.responses.queue` — ответы для Camunda
- `errors.camunda_tasks.queue` — ошибки обработки

## Логи

```bash
# Production
tail -f logs/prod/camunda-worker.log
tail -f logs/prod/task-creator.log

# Development
tail -f logs/dev/camunda-worker.log
tail -f logs/dev/task-creator.log

# Systemd
journalctl -u exchanger-camunda-worker-prod -f
```

## Конфигурация

Основные переменные окружения (см. `config.env.example`):

```bash
# RabbitMQ
RABBITMQ_HOST, RABBITMQ_PORT, RABBITMQ_VIRTUAL_HOST

# Camunda
CAMUNDA_BASE_URL, CAMUNDA_TENANT_ID, CAMUNDA_AUTH_USERNAME/PASSWORD

# Bitrix24
BITRIX_WEBHOOK_URL, BITRIX_DEFAULT_RESPONSIBLE_ID

# Debug
DEBUG_SAVE_RESPONSE_MESSAGES, CAMUNDA_DEBUG
```

## Стандарты кодирования

- Логирование через `loguru` с метками среды `[PROD]`/`[DEV]`
- Конфигурация через `pydantic-settings`
- Типизация через type hints
- Документация на русском языке
- Graceful shutdown через обработку SIGINT/SIGTERM

## Диагностика

```bash
# Статус воркера
python camunda-worker/tools/worker_diagnostics.py

# Проверка очередей
python camunda-worker/tools/check_queues.py

# Информация о процессах Camunda
python camunda-worker/tools/camunda_processes.py --stats
```

## Статус компонентов

| Компонент | Статус |
|-----------|--------|
| Camunda Worker | Production |
| Task Creator - Bitrix24 | Production |
| Camunda-StormBPMN Sync | Production |
| Task Creator - OpenProject | В разработке |
| Task Creator - 1C | В планах |
| Task Tracker | В планах |
