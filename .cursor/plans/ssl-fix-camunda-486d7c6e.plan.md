<!-- 486d7c6e-3130-4673-a2fe-20b7e5f32644 a0cc20e6-28ad-41da-9fdf-23f204fb6d24 -->
# Исправление SSL проблем Camunda External Task Client

## Проблема

Библиотека `camunda-external-task-client-python3==4.5.0` не поддерживает настройку SSL параметров. В файле `/opt/exchanger.py/venv/lib/python3.12/site-packages/camunda/client/external_task_client.py` все HTTP запросы (строки 59, 94, 113, 133) используют `requests.post()` без параметра `verify`, что приводит к SSL ошибкам:

```
SSLError(1, '[SSL: TLSV1_ALERT_DECODE_ERROR] tlsv1 alert decode error (_ssl.c:1000)')
```

## Решение

**Monkey patching библиотеки** с hardcoded `verify=False` + унификация SSL подхода во всех модулях.

## Изменения

### 1. Camunda Worker - SSL Patch Module

Создать новый модуль `/opt/exchanger.py/camunda-worker/ssl_patch.py`:

- Monkey patch для `requests.post`, `requests.get`, `requests.Session.request`
- Автоматическое добавление `verify=False` ко всем запросам к Camunda
- Отключение SSL warnings через `urllib3.disable_warnings()`
- Логирование применения патча

### 2. Интеграция патча в Camunda Worker

Обновить `/opt/exchanger.py/camunda-worker/main.py`:

- Импортировать `ssl_patch` **ДО** импорта `ExternalTaskClient`
- Добавить логирование успешного применения патча

Обновить `/opt/exchanger.py/camunda-worker/camunda_worker.py`:

- Добавить импорт `ssl_patch` в начало файла (строка ~6)

### 3. Унификация SSL в Camunda Sync

Обновить `/opt/exchanger.py/camunda-sync/camunda_client.py`:

- Добавить импорт `urllib3`
- Добавить `urllib3.disable_warnings()` в начале файла
- Добавить `verify=False` в `session.request()` (строка ~96)

Обновить `/opt/exchanger.py/camunda-sync/main.py`:

- Добавить импорт и настройку SSL warnings

### 4. Документация

Обновить `/opt/exchanger.py/camunda-worker/README.md`:

- Добавить секцию "SSL Configuration"
- Описать причину использования `verify=False`
- Предупреждение о безопасности

Обновить `/opt/exchanger.py/README.md`:

- Добавить общую информацию о SSL в проекте

## Технические детали

**Файлы для изменения:**

1. `/opt/exchanger.py/camunda-worker/ssl_patch.py` (создать)
2. `/opt/exchanger.py/camunda-worker/main.py`
3. `/opt/exchanger.py/camunda-worker/camunda_worker.py`
4. `/opt/exchanger.py/camunda-sync/camunda_client.py`
5. `/opt/exchanger.py/camunda-sync/main.py`
6. `/opt/exchanger.py/camunda-worker/README.md`
7. `/opt/exchanger.py/README.md`

**Ключевые моменты:**

- Патч применяется глобально для всех `requests` вызовов
- Hardcoded `verify=False` без конфигурации
- Совместимость с существующим кодом
- Минимальные изменения

### To-dos

- [ ] Создать модуль ssl_patch.py с monkey patching для requests библиотеки
- [ ] Интегрировать SSL патч в camunda-worker (main.py и camunda_worker.py)
- [ ] Унифицировать SSL подход в camunda-sync модуле
- [ ] Обновить документацию с информацией о SSL настройках
- [ ] Проверить работу сервисов после применения исправлений