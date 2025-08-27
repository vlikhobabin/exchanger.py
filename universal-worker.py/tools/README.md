# Сервисные инструменты Universal Camunda Worker

Каталог содержит вспомогательные скрипты для управления, мониторинга и диагностики системы Universal Camunda Worker.

## 🚀 Быстрый старт - Process Manager

**process_manager.py** - основной инструмент для управления процессами Camunda. Рекомендуется для ежедневного использования.

```bash
# Показать список всех процессов
python universal-worker.py/tools/process_manager.py list

# Показать больше процессов
python universal-worker.py/tools/process_manager.py list --limit 20

# Подробная информация о процессе
python universal-worker.py/tools/process_manager.py info TestProcess

# Запустить процесс с переменными (JSON формат)
python universal-worker.py/tools/process_manager.py start TestProcess --variables '{"user": "John", "amount": 100}'

# Запустить процесс с переменными (key=value формат)
python universal-worker.py/tools/process_manager.py start TestProcess --variables "user=John,amount=100" --business-key "ORDER-123"

# Остановить все экземпляры процесса
python universal-worker.py/tools/process_manager.py stop TestProcess

# Удалить процесс полностью
python universal-worker.py/tools/process_manager.py delete TestProcess

# Принудительные операции без подтверждения
python universal-worker.py/tools/process_manager.py stop TestProcess --force
python universal-worker.py/tools/process_manager.py delete TestProcess --force
```

## 📋 Актуальные утилиты

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
python universal-worker.py/tools/camunda_processes.py --definitions

# Только активные экземпляры
python camunda_processes.py --instances

# Все экземпляры (включая завершенные)
python camunda_processes.py --instances --all-instances

# Только пользовательские задачи
python camunda_processes.py --user-tasks

# Экспорт в JSON файл
python camunda_processes.py --export camunda_data.json
```

### process_manager.py

Многофункциональный скрипт управления процессами Camunda.

#### Возможности

- Список процессов с базовой информацией
- Подробная информация о конкретном процессе
- Запуск новых экземпляров процессов
- Остановка всех экземпляров процесса
- Удаление процесса полностью
- Управление External Tasks

#### Использование

```bash
# Показать список процессов
python universal-worker.py/tools/process_manager.py list

# Подробная информация о процессе
python universal-worker.py/tools/process_manager.py info TestProcess

# Запустить процесс с переменными
python process_manager.py start TestProcess --variables '{"user": "John", "amount": 100}'
python process_manager.py start TestProcess --variables "user=John,amount=100" --business-key "ORDER-123"

# Остановить все экземпляры процесса
python process_manager.py stop TestProcess

# Удалить процесс полностью
python process_manager.py delete TestProcess

# Принудительные операции без подтверждения
python process_manager.py stop TestProcess --force
python process_manager.py delete TestProcess --force
```

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
python universal-worker.py/tools/check_queues.py
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
python universal-worker.py/tools/queue_reader.py

# Просмотр первых 5 сообщений из очереди
python universal-worker.py/tools/queue_reader.py bitrix24.queue

# Просмотр первых 10 сообщений
python queue_reader.py errors.camunda_tasks.queue --count 10

# Экспорт всех сообщений в JSON файл
python universal-worker.py/tools/queue_reader.py bitrix24.queue --output bitrix24_queue.json

# Очистка очереди (с подтверждением)
python universal-worker.py/tools/queue_reader.py bitrix24.queue --clear

# Принудительная очистка без подтверждения
python universal-worker.py/tools/queue_reader.py bitrix24.queue --clear --force
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

## 🔧 Общие параметры

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

## ⚙️ Конфигурация

Все скрипты используют настройки из основного файла `config.py`. Для переопределения параметров:

1. Создайте файл `.env` в корне проекта
2. Установите переменные окружения
3. Или используйте параметр `--config` для указания альтернативного файла

## 📝 Логирование

Все скрипты ведут логи в:
- Консоль (с цветовой подсветкой)
- Файл `logs/tools.log` (опционально)
- Системный журнал (при запуске как сервис)

## 💡 Примеры использования

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
python check_queues.py
python unlock_task.py --topic problem_topic

# При проблемах с подключением
python worker_diagnostics.py --quick
python status_check.py --performance
```

## 🚀 Интеграция

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

## 📊 BPMN Metadata Cache

Система кэширования метаданных BPMN интегрирована в основной worker и обеспечивает:

- **Lazy Loading** - загрузка XML только при первом обращении
- **Эффективное кэширование** с TTL и LRU стратегией очистки
- **Автоматический парсинг** Extension Properties, Field Injections, Input/Output Parameters
- **Thread-safe** операции с блокировками

### Извлекаемые метаданные

```json
{
  "extensionProperties": {
    "customProperty": "customValue"
  },
  "fieldInjections": {
    "fieldName": "fieldValue"
  },
  "inputParameters": {
    "inputParam": "inputValue"
  },
  "outputParameters": {
    "outputParam": "outputValue"
  },
  "activityInfo": {
    "id": "Activity_1",
    "name": "Task Name",
    "type": "external",
    "topic": "topic_name"
  }
}
```

### Производительность

- **Парсинг XML**: ~0.001s (первый раз)
- **Обращение к кэшу**: ~0.0002s
- **Ускорение**: 5-6x
- **Кэш**: до 150 процессов, TTL 24 часа 