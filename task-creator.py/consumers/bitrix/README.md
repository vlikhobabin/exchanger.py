# Bitrix24 Integration Module

Модуль интеграции с Bitrix24 для создания задач из процессов Camunda BPM.

## Описание

Этот модуль обрабатывает сообщения из RabbitMQ очереди `bitrix24.queue` и создает соответствующие задачи в Bitrix24 через REST API.

## Компоненты

- `handler.py` - Основной обработчик сообщений для создания задач в Bitrix24
- `config.py` - Конфигурация специфичная для Bitrix24
- `README.md` - Эта документация

## Конфигурация

### Переменные окружения для Bitrix24

```bash
# Обязательные настройки
BITRIX_WEBHOOK_URL=https://bx.eg-holding.ru/rest/1/123123123123

# Опциональные настройки
BITRIX_DEFAULT_RESPONSIBLE_ID=1
BITRIX_DEFAULT_PRIORITY=2
BITRIX_REQUEST_TIMEOUT=30
BITRIX_MAX_DESCRIPTION_LENGTH=10000
```

## Поддерживаемые топики

- `bitrix_create_task` - Создание новой задачи
- `bitrix_update_task` - Обновление существующей задачи
- `bitrix_create_deal` - Создание новой сделки
- `bitrix_update_deal` - Обновление существующей сделки
- `bitrix_create_contact` - Создание нового контакта
- `bitrix_create_lead` - Создание нового лида
- `bitrix_update_lead` - Обновление существующего лида
- `bitrix_create_company` - Создание новой компании
- `bitrix_update_company` - Обновление существующей компании

## Формат входящих сообщений

Модуль обрабатывает сообщения в формате JSON из Camunda:

```json
{
  "task_id": "abc123",
  "topic": "bitrix_create_task",
  "variables": {
    "title": {"value": "Название задачи"},
    "description": {"value": "Описание задачи"},
    "responsible_id": {"value": "123"},
    "priority": {"value": "2"},
    "deadline": {"value": "2024-12-31 23:59:59"}
  },
  "metadata": {
    "inputParameters": {},
    "outputParameters": {},
    "extensionProperties": {}
  }
}
```

## Извлечение данных

Обработчик извлекает данные из переменных сообщения по следующему приоритету:

### Заголовок задачи
- `title`, `name`, `subject`, `task_title`, `task_name`

### Ответственный
- `responsible_id`, `responsible`, `assignee_id`, `assignee`, `user_id`

### Приоритет
- `priority`, `task_priority`, `urgency`, `importance`
- Поддерживает: числовые значения (1-3) или текстовые ('low', 'normal', 'high')

### Дедлайн
- `deadline`, `due_date`, `end_date`, `task_deadline`

## Статистика

Модуль ведет статистику обработки:
- Общее количество сообщений
- Успешно созданные задачи
- Ошибки при создании
- Время работы
- Процент успеха
- Сообщений в минуту

## Логирование

Используется библиотека `loguru` для структурированного логирования всех операций.

## Тестирование

Для тестирования интеграции используйте тестовые скрипты из корневой папки проекта. 