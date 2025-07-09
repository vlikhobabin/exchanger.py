# Camunda-StormBPMN Sync Module

Модуль для синхронизации схем процессов между StormBPMN (https://stormbpmn.com) и Camunda (https://camunda.eg-holding.ru).

## Описание

Данный модуль обеспечивает автоматическую синхронизацию BPMN диаграмм между облачной платформой StormBPMN и локальной установкой Camunda. Модуль разработан в стиле существующих модулей проекта (`task-creator.py` и `universal-worker.py`).

## Возможности

### Основные функции:
- Получение списка диаграмм из StormBPMN
- Получение данных диаграммы по GUID
- Получение списка ответственных по диаграмме
- Синхронизация BPMN XML между системами
- Маппинг метаданных и статусов

### Текущий статус:
🚧 **В разработке** - Реализован первый класс для работы с StormBPMN API

## Структура модуля

```
camunda-sync.py/
├── config.py              # Конфигурация модуля
├── main.py                # Точка входа и тестирование
├── stormbpmn_client.py    # Клиент для работы с StormBPMN API
├── camunda_client.py      # Клиент для работы с Camunda REST API
├── bpmn_converter.py      # Конвертер BPMN StormBPMN → Camunda
├── tools/                 # Утилиты и скрипты
│   ├── convert.py         # Скрипт конвертации BPMN
│   ├── deploy.py          # Скрипт деплоя в Camunda
│   ├── validate_bpmn.py   # Валидация BPMN файлов
│   ├── test_convert.py    # Тестирование конвертера
│   ├── check_element_order.py # Проверка порядка элементов в BPMN
│   ├── test_simple.bpmn   # Простой тестовый BPMN файл
│   ├── get_diagram_xml.py # Получение XML из StormBPMN
│   ├── get_diagrams_list.py # Получение списка схем
│   └── test_deploy.py     # Тестирование Camunda API
├── test_input.bpmn        # Тестовый входной файл для конвертера
├── logs/                  # Логи работы модуля
├── BPMN_CONVERTER_README.md # Документация по конвертеру
└── README.md             # Данная документация
```

## Установка и настройка

### 1. Переменные окружения

Скопируйте файл `../config.env.example` в `.env` в корне проекта и заполните необходимые параметры:

```bash
# Скопируйте общий файл конфигурации
cp ../config.env.example ../.env
```

Основные параметры для camunda-sync модуля:
- `STORMBPMN_BEARER_TOKEN` - Bearer token из браузера (обязательно)
- `SYNC_ENABLED` - включение/отключение синхронизации
- `SYNC_INTERVAL` - интервал синхронизации в секундах
- `LOG_LEVEL` - уровень логирования

### 2. Получение Bearer Token для StormBPMN

Bearer token можно получить из браузера:
1. Откройте https://stormbpmn.com и войдите в систему
2. Откройте Developer Tools (F12)
3. Перейдите на вкладку Network
4. Обновите страницу или выполните любой запрос
5. Найдите любой запрос к API и скопируйте значение заголовка `Authorization: Bearer ...`

### 3. Зависимости

Установите зависимости из корневого файла requirements.txt:

```bash
cd ..
pip install -r requirements.txt
cd camunda-sync.py
```

## Использование

### Запуск модуля

```bash
cd camunda-sync.py
python main.py
```

### Пример использования StormBPMN Client

```python
from stormbpmn_client import StormBPMNClient

# Создание клиента
client = StormBPMNClient()

# Получение списка диаграмм
diagrams = client.get_diagrams_list(size=20, page=0)
print(f"Найдено {len(diagrams['content'])} диаграмм")

# Получение конкретной диаграммы
diagram_id = "9d5687e5-6108-4f05-b46a-2d24b120ba9d"
diagram = client.get_diagram_by_id(diagram_id)
print(f"Диаграмма: {diagram['diagram']['name']}")

# Получение ответственных
assignees = client.get_diagram_assignees(diagram_id)
print(f"Ответственных: {len(assignees)}")
```

### Пример использования Camunda Client

```python
from camunda_client import CamundaClient

# Создание клиента
client = CamundaClient()

# Проверка соединения
if client.test_connection():
    print("✅ Camunda доступна")

# Деплой BPMN схемы
result = client.deploy_diagram("my_process.bpmn")
print(f"Деплой ID: {result['id']}")

# Получение списка деплоев
deployments = client.get_deployments(limit=5)
print(f"Найдено {len(deployments)} деплоев")
```

### Пример полного workflow

```bash
# 1. Получить XML схемы из StormBPMN
cd tools
python get_diagram_xml.py 9d5687e5-6108-4f05-b46a-2d24b120ba9d

# 2. Конвертировать схему для Camunda
python convert.py ../Разработка_и_получение_разрешительной_документации.bpmn

# 3. Валидация BPMN файла (опционально)
python validate_bpmn.py ../camunda_Разработка_и_получение_разрешительной_документации.bpmn

# 4. Тестирование конвертера (опционально)
python test_convert.py

# 5. Проверка порядка элементов (при ошибках ENGINE-09005)
python check_element_order.py ../camunda_Разработка_и_получение_разрешительной_документации.bpmn

# 6. Деплой в Camunda
python deploy.py ../camunda_Разработка_и_получение_разрешительной_документации.bpmn
```

### Диагностика проблем

Если при деплое возникают ошибки:

1. **Проверьте соединение с Camunda:**
   ```bash
   cd tools
   python test_deploy.py
   ```

2. **Валидируйте BPMN файл:**
   ```bash
   python validate_bpmn.py your_file.bpmn
   ```

3. **Протестируйте на простом файле:**
   ```bash
   python deploy.py test_simple.bpmn
   ```

4. **Проверьте порядок элементов:**
   ```bash
   python check_element_order.py your_file.bpmn
   ```

5. **Проверьте логи** - все ошибки API детально логируются

#### Типичные проблемы:

- **HTTP 400** - Проблемы с BPMN файлом (невалидный XML, отсутствуют обязательные элементы)
- **ENGINE-09005** - Неверный порядок элементов (incoming/outgoing перемешаны) или конфликты default flow
- **Default flow конфликты** - Эксклюзивные шлюзы с default flow, у которых есть условие
- **HTTP 401/403** - Проблемы с аутентификацией (проверьте .env)
- **HTTP 500** - Внутренняя ошибка Camunda (проверьте сервер)
- **Размер файла** - Слишком большие файлы могут вызывать проблемы

## API Reference

### StormBPMNClient

#### get_diagrams_list(size=20, page=0, **filters)
Получение списка диаграмм с пагинацией и фильтрацией.

**Параметры:**
- `size` (int): Количество диаграмм на страницу (по умолчанию 20)
- `page` (int): Номер страницы (по умолчанию 0)
- `quality` (str): Фильтр по качеству ("0,ge" - больше или равно 0)
- `view` (str): Тип представления ("TEAM" - командные диаграммы)
- `sort` (str): Сортировка ("updatedOn,desc" - по дате обновления)

**Возвращает:** dict с полным ответом API, включая пагинацию

#### get_diagram_by_id(diagram_id)
Получение полных данных диаграммы по GUID.

**Параметры:**
- `diagram_id` (str): GUID диаграммы

**Возвращает:** dict с данными диаграммы, включая BPMN XML

#### get_diagram_assignees(diagram_id)
Получение списка ответственных по диаграмме.

**Параметры:**
- `diagram_id` (str): GUID диаграммы

**Возвращает:** list словарей с информацией об ответственных

### CamundaClient

#### deploy_diagram(bpmn_file_path, deployment_name=None, enable_duplicate_filtering=False, deployment_source="camunda-sync")
Развернуть BPMN диаграмму в Camunda.

**Параметры:**
- `bpmn_file_path` (str): Путь к BPMN файлу
- `deployment_name` (str, optional): Имя деплоя (по умолчанию - имя файла)
- `enable_duplicate_filtering` (bool): Включить фильтрацию дубликатов
- `deployment_source` (str): Источник деплоя

**Возвращает:** dict с информацией о деплое и развернутых процессах

#### get_deployments(name=None, limit=10)
Получение списка деплоев с фильтрацией.

**Параметры:**
- `name` (str, optional): Фильтр по имени деплоя
- `limit` (int): Максимальное количество результатов

**Возвращает:** list деплоев

#### get_deployment_by_id(deployment_id)
Получение информации о деплое по ID.

**Параметры:**
- `deployment_id` (str): ID деплоя

**Возвращает:** dict с информацией о деплое

#### get_process_definitions(limit=10)
Получение списка определений процессов.

**Параметры:**
- `limit` (int): Максимальное количество результатов

**Возвращает:** list определений процессов

#### test_connection()
Проверка соединения с Camunda REST API.

**Возвращает:** bool - True если соединение работает

## Конфигурация

### Маппинг статусов

```python
STATUS_MAPPING = {
    "NEW": "active",
    "IN_PROGRESS": "active", 
    "DONE": "suspended",
    "ARCHIVED": "suspended"
}
```

### Фильтры синхронизации

- `SYNC_ONLY_TEAM_DIAGRAMS`: Синхронизировать только командные диаграммы
- `SYNC_ONLY_PUBLIC`: Синхронизировать только публичные диаграммы  
- `SYNC_DIAGRAM_TYPES`: Типы диаграмм для синхронизации (["BPMN"])
- `SYNC_STATUSES`: Статусы для синхронизации (["IN_PROGRESS", "DONE"])

## Логирование

Логи сохраняются в директории `logs/`:
- `camunda_sync.log` - основные логи
- `camunda_sync_errors.log` - только ошибки

Уровень логирования настраивается через `LOG_LEVEL`.

## Разработка

### Планируемые функции:
1. ✅ StormBPMNClient - базовые методы API
2. ✅ CamundaClient - деплой схем в Camunda
3. ✅ BPMN Converter - конвертация StormBPMN → Camunda
4. 🚧 Полная синхронизация диаграмм
5. 🚧 Обработка изменений в реальном времени
6. 🚧 Маппинг ролей и пользователей
7. 🚧 Валидация BPMN XML
8. 🚧 Откат изменений при ошибках

### Тестирование

Для тестирования используйте тестовую диаграмму:
- GUID: `9d5687e5-6108-4f05-b46a-2d24b120ba9d`
- Название: "Разработка и получение разрешительной документации"
- URL: https://stormbpmn.com/app/diagram/9d5687e5-6108-4f05-b46a-2d24b120ba9d

## Поддержка

При возникновении проблем:
1. Проверьте логи в директории `logs/`
2. Убедитесь, что Bearer token актуален
3. Проверьте доступность StormBPMN и Camunda API
4. Проверьте переменные окружения 