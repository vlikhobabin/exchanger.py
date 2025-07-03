# Сервисные инструменты Universal Camunda Worker

Каталог содержит вспомогательные скрипты для управления, мониторинга и диагностики системы Universal Camunda Worker.

## Скрипты

### start_process.py

Запуск новых экземпляров процессов в Camunda через REST API.

#### Возможности

- Запуск процессов по ключу процесса
- Передача переменных в JSON и key=value форматах
- Установка business key для уникальной идентификации
- Выбор конкретной версии процесса
- Dry-run режим для тестирования без фактического запуска
- Просмотр информации о процессе
- Список всех версий процесса

#### Использование

```bash
# Простой запуск процесса
python start_process.py ProcessKey

# Запуск с переменными (key=value формат)
python start_process.py ProcessKey --variables "userName=John,amount=100,approved=true"

# Запуск с переменными (JSON формат)  
python start_process.py ProcessKey --variables '{"userName": "John", "amount": 100}'

# Запуск с business key
python start_process.py ProcessKey --business-key "ORDER-123"

# Запуск конкретной версии
python start_process.py ProcessKey --version 2

# Просмотр информации о процессе
python start_process.py ProcessKey --info

# Список всех версий процесса
python start_process.py ProcessKey --list-versions

# Тестирование без запуска
python start_process.py ProcessKey --variables "test=value" --dry-run
```

#### Примеры переменных

```bash
# Строковые переменные
--variables "userName=John Doe,email=john@example.com"

# Смешанные типы
--variables "name=John,age=30,active=true,score=95.5"

# JSON объекты
--variables '{"user": {"name": "John", "age": 30}, "config": {"debug": true}}'
```

### camunda_processes.py

Получение детальной информации о процессах, экземплярах и задачах в Camunda.

#### Возможности

- Просмотр определений процессов (BPMN модели)
- Мониторинг экземпляров процессов (активных и завершенных)
- Анализ внешних задач (External Tasks)
- Просмотр пользовательских задач (User Tasks)
- Общая статистика системы
- Экспорт данных в JSON формат

#### Использование

```bash
# Полная информация о системе
python camunda_processes.py

# Только статистика
python camunda_processes.py --stats

# Только внешние задачи
python camunda_processes.py --external-tasks

# Только определения процессов
python camunda_processes.py --definitions

# Только активные экземпляры
python camunda_processes.py --instances

# Все экземпляры (включая завершенные)
python camunda_processes.py --instances --all-instances

# Только пользовательские задачи
python camunda_processes.py --user-tasks

# Экспорт в JSON файл
python camunda_processes.py --export camunda_data.json

# Комбинирование опций
python camunda_processes.py --stats --external-tasks --export stats.json
```

#### Выходная информация

- **Определения процессов**: ID, ключ, название, версия, статус развертывания
- **Экземпляры процессов**: ID, ключ процесса, business key, статус, даты
- **Внешние задачи**: ID, топик, процесс, активность, worker ID, статус блокировки
- **Пользовательские задачи**: ID, название, назначение, процесс, даты
- **Статистика**: количество процессов, экземпляров, задач по статусам

### check_queues.py

Мониторинг состояния очередей RabbitMQ.

#### Возможности

- Просмотр всех очередей проекта
- Количество сообщений в каждой очереди
- Статус подключения к RabbitMQ
- Информация об Alternate Exchange
- Проверка инфраструктуры очередей

#### Использование

```bash
# Проверка всех очередей
python check_queues.py
```

#### Выходная информация

```
🐰 ПРОВЕРКА RABBITMQ ОЧЕРЕДЕЙ
========================================
✅ Подключение к RabbitMQ успешно

🔄 Alternate Exchange: camunda.unrouted.tasks
   Тип: fanout
   Описание: Обрабатывает неопознанные сообщения

📊 Найдено очередей: 6

📬 bitrix24.queue: 🎯
   📨 Сообщений: 3
   🚫 Потребителей: 0
   ⚠️ В очереди есть необработанные сообщения!

📭 default.queue: 🔄
   📨 Сообщений: 0
   🚫 Потребителей: 0
   🔄 Источник: Alternate Exchange (camunda.unrouted.tasks)
```

### test_alternate_exchange.py

Тестирование корректности работы Alternate Exchange и маршрутизации сообщений.

#### Возможности

- Тестирование известных топиков
- Тестирование неизвестных топиков  
- Проверка отсутствия дублирования
- Анализ маршрутизации сообщений
- Отчет о результатах тестирования

#### Использование

```bash
# Полное тестирование Alternate Exchange
python test_alternate_exchange.py
```

#### Процесс тестирования

1. **Очистка очередей** - подготовка к тестированию
2. **Тест известных топиков** - проверка попадания в целевые очереди
3. **Тест неизвестных топиков** - проверка попадания в default.queue
4. **Анализ результатов** - проверка отсутствия дублирования

#### Выходная информация

```
======================================================================
                        ТЕСТИРОВАНИЕ ALTERNATE EXCHANGE                         
======================================================================
Проверка корректности маршрутизации сообщений
без дублирования в default.queue

✅ Подключение к RabbitMQ успешно
🏗️ Создание инфраструктуры с Alternate Exchange...
✅ Инфраструктура создана успешно

🧹 Очистка очередей перед тестом...
   ✅ bitrix24.queue очищена
   ✅ default.queue очищена

======================================================================
                            ТЕСТ 1: ИЗВЕСТНЫЕ ТОПИКИ                            
======================================================================
📨 Топик: bitrix_create_task
   Система: bitrix24
   Очередь: bitrix24.queue
   Статус: ✅ Отправлено

======================================================================
                     ТЕСТ 2: НЕИЗВЕСТНЫЕ ТОПИКИ (ALTERNATE EXCHANGE)                      
======================================================================
📨 Топик: unknown_service_task
   Ожидается: default.queue (через AE)
   Статус: ✅ Отправлено

======================================================================
                           РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ                            
======================================================================
🔄 Alternate Exchange:
   Название: camunda.unrouted.tasks
   Тип: fanout
   Описание: Обрабатывает неопознанные сообщения

📊 Состояние очередей:
   📬 bitrix24.queue: 4 сообщений 🎯
   📬 default.queue: 4 сообщения 🔄
      └─ Источник: Alternate Exchange (camunda.unrouted.tasks)

🔍 Анализ:
   📌 Известные топики: 4 сообщений в целевых очередях
   🔄 Неизвестные топики: 4 сообщений в default.queue
   ✅ Дублирование отсутствует - сообщения корректно разделены
```

### unlock_task.py

Разблокировка заблокированных задач в Camunda.

#### Возможности

- Разблокировка задач по ID
- Массовая разблокировка задач
- Разблокировка по топику
- Разблокировка по worker ID
- Безопасный режим с подтверждением

#### Использование

```bash
# Разблокировка конкретной задачи
python unlock_task.py --task-id abc123-def456-ghi789

# Разблокировка нескольких задач
python unlock_task.py --task-id id1,id2,id3

# Разблокировка всех задач топика
python unlock_task.py --topic bitrix_create_task

# Разблокировка задач конкретного worker
python unlock_task.py --worker-id universal-worker

# Разблокировка всех заблокированных задач (с подтверждением)
python unlock_task.py --all --confirm

# Просмотр заблокированных задач без разблокировки
python unlock_task.py --list

# Принудительная разблокировка без подтверждения
python unlock_task.py --task-id abc123 --force
```

#### Безопасность

Скрипт включает несколько уровней защиты:
- Подтверждение для массовых операций
- Проверка существования задач
- Валидация ID задач
- Логирование всех операций

### worker_diagnostics.py

Комплексная диагностика системы Universal Camunda Worker.

#### Возможности

- Проверка подключения к Camunda
- Проверка подключения к RabbitMQ
- Анализ конфигурации
- Тестирование API endpoints
- Проверка состояния очередей
- Валидация маппинга топиков

#### Использование

```bash
# Полная диагностика
python worker_diagnostics.py

# Быстрая проверка подключений
python worker_diagnostics.py --quick

# Проверка только Camunda
python worker_diagnostics.py --camunda-only

# Проверка только RabbitMQ  
python worker_diagnostics.py --rabbitmq-only

# Детальный отчет
python worker_diagnostics.py --detailed

# Экспорт результатов в файл
python worker_diagnostics.py --export diagnostics_report.json
```

#### Проверяемые компоненты

1. **Camunda Engine**
   - Доступность REST API
   - Аутентификация
   - Список определений процессов
   - Количество активных экземпляров
   - Внешние задачи

2. **RabbitMQ**
   - Подключение к серверу
   - Состояние очередей
   - Проверка exchanges
   - Права доступа

3. **Конфигурация**
   - Валидация параметров
   - Проверка маппинга топиков
   - Анализ routing rules

### status_check.py

Быстрая проверка состояния всех компонентов системы.

#### Возможности

- Статус Worker процесса
- Статус Response Handler
- Общая статистика обработки
- Время работы системы
- Последние ошибки

#### Использование

```bash
# Статус системы
python status_check.py

# Краткий статус
python status_check.py --brief

# Статус с деталями производительности
python status_check.py --performance

# JSON формат (для скриптов)
python status_check.py --json
```

## Общие параметры

Все скрипты поддерживают общие параметры:

```bash
# Помощь по использованию
python script_name.py --help

# Подробный вывод
python script_name.py --verbose

# Тихий режим (только ошибки)
python script_name.py --quiet

# Использование альтернативного config файла
python script_name.py --config custom_config.py
```

## Конфигурация

Все скрипты используют настройки из основного файла `config.py`. Для переопределения параметров:

1. Создайте файл `.env` в корне проекта
2. Установите переменные окружения
3. Или используйте параметр `--config` для указания альтернативного файла

## Логирование

Все скрипты ведут логи в:
- Консоль (с цветовой подсветкой)
- Файл `logs/tools.log` (опционально)
- Системный журнал (при запуске как сервис)

## Примеры использования

### Базовый мониторинг

```bash
# Ежедневная проверка системы
python worker_diagnostics.py --detailed
python check_queues.py
python camunda_processes.py --stats
```

### Обслуживание

```bash
# Очистка заблокированных задач
python unlock_task.py --list
python unlock_task.py --all --confirm

# Перезапуск процесса для тестирования
python start_process.py TestProcess --dry-run
python start_process.py TestProcess --variables "test=true"
```

### Отладка проблем

```bash
# При проблемах с задачами
python camunda_processes.py --external-tasks
python check_queues.py --non-empty
python unlock_task.py --topic problem_topic

# При проблемах с подключением
python worker_diagnostics.py --quick
python status_check.py --performance
```

## Интеграция

Скрипты можно интегрировать в:
- Cron jobs для автоматического мониторинга
- CI/CD pipeline для проверки деплоймента
- Мониторинговые системы (Nagios, Zabbix)
- Скрипты резервного копирования

### Пример cron job

```bash
# Проверка каждые 5 минут
*/5 * * * * /path/to/python /path/to/check_queues.py --brief >> /var/log/camunda_monitor.log

# Ежедневный отчет
0 9 * * * /path/to/python /path/to/worker_diagnostics.py --export /reports/daily_$(date +\%Y\%m\%d).json
```

### queue_reader.py

Универсальная утилита для работы с сообщениями в очередях RabbitMQ.

#### Возможности

- Просмотр списка всех очередей с количеством сообщений
- Чтение первых N сообщений из очереди (без удаления)
- Экспорт всех сообщений очереди в JSON файл
- Очистка очереди с подтверждением
- Безопасный просмотр - сообщения возвращаются в очередь

#### Использование

```bash
# Список всех очередей с количеством сообщений
python queue_reader.py

# Просмотр первых 5 сообщений из очереди
python queue_reader.py errors.camunda_tasks.queue

# Просмотр первых 10 сообщений
python queue_reader.py errors.camunda_tasks.queue --count 10

# Экспорт всех сообщений в JSON файл
python queue_reader.py errors.camunda_tasks.queue --output errors_backup.json

# Очистка очереди (с подтверждением)
python queue_reader.py errors.camunda_tasks.queue --clear

# Принудительная очистка без подтверждения
python queue_reader.py errors.camunda_tasks.queue --clear --force
```

#### Функции безопасности

- **Неразрушающий просмотр**: все просмотренные сообщения возвращаются в очередь 