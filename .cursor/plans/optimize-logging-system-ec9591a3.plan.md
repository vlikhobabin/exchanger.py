<!-- ec9591a3-fb08-4dc7-bef9-276b94cb84f0 95b214a8-61d1-468a-adff-0fd02920508e -->
# Оптимизация системы логирования

## Текущая проблема

Сейчас логи пишутся в два места:

- `/opt/exchanger.py/logs/` - основной каталог (для обоих сервисов)
- `/opt/exchanger.py/task-creator/logs/` - дублирующий каталог (только task-creator)

Имена файлов не соответствуют именам сервисов, что создает путаницу.

## Решение

### 1. Обновление task-creator логирования

Файл: `task-creator/main.py`

Заменить в функции `setup_logging()` (строки 42 и 52):

```python
# Было:
logger.add("logs/worker.log", ...)
logger.add("logs/worker_errors.log", ...)

# Станет:
logger.add("/opt/exchanger.py/logs/exchanger-task-creator.log", ...)
logger.add("/opt/exchanger.py/logs/exchanger-task-creator-errors.log", ...)
```

Также удалить строку 38 создания локальной директории `logs`:

```python
os.makedirs("logs", exist_ok=True)  # <- удалить эту строку
```

### 2. Обновление camunda-worker логирования

Файл: `camunda-worker/main.py`

Заменить в функции `setup_logging()` (строки 40 и 50):

```python
# Было:
logger.add("logs/camunda_worker.log", ...)
logger.add("logs/camunda_worker_errors.log", ...)

# Станет:
logger.add("/opt/exchanger.py/logs/camunda-worker.log", ...)
logger.add("/opt/exchanger.py/logs/camunda-worker-errors.log", ...)
```

### 3. Очистка старых логов

Удалить все существующие лог-файлы и дублирующую директорию:

```bash
# Удаление старых логов из основного каталога
rm -f /opt/exchanger.py/logs/worker.log*
rm -f /opt/exchanger.py/logs/worker_errors.log*
rm -f /opt/exchanger.py/logs/camunda_worker.log*
rm -f /opt/exchanger.py/logs/camunda_worker_errors.log*

# Удаление дублирующего каталога
rm -rf /opt/exchanger.py/task-creator/logs/
```

### 4. Перезапуск сервисов

После внесения изменений перезапустить оба сервиса для применения новой конфигурации логирования:

```bash
cd /opt/exchanger.py/servieces-management
./restart_services.sh
```

## Результат

После выполнения структура логов:

```
/opt/exchanger.py/logs/
├── exchanger-task-creator.log        # Основные логи task-creator
├── exchanger-task-creator-errors.log # Ошибки task-creator
├── camunda-worker.log                # Основные логи camunda-worker
└── camunda-worker-errors.log         # Ошибки camunda-worker
```

Преимущества:

- Единое место для всех логов
- Четкие имена, соответствующие systemd сервисам
- Нет дублирования
- Упрощенный мониторинг

### To-dos

- [ ] Обновить конфигурацию логирования в task-creator/main.py: использовать абсолютные пути и новые имена файлов
- [ ] Обновить конфигурацию логирования в camunda-worker/main.py: использовать абсолютные пути и новые имена файлов
- [ ] Удалить старые лог-файлы и дублирующий каталог task-creator/logs/
- [ ] Перезапустить оба сервиса через restart_services.sh для применения изменений