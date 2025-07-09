# Camunda-StormBPMN Sync Service

Сервис для синхронизации BPMN диаграмм между StormBPMN (https://stormbpmn.com) и Camunda (https://camunda.eg-holding.ru).

## Описание

Данный сервис обеспечивает полный цикл переноса BPMN диаграмм из облачной платформы StormBPMN в локальную установку Camunda с автоматической конвертацией формата и встраиванием метаданных об ответственных.

## Возможности

- **Получение списка диаграмм** из StormBPMN с фильтрацией и пагинацией
- **Скачивание BPMN схем** с автоматическим сохранением XML и списка ответственных
- **Автоматическая конвертация** StormBPMN → Camunda формат с встраиванием ответственных
- **Деплой сконвертированных схем** в Camunda через REST API

## Архитектура

### Основные компоненты:

#### Классы:
- **`StormBPMNClient`** (`stormbpmn_client.py`) - работа с API StormBPMN
- **`BPMNConverter`** (`bpmn_converter.py`) - конвертация BPMN схем
- **`CamundaClient`** (`camunda_client.py`) - работа с Camunda REST API

#### Сервисные скрипты:
- **`get_diagrams_list.py`** - получение списка процессов
- **`get_diagram_xml.py`** - получение схемы процесса и ответственных
- **`convert.py`** - конвертация схемы для Camunda
- **`deploy.py`** - деплой схемы в Camunda

## Основной Workflow

### 1. Получение списка процессов

**Описание**: Получение списка доступных BPMN диаграмм из StormBPMN с возможностью фильтрации.

**Класс**: `StormBPMNClient`
**Методы**: 
- `get_diagrams_list(size=20, page=0, **filters)` - получение списка с пагинацией

**Сервисный скрипт**: `tools/get_diagrams_list.py`

**Использование**:
```bash
cd tools
python get_diagrams_list.py
```

**Результат**: JSON список диаграмм с метаданными (название, ID, автор, дата обновления)

**Пример вывода**:
```json
{
  "content": [
    {
      "id": "9d5687e5-6108-4f05-b46a-2d24b120ba9d",
      "name": "Разработка и получение разрешительной документации",
      "status": "IN_PROGRESS",
      "authorUsername": "user@company.com",
      "updatedOn": "2024-01-15T10:30:00Z"
    }
  ],
  "totalElements": 197,
  "totalPages": 10
}
```

---

### 2. Получение схемы процесса по ID

**Описание**: Скачивание BPMN XML диаграммы и списка ответственных по GUID.

**Класс**: `StormBPMNClient`
**Методы**: 
- `get_diagram_by_id(diagram_id)` - получение BPMN XML
- `get_diagram_assignees(diagram_id)` - получение списка ответственных

**Сервисный скрипт**: `tools/get_diagram_xml.py`

**Использование**:
```bash
cd tools
python get_diagram_xml.py 9d5687e5-6108-4f05-b46a-2d24b120ba9d
```

**Результат**: 
- Файл `{название_диаграммы}.bpmn` в корне проекта
- Файл `{название_диаграммы}_assignees.json` с ответственными

**Пример результата**:
```
📁 Разработка_и_получение_разрешительной_документации.bpmn
📁 Разработка_и_получение_разрешительной_документации_assignees.json
```

**Содержимое _assignees.json**:
```json
[
  {
    "assigneeEdgeId": 15700296,
    "assigneeName": "Рук.отд. арх.сопр. и анализа проектов",
    "assigneeId": 15298311,
    "elementId": "Activity_1597r5e",
    "elementName": "Поставить задачу",
    "assigneeType": "HUMAN",
    "duration": 900
  }
]
```

---

### 3. Конвертация схемы для Camunda

**Описание**: Преобразование BPMN схемы из формата StormBPMN в формат Camunda с автоматическим встраиванием ответственных.

**Класс**: `BPMNConverter`
**Методы**: 
- `convert_file(input_file, assignees_data=None)` - конвертация с встраиванием ответственных

**Сервисный скрипт**: `tools/convert.py`

**Использование**:
```bash
cd tools
python convert.py ../Разработка_и_получение_разрешительной_документации.bpmn
```

**Автоматическая логика**:
1. Ищет файл `{название}_assignees.json` рядом с BPMN файлом
2. Если найден - автоматически встраивает ответственных в serviceTask элементы
3. Применяет все необходимые преобразования для Camunda

**Результат**: Файл `camunda_{название_диаграммы}.bpmn` готовый для деплоя

**Основные преобразования**:
- Все задачи → `serviceTask` с `camunda:type="external"` и `camunda:topic="bitrix_create_task"`
- Удаление промежуточных событий с перенаправлением потоков
- Встраивание ответственных как `camunda:properties`
- Добавление условных выражений для потоков "да"/"нет"
- Исправление порядка элементов согласно BPMN спецификации

---

### 4. Деплой схемы в Camunda

**Описание**: Развертывание сконвертированной BPMN схемы в Camunda Platform.

**Класс**: `CamundaClient`
**Методы**: 
- `deploy_diagram(bpmn_file_path, deployment_name=None)` - деплой с созданием нового деплоя

**Сервисный скрипт**: `tools/deploy.py`

**Использование**:
```bash
cd tools
python deploy.py ../camunda_Разработка_и_получение_разрешительной_документации.bpmn
```

**Результат**: 
- Новый deployment в Camunda
- Активные определения процессов готовые к выполнению
- Подробная информация о развернутых процессах

**Пример вывода**:
```
🎉 Деплой завершен успешно!
🆔 ID деплоя: 12345678-1234-5678-9012-123456789012
📋 Развернутые процессы (1):
   📋 Разработка и получение разрешительной документации
      Key: Process_1d4oa6g46
      Version: 3
      Исполняемый: ✅ Да
```

## Полный пример workflow

```bash
# 1. Получаем список процессов
cd camunda-sync.py/tools
python get_diagrams_list.py

# 2. Скачиваем нужную схему (заменить на реальный ID)
python get_diagram_xml.py 9d5687e5-6108-4f05-b46a-2d24b120ba9d

# 3. Конвертируем для Camunda (автоматически найдет и встроит ответственных)
python convert.py ../Разработка_и_получение_разрешительной_документации.bpmn

# 4. Разворачиваем в Camunda
python deploy.py ../camunda_Разработка_и_получение_разрешительной_документации.bpmn
```

## Дополнительные возможности

### Получение только ответственных

Если нужно проанализировать ответственных без скачивания XML:

```bash
cd tools
python get_diagram_assignees.py 9d5687e5-6108-4f05-b46a-2d24b120ba9d
```

Выводит JSON + краткую статистику по ответственным.

## Установка и настройка

### 1. Зависимости

```bash
cd ..
pip install -r requirements.txt
```

### 2. Переменные окружения

Скопируйте файл `../config.env.example` в `../.env` и заполните:

```bash
# StormBPMN API
STORMBPMN_BEARER_TOKEN=your_bearer_token_here

# Camunda API  
CAMUNDA_BASE_URL=https://camunda.eg-holding.ru/engine-rest
CAMUNDA_AUTH_USERNAME=your_username
CAMUNDA_AUTH_PASSWORD=your_password
```

### 3. Получение Bearer Token

1. Откройте https://stormbpmn.com и войдите в систему
2. F12 → Network → любой запрос к API
3. Скопируйте значение заголовка `Authorization: Bearer ...`

## Диагностика проблем

### Проверка соединений

```bash
cd tools
# Тест StormBPMN API
python get_diagrams_list.py

# Тест Camunda API  
python deploy.py --test  # (если добавить опцию)
```

### Логи

Все операции логируются с детальной информацией об ошибках для быстрой диагностики проблем.

## API Reference

### StormBPMNClient

- `get_diagrams_list(size=20, page=0, **filters)` - список диаграмм
- `get_diagram_by_id(diagram_id)` - данные диаграммы с BPMN XML
- `get_diagram_assignees(diagram_id)` - список ответственных

### BPMNConverter

- `convert_file(input_file, assignees_data=None)` - конвертация с встраиванием

### CamundaClient  

- `deploy_diagram(bpmn_file_path, deployment_name=None)` - деплой
- `get_deployments(limit=10)` - список деплоев
- `test_connection()` - проверка соединения

## Поддержка

При возникновении проблем проверьте:
1. Актуальность Bearer token для StormBPMN
2. Доступность Camunda сервера
3. Правильность учетных данных в .env
4. Логи выполнения команд 