# Модули Exchanger.py

Краткое описание всех модулей платформы интеграции Camunda BPM с внешними системами.

---

## camunda-worker

**Назначение:** Получение External Tasks из Camunda и маршрутизация в RabbitMQ

**Ключевые возможности:**
- Мониторинг External Tasks от Camunda BPM
- Multi-Tenancy — изоляция задач по tenant ID (prod/dev)
- Многопоточная обработка — отдельный поток для каждого топика
- Извлечение BPMN метаданных (Extension Properties, Field Injections, I/O Parameters)
- LRU-кэш BPMN XML с TTL 24 часа
- Интегрированный Response Handler для завершения задач
- Автоматическое переподключение к RabbitMQ
- Обработка ошибок с перемещением в `errors.camunda_tasks.queue`

**Статус:** Production

---

## task-creator

**Назначение:** Обработка сообщений из RabbitMQ и создание задач во внешних системах

**Ключевые возможности:**
- Универсальная архитектура с динамической загрузкой обработчиков
- Парсинг данных из Camunda с поддержкой BPMN метаданных
- Прямое использование `assigneeId` как `responsible_id`
- Система tracker'ов для автоматического отслеживания статуса задач
- Очереди успешных сообщений (`*.sent.queue`)
- Синхронизация процессов Camunda с Bitrix24
- Защита от множественных инстансов (файловая блокировка)
- Система отслеживания критических ошибок с автоматическим shutdown

**Поддерживаемые системы:**
| Система | Статус |
|---------|--------|
| Bitrix24 | Production |
| OpenProject | Планируется |
| 1C | Планируется |
| Python Services | Планируется |

**Статус:** Production

---

## task-creator/consumers/bitrix

**Назначение:** Интеграция с Bitrix24 — создание и управление задачами

**Ключевые возможности:**
- Создание задач через `tasks.task.add`
- Работа с шаблонами задач (`imena.camunda.tasktemplate.get`)
- Чек-листы задач (`ChecklistService`)
- Анкеты задач (`QuestionnaireService`)
- Зависимости между задачами (`PredecessorService`)
- Прикрепление файлов (`FileService`)
- Синхронизация с RabbitMQ (`SyncService`)
- Валидация обязательных UF-полей при старте
- Поддержка `questionnairesInDescription` — вывод данных анкет в описание задачи

**Компоненты:**
- `handler.py` — оркестратор создания задач
- `clients/bitrix_client.py` — API-клиент
- `services/` — сервисы (checklist, diagram, file, predecessor, questionnaire, sync, template, user)
- `validators/field_validator.py` — валидация полей

**Статус:** Production

---

## camunda-sync

**Назначение:** Синхронизация BPMN диаграмм между StormBPMN и Camunda

**Ключевые возможности:**
- Получение списка диаграмм из StormBPMN с фильтрацией
- Скачивание BPMN схем с автоматическим встраиванием метаданных
- Конвертация StormBPMN → Camunda формат
- Автоматическое встраивание ответственных и чек-листов
- Деплой сконвертированных схем в Camunda через REST API
- Вставка промежуточных задач между шлюзами
- Добавление условных выражений для потоков

**Компоненты:**
- `StormBPMNClient` — работа с API StormBPMN
- `BPMNConverter` — конвертация схем
- `CamundaClient` — работа с Camunda REST API

**Статус:** Production

---

## camunda-sync/extensions

**Назначение:** Система расширений для кастомной обработки BPMN процессов

**Описание:**
- Позволяет создавать специфичную логику для отдельных процессов
- Pre-process и post-process хуки
- Динамическая загрузка модулей по ID процесса

**Статус:** Отключена (код перенесен в основной конвертер)

---

## servieces-management

**Назначение:** Управление systemd сервисами для Production и Development сред

**Возможности:**
- Единая кодовая база с разделением по `EXCHANGER_ENV`
- Раздельные конфигурации (`.env.prod`, `.env.dev`)
- Раздельные логи (`logs/prod/`, `logs/dev/`)
- Автозапуск только для Production

**Скрипты:**
- `install_services.sh` — установка 4 systemd сервисов
- `start_services.sh [prod|dev|all]` — запуск
- `stop_services.sh [prod|dev|all]` — остановка
- `restart_services.sh [prod|dev|all]` — перезапуск
- `status_services.sh [prod|dev|all|summary]` — статус

**Сервисы:**
| Сервис | Среда | Автозапуск |
|--------|-------|------------|
| `exchanger-camunda-worker-prod` | Production | Да |
| `exchanger-task-creator-prod` | Production | Да |
| `exchanger-camunda-worker-dev` | Development | Нет |
| `exchanger-task-creator-dev` | Development | Нет |

**Статус:** Production

---

## camunda-worker/tools

**Назначение:** Сервисные утилиты для диагностики и управления

**Основные инструменты:**

| Утилита | Назначение |
|---------|------------|
| `process_manager.py` | Управление процессами Camunda (list, info, start, stop, delete) |
| `start_process.py` | Запуск процессов с переменными |
| `camunda_processes.py` | Мониторинг процессов, экземпляров, задач |
| `check_queues.py` | Мониторинг очередей RabbitMQ |
| `queue_reader.py` | Чтение/экспорт/очистка сообщений из очередей |
| `unlock_task.py` | Разблокировка заблокированных задач |
| `worker_diagnostics.py` | Комплексная диагностика системы |
| `status_check.py` | Быстрая проверка состояния компонентов |

**Статус:** Production

---

## Общая архитектура

```
Camunda BPM
    ↓ External Tasks + Variables
camunda-worker (UniversalCamundaWorker)
    ↓ + BPMN Metadata
RabbitMQ (camunda.external.tasks)
    ↓
task-creator (MessageProcessor + Handlers)
    ↓
External Systems (Bitrix24, OpenProject, 1C)
    ↓
*.sent.queue
    ↓
Task Tracker
    ↓
camunda.responses.queue
    ↓
Response Handler
    ↓
Camunda BPM (Complete Task)
```
