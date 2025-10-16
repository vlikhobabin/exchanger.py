<!-- edfe5b72-d97e-411e-8f3e-06c6baa94498 b6388110-3bbb-405b-80f9-1bd46d511129 -->
# План оптимизации логирования и защиты от наложения инстансов

## Проблема

При переходе на `HEARTBEAT_INTERVAL=5` секунд возникают две критические проблемы:

1. **Избыточное логирование**: Monitor loop будет писать статистику каждые 5 секунд, что создаст огромные логи
2. **Наложение инстансов**: При `RestartSec=10` в systemd и возможных задержках при shutdown старый процесс может не успеть завершиться до запуска нового

## Решение

### 1. Добавление файловой блокировки (fcntl.flock)

**Файл**: `task-creator/instance_lock.py` (новый)

Создать класс `InstanceLock` с механизмом файловой блокировки:

- Lock file: `/tmp/exchanger-task-creator.lock`
- Использование `fcntl.flock()` с `LOCK_EX | LOCK_NB` (неблокирующая эксклюзивная блокировка)
- Запись PID процесса в lock file
- Автоматическое освобождение при завершении

**Интеграция**: Добавить проверку блокировки в `task-creator/main.py` перед запуском MessageProcessor

### 2. Оптимизация логирования в Monitor Loop

**Файл**: `task-creator/message_processor.py`

Изменить метод `_monitor_loop()` (строки 330-378):

**Текущее поведение**: Логирует статистику каждые `HEARTBEAT_INTERVAL` секунд

**Новое поведение**:

- Добавить отдельную конфигурацию `MONITOR_LOG_INTERVAL` (по умолчанию 300 сек = 5 минут)
- Логировать полную статистику только раз в 5 минут
- Логировать критические события (reconnect, errors) всегда

**Конфигурация**: Добавить `MONITOR_LOG_INTERVAL=300` в `config.env.example` и `WorkerConfig`

### 3. Оптимизация логирования RabbitMQ reconnection

**Файлы**:

- `task-creator/rabbitmq_consumer.py` (строка 235)
- `task-creator/rabbitmq_publisher.py` (строка 72)

**Изменения**:

- Не логировать reconnect попытки на уровне INFO при каждой проверке в monitor loop
- Изменить строку 367 в `message_processor.py`: убрать INFO лог при успешном reconnect, если прошло меньше 5 минут с последнего лога

### 4. Оптимизация логирования Tracker

**Файл**: `task-creator/consumers/bitrix/tracker.py` (строка 47)

Изменить частоту логирования:

- Не логировать "Проверка N сообщений" каждый цикл (каждые 5 сек)
- Логировать только при обнаружении сообщений ИЛИ раз в 5 минут для heartbeat

### 5. Добавление системы отслеживания критических ошибок

**Файл**: `task-creator/error_tracker.py` (новый)

Создать класс `ErrorTracker` для отслеживания критических ошибок:

- Порог: 10 ошибок за 5 минут = критическая ситуация
- При достижении порога: логирование CRITICAL и graceful shutdown
- Интеграция в `message_processor.py` для отслеживания ошибок обработки

## Технические детали

### Структура InstanceLock

```python
class InstanceLock:
    def __init__(self, lock_file="/tmp/exchanger-task-creator.lock")
    def acquire(self) -> bool  # Попытка захвата блокировки
    def release(self)           # Освобождение блокировки
    def __enter__/__exit__      # Context manager support
```

### Новые переменные в config.env.example

```bash
# Интервал логирования статистики монитора (в секундах)
MONITOR_LOG_INTERVAL=300
```

### Изменения в WorkerConfig

```python
monitor_log_interval: int = Field(default=300, env="MONITOR_LOG_INTERVAL")
```

## Файлы для изменения

1. **Новые файлы**:

   - `task-creator/instance_lock.py` - файловая блокировка
   - `task-creator/error_tracker.py` - отслеживание критических ошибок

2. **Изменяемые файлы**:

   - `task-creator/main.py` - добавление проверки instance lock
   - `task-creator/config.py` - добавление MONITOR_LOG_INTERVAL
   - `task-creator/message_processor.py` - оптимизация monitor loop
   - `task-creator/consumers/bitrix/tracker.py` - уменьшение частоты логов
   - `config.env.example` - документирование новых параметров

## Тестирование

После внедрения:

1. Запустить с `HEARTBEAT_INTERVAL=5`
2. Проверить, что логи пишутся раз в 5 минут
3. Попытаться запустить второй инстанс вручную - должен завершиться с ошибкой
4. Проверить graceful shutdown при критических ошибках

### To-dos

- [ ] Создать класс InstanceLock в task-creator/instance_lock.py с fcntl.flock блокировкой
- [ ] Создать класс ErrorTracker в task-creator/error_tracker.py для отслеживания критических ошибок
- [ ] Добавить MONITOR_LOG_INTERVAL в WorkerConfig (task-creator/config.py) и config.env.example
- [ ] Оптимизировать _monitor_loop в message_processor.py с раздельными интервалами для heartbeat и логирования
- [ ] Уменьшить частоту логирования в tracker.py (только при наличии сообщений или heartbeat)
- [ ] Интегрировать InstanceLock в main.py с обработкой ошибки при невозможности захвата блокировки
- [ ] Интегрировать ErrorTracker в message_processor.py для отслеживания критических ошибок