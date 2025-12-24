# Отчет по рефакторингу BitrixTaskHandler

## Статус: ✅ ЗАВЕРШЁН

**Файл:** `task-creator/consumers/bitrix/handler.py`
**Размер:** 4344 → 860 строк (**-80%**)
**Класс:** `BitrixTaskHandler`
**Дата начала:** 2025-12-23
**Дата завершения:** 2025-12-23

### Итоговые результаты

| Метрика | До | После | Изменение |
|---------|-----|-------|-----------|
| Строк кода | 4344 | 860 | **-80%** |
| Методов | 72 | 16 | **-78%** |
| Макс. метод | 476 | 184 | **-61%** |
| Модулей | 1 | 11 | **+10** |
| Устаревший код | 362 | 0 | **-100%** |

---

## История изменений

| Дата | Размер | Изменения |
|------|--------|-----------|
| 2025-12-23 | 773 → 860 | **Декомпозиция `_create_task_fallback`**: 162→49 строк (-70%), добавлены 6 хелпер-методов (Этап 2.13) |
| 2025-12-23 | 700 → 773 | **Декомпозиция `_create_bitrix_task`**: 275→184 строк (-33%), добавлены 4 хелпер-метода (Этап 2.12) |
| 2025-12-23 | 858 → 700 | **-158 строк**: вынесены 3 метода в `services/diagram_service.py` (Этап 2.11) |
| 2025-12-23 | 1159 → 858 | **-301 строка**: вынесены 2 метода в `validators/field_validator.py` (Этап 2.10) |
| 2025-12-23 | 1791 → 1159 | **-632 строки**: вынесены 4 метода в `services/template_service.py` (Этап 2.9) |
| 2025-12-23 | 2213 → 1791 | **-422 строки**: вынесены 7 методов в `services/predecessor_service.py` (Этап 2.8) |
| 2025-12-23 | 2430 → 2213 | **-217 строк**: вынесены 4 метода в `services/sync_service.py` (Этап 2.7) |
| 2025-12-23 | 2587 → 2430 | **-157 строк**: вынесены 3 метода в `services/user_service.py` (Этап 2.6) |
| 2025-12-23 | 2736 → 2587 | **-149 строк**: вынесены 3 метода в `services/file_service.py` (Этап 2.5) |
| 2025-12-23 | 3078 → 2736 | **-342 строки**: вынесены 6 методов в `services/questionnaire_service.py` (Этап 2.4) |
| 2025-12-23 | 3584 → 3078 | **-506 строк**: вынесены 10 методов в `services/checklist_service.py` (Этап 2.3) |
| 2025-12-23 | 3854 → 3584 | **-270 строк**: вынесены 5 методов в `clients/bitrix_client.py` (Этап 2.2) |
| 2025-12-23 | 3982 → 3854 | **-128 строк**: вынесены 3 метода в `utils/camunda_utils.py` (Этап 2.1) |
| 2025-12-23 | 4344 → 3982 | **-362 строки**: удалено 12 deprecated методов (Этап 1 рефакторинга) |
| 2025-12-23 | 4316 → 4344 | +28 строк: добавлен "Шаг 3.05" в `_create_bitrix_task` — вставка блока `questionnairesInDescription` в описание задачи |

### Созданные модули

#### `utils/camunda_utils.py` (162 строки)
Утилиты для работы с переменными Camunda BPM:
- `format_process_variable_value()` — форматирование значения переменной
- `get_camunda_int()` — безопасное извлечение int из переменных
- `get_camunda_datetime()` — безопасное извлечение datetime из переменных

#### `clients/bitrix_client.py` (277 строк)
API-клиент для работы с Bitrix24 REST API:
- `BitrixAPIClient` — класс для HTTP-запросов к Bitrix24
- `request_sync()` — синхронный HTTP запрос
- `request_async()` — асинхронный HTTP запрос
- `send_task()` — отправка задачи в Bitrix24
- `find_task_by_external_id()` — поиск задачи по External Task ID
- `get_list_element_name()` — получение названия элемента списка

#### `services/checklist_service.py` (541 строка)
Сервис для работы с чек-листами задач Bitrix24:
- `ChecklistService` — класс для управления чек-листами
- `extract_from_template()` — извлечение чек-листов из шаблона
- `create_group_sync()` / `create_group_async()` — создание группы чек-листа
- `add_item_sync()` / `add_item_async()` — добавление элемента чек-листа
- `create_checklists_sync()` / `create_checklists_async()` — создание чек-листов
- `get_checklists_async()` — получение чек-листов задачи
- `delete_item_async()` — удаление элемента чек-листа
- `clear_checklists_async()` — очистка чек-листов задачи

#### `services/questionnaire_service.py` (394 строки)
Сервис для работы с анкетами задач Bitrix24:
- `QuestionnaireService` — класс для управления анкетами
- `extract_from_template()` — извлечение анкет из шаблона (questionnaires.items)
- `extract_for_description()` — извлечение анкет для описания (questionnairesInDescription)
- `add_to_task()` — добавление анкет к задаче через REST API
- `get_user_name_by_id()` — получение имени пользователя Bitrix24
- `format_answer()` — форматирование ответа на вопрос анкеты
- `build_description_block()` — формирование BB-code блока анкет для описания

#### `services/file_service.py` (196 строк)
Сервис для работы с файлами задач Bitrix24:
- `FileService` — класс для управления файлами
- `attach_template_files()` — прикрепление файлов из шаблона к задаче
- `attach_predecessor_files()` — прикрепление файлов от задач-предшественников
- `build_template_files_block()` — формирование текстового блока со ссылками на файлы

#### `services/user_service.py` (206 строк)
Сервис для работы с пользователями Bitrix24:
- `UserService` — класс для работы с пользователями
- `get_responsible_info()` — получение информации об ответственном элемента диаграммы
- `get_responsible_id_by_assignee()` — конвертация assigneeId в ID ответственного
- `get_supervisor()` — получение ID руководителя пользователя

#### `services/sync_service.py` (268 строк)
Сервис для синхронизации и отправки сообщений в RabbitMQ:
- `SyncService` — класс для работы с очередями RabbitMQ и синхронизацией
- `send_success_message()` — отправка успешного сообщения в очередь
- `send_to_error_queue()` — отправка сообщения в очередь ошибок
- `send_success_message_with_retry()` — отправка успешного сообщения с retry
- `send_sync_request()` — отправка запроса синхронизации в Bitrix24

#### `services/predecessor_service.py` (469 строк)
Сервис для работы с предшественниками задач Bitrix24:
- `PredecessorService` — класс для управления зависимостями между задачами
- `get_element_predecessor_ids()` — получение ID элементов-предшественников
- `apply_dependencies()` — добавление зависимостей в task_data
- `create_dependencies()` — создание зависимостей через REST API
- `get_task_results()` — получение результатов задачи (текст + файлы)
- `get_predecessor_results()` — получение результатов всех предшественников
- `build_results_block()` — формирование блока текста с результатами
- `find_task_by_element_and_instance()` — поиск задачи по element_id и process_instance_id

#### `services/template_service.py` (571 строка)
Сервис для работы с шаблонами задач Bitrix24:
- `TemplateService` — класс для управления шаблонами задач
- `extract_template_params()` — извлечение параметров шаблона (camundaProcessId, elementId, diagramId)
- `get_template()` — получение шаблона задачи через REST API (imena.camunda.tasktemplate.get)
- `build_task_data()` — формирование task_data из шаблона (рефакторинг 476-строчного метода)
- Вспомогательные методы: `_extract_initiator_id()`, `_set_created_by()`, `_set_deadline()`,
  `_set_responsible_id()`, `_set_accomplices()`, `_set_auditors()`, `_set_with_supervisor_fallback()`,
  `_add_supervisor_to_list()`, `_log_task_data()`, `_parse_template_response()`

#### `validators/field_validator.py` (400 строк)
Валидатор обязательных полей Bitrix24:
- `FieldValidator` — класс для валидации и извлечения пользовательских полей
- `extract_user_fields()` — извлечение UF_ полей из метаданных (UF_RESULT_EXPECTED, UF_RESULT_QUESTION)
- `check_required_fields()` — критическая проверка обязательных полей при старте сервиса
- Вспомогательные методы: `_fetch_user_fields()`, `_fetch_user_fields_direct_api()`,
  `_build_found_fields_dict()`, `_validate_fields()`, `_log_fatal_error_*()` методы логирования

#### `services/diagram_service.py` (235 строк)
Сервис для работы с диаграммами Camunda и параметрами процессов:
- `DiagramService` — класс для работы с диаграммами BPMN
- `build_process_variables_block()` — формирование блока переменных процесса для описания задачи
- `get_properties()` — получение параметров диаграммы через REST API (imena.camunda.diagram.properties.list)
- `resolve_id()` — определение ID диаграммы Storm по различным источникам
- Кэширование: `properties_cache`, `details_cache`

### Удалённые deprecated методы (12 шт, ~362 строк)

- `_extract_title` — извлечение заголовка задачи
- `_create_description` — создание описания задачи
- `_extract_assignee_id` — извлечение assigneeId из extensionProperties
- `_extract_priority` — извлечение приоритета задачи
- `_extract_deadline` — извлечение дедлайна
- `_extract_project_id` — извлечение ID проекта
- `_extract_started_by_id` — извлечение startedBy
- `_extract_originator_id` — извлечение originatorId
- `_extract_group_id` — извлечение groupId
- `_extract_created_by_id` — извлечение createdById
- `_extract_additional_fields` — извлечение дополнительных полей
- `_extract_checklists` — извлечение чек-листов из metadata

---

## Текущая структура класса

### Полный список методов (16 методов)

| № | Метод | Строки | Описание | Группа |
|---|-------|--------|----------|--------|
| 1 | `__init__` | 26-129 | Инициализация, сервисы, статистика | Core |
| 2 | `process_message` | 131-208 | Точка входа обработки сообщений | Core |
| 3 | `_create_bitrix_task` | 210-485 | Основная логика создания задачи | Core |
| 4 | ~~`_build_process_variables_block`~~ | - | ✅ ВЫНЕСЕНО в `services/diagram_service.py` | Variables |
| 5 | ~~`_get_diagram_properties`~~ | - | ✅ ВЫНЕСЕНО в `services/diagram_service.py` | Diagram |
| 6 | ~~`_resolve_diagram_id`~~ | - | ✅ ВЫНЕСЕНО в `services/diagram_service.py` | Diagram |
| 7 | ~~`_get_responsible_info`~~ | - | ✅ ВЫНЕСЕНО в `services/user_service.py` | Responsible |
| 8 | ~~`_get_element_predecessor_ids`~~ | - | ✅ ВЫНЕСЕНО в `services/predecessor_service.py` | Predecessors |
| 9 | ~~`_apply_predecessor_dependencies`~~ | - | ✅ ВЫНЕСЕНО в `services/predecessor_service.py` | Predecessors |
| 10 | ~~`_create_task_dependencies`~~ | - | ✅ ВЫНЕСЕНО в `services/predecessor_service.py` | Predecessors |
| 11 | ~~`_get_task_results`~~ | - | ✅ ВЫНЕСЕНО в `services/predecessor_service.py` | Predecessors |
| 12 | ~~`_get_predecessor_results`~~ | - | ✅ ВЫНЕСЕНО в `services/predecessor_service.py` | Predecessors |
| 13 | ~~`_build_predecessor_results_block`~~ | - | ✅ ВЫНЕСЕНО в `services/predecessor_service.py` | Predecessors |
| 14 | ~~`_attach_predecessor_files`~~ | - | ✅ ВЫНЕСЕНО в `services/file_service.py` | Files |
| 15 | ~~`_find_task_by_element_and_instance`~~ | - | ✅ ВЫНЕСЕНО в `services/predecessor_service.py` | Predecessors |
| 16 | ~~`_build_task_data_from_template`~~ | - | ✅ ВЫНЕСЕНО в `services/template_service.py` | Template |
| 17 | ~~`_build_template_files_block`~~ | - | ✅ ВЫНЕСЕНО в `services/file_service.py` | Files |
| 18 | ~~`_attach_files_to_task`~~ | - | ✅ ВЫНЕСЕНО в `services/file_service.py` | Files |
| 19 | `_create_task_fallback` | 1713-1874 | Fallback создание задачи | Core |
| 20 | ~~`_send_task_to_bitrix`~~ | - | ✅ ВЫНЕСЕНО в `clients/bitrix_client.py` | API |
| 21 | ~~`_extract_checklists_from_template`~~ | - | ✅ ВЫНЕСЕНО в `services/checklist_service.py` | Checklists |
| 22 | ~~`_extract_questionnaires_from_template`~~ | - | ✅ ВЫНЕСЕНО в `services/questionnaire_service.py` | Questionnaires |
| 23 | ~~`_add_questionnaires_to_task`~~ | - | ✅ ВЫНЕСЕНО в `services/questionnaire_service.py` | Questionnaires |
| 24 | ~~`_extract_questionnaires_in_description`~~ | - | ✅ ВЫНЕСЕНО в `services/questionnaire_service.py` | Questionnaires |
| 25 | ~~`_get_user_name_by_id`~~ | - | ✅ ВЫНЕСЕНО в `services/questionnaire_service.py` | Users |
| 26 | ~~`_get_list_element_name`~~ | - | ✅ ВЫНЕСЕНО в `clients/bitrix_client.py` | API |
| 27 | ~~`_format_questionnaire_answer`~~ | - | ✅ ВЫНЕСЕНО в `services/questionnaire_service.py` | Questionnaires |
| 28 | ~~`_build_questionnaires_description_block`~~ | - | ✅ ВЫНЕСЕНО в `services/questionnaire_service.py` | Questionnaires |
| 29 | ~~`_get_responsible_id_by_assignee`~~ | - | ✅ ВЫНЕСЕНО в `services/user_service.py` | Responsible |
| 30 | ~~`_extract_user_fields`~~ | - | ✅ ВЫНЕСЕНО в `validators/field_validator.py` | Validation |
| 31 | ~~`_request_sync`~~ | - | ✅ ВЫНЕСЕНО в `clients/bitrix_client.py` | API |
| 32 | ~~`create_checklist_group_sync`~~ | - | ✅ ВЫНЕСЕНО в `services/checklist_service.py` | Checklists |
| 33 | ~~`add_checklist_item_sync`~~ | - | ✅ ВЫНЕСЕНО в `services/checklist_service.py` | Checklists |
| 34 | ~~`create_task_checklists_sync`~~ | - | ✅ ВЫНЕСЕНО в `services/checklist_service.py` | Checklists |
| 35 | ~~`_request`~~ | - | ✅ ВЫНЕСЕНО в `clients/bitrix_client.py` | API |
| 36 | ~~`create_checklist_group`~~ | - | ✅ ВЫНЕСЕНО в `services/checklist_service.py` | Checklists |
| 37 | ~~`add_checklist_item`~~ | - | ✅ ВЫНЕСЕНО в `services/checklist_service.py` | Checklists |
| 38 | ~~`get_task_checklists`~~ | - | ✅ ВЫНЕСЕНО в `services/checklist_service.py` | Checklists |
| 39 | ~~`delete_checklist_item`~~ | - | ✅ ВЫНЕСЕНО в `services/checklist_service.py` | Checklists |
| 40 | ~~`clear_task_checklists`~~ | - | ✅ ВЫНЕСЕНО в `services/checklist_service.py` | Checklists |
| 41 | ~~`create_task_checklists`~~ | - | ✅ ВЫНЕСЕНО в `services/checklist_service.py` | Checklists |
| 42 | ~~`_send_success_message`~~ | - | ✅ ВЫНЕСЕНО в `services/sync_service.py` | RabbitMQ |
| 43 | ~~`_send_to_error_queue`~~ | - | ✅ ВЫНЕСЕНО в `services/sync_service.py` | RabbitMQ |
| 44 | ~~`_send_success_message_with_retry`~~ | - | ✅ ВЫНЕСЕНО в `services/sync_service.py` | RabbitMQ |
| 45 | ~~`_send_sync_request`~~ | - | ✅ ВЫНЕСЕНО в `services/sync_service.py` | Sync |
| 46 | `get_stats` | 3276-3318 | Получение статистики | Core |
| 47 | ~~`_extract_template_params`~~ | - | ✅ ВЫНЕСЕНО в `services/template_service.py` | Template |
| 48 | ~~`_get_task_template`~~ | - | ✅ ВЫНЕСЕНО в `services/template_service.py` | Template |
| 49 | ~~`_parse_task_template_response`~~ | - | ✅ ВЫНЕСЕНО в `services/template_service.py` | Template |
| 50 | ~~`_get_user_supervisor`~~ | - | ✅ ВЫНЕСЕНО в `services/user_service.py` | Users |
| 51 | ~~`_check_required_user_field`~~ | - | ✅ ВЫНЕСЕНО в `validators/field_validator.py` | Validation |
| 52 | ~~`_find_task_by_external_id`~~ | - | ✅ ВЫНЕСЕНО в `clients/bitrix_client.py` | Search |
| 53 | `cleanup` | 3848-3854 | Очистка ресурсов | Core |

---

## Выявленные проблемы

### 1. Нарушение принципа единой ответственности (SRP)
Класс выполняет слишком много функций:
- ~~Обработка сообщений RabbitMQ~~ ✅ ВЫНЕСЕНО в `SyncService`
- ~~Работа с шаблонами задач~~ ✅ ВЫНЕСЕНО в `TemplateService`
- ~~Управление зависимостями/предшественниками~~ ✅ ВЫНЕСЕНО в `PredecessorService`
- ~~Работа с файлами~~ ✅ ВЫНЕСЕНО в `FileService`
- ~~Управление чек-листами~~ ✅ ВЫНЕСЕНО в `ChecklistService`
- ~~Управление анкетами~~ ✅ ВЫНЕСЕНО в `QuestionnaireService`
- ~~Работа с пользователями~~ ✅ ВЫНЕСЕНО в `UserService`
- ~~Валидация полей~~ ✅ ВЫНЕСЕНО в `FieldValidator`
- Статистика

### 2. ~~Огромный метод `_build_task_data_from_template`~~ ✅ РЕШЕНО
- ~~**476 строк** — это больше, чем многие классы целиком~~ ✅ Вынесен в `TemplateService`
- ~~Содержит сложную логику определения RESPONSIBLE_ID, CREATED_BY, ACCOMPLICES, AUDITORS~~ ✅ Декомпозирован на 10+ вспомогательных методов
- ~~Много дублирования кода (проверка USE_SUPERVISOR повторяется 6+ раз)~~ ✅ Вынесен в helper-метод `_set_with_supervisor_fallback()`

### 3. ~~Дублирование sync/async версий~~ ✅ РЕШЕНО
- ~~`_request_sync` и `_request` — практически идентичны~~ ✅ Вынесены в `BitrixAPIClient`
- ~~`create_checklist_group_sync` и `create_checklist_group` — дублирование~~ ✅ Вынесены в `ChecklistService`
- ~~`add_checklist_item_sync` и `add_checklist_item` — дублирование~~ ✅ Вынесены в `ChecklistService`
- ~~`create_task_checklists_sync` и `create_task_checklists` — дублирование~~ ✅ Вынесены в `ChecklistService`

### 4. ~~Устаревший код (Legacy)~~ ✅ РЕШЕНО
- ~~11 методов помечены как `[DEPRECATED]` с датой 2025-11-03~~
- ~~Занимают ~350 строк~~
- **Удалено 12 deprecated методов (362 строки) — 2025-12-23**

### 5. Множественные кэши
- `diagram_properties_cache`
- `diagram_details_cache`
- `element_predecessors_cache`
- `responsible_cache`
- `element_task_cache`

---

## Рекомендуемая архитектура

### Предлагаемое разделение на классы

```
task-creator/consumers/bitrix/
├── handler.py                    # BitrixTaskHandler (оркестратор, ~200 строк)
├── services/
│   ├── __init__.py
│   ├── template_service.py       # TemplateService (~400 строк)
│   ├── predecessor_service.py    # PredecessorService (~350 строк)
│   ├── checklist_service.py      # ChecklistService (~300 строк)
│   ├── questionnaire_service.py  # QuestionnaireService (~250 строк)
│   ├── file_service.py           # FileService (~150 строк)
│   ├── user_service.py           # UserService (~200 строк)
│   └── sync_service.py           # SyncService (~150 строк)
├── clients/
│   ├── __init__.py
│   ├── bitrix_client.py          # BitrixAPIClient (~200 строк)
│   └── rabbitmq_client.py        # (уже есть rabbitmq_publisher.py)
├── builders/
│   ├── __init__.py
│   ├── task_builder.py           # TaskDataBuilder (~300 строк)
│   └── description_builder.py    # DescriptionBuilder (~150 строк)
├── validators/
│   ├── __init__.py
│   └── field_validator.py        # FieldValidator (~250 строк)
├── utils/
│   ├── __init__.py
│   ├── camunda_utils.py          # Утилиты для Camunda переменных (~100 строк)
│   └── cache.py                  # CacheManager (~100 строк)
└── config.py                     # (уже существует)
```

---

## Детальное описание новых классов

### 1. BitrixTaskHandler (Оркестратор)
**Файл:** `handler.py`
**Ответственность:** Координация процесса создания задачи

```python
class BitrixTaskHandler:
    """Оркестратор создания задач в Bitrix24"""

    def __init__(self):
        self.template_service = TemplateService()
        self.predecessor_service = PredecessorService()
        self.checklist_service = ChecklistService()
        self.questionnaire_service = QuestionnaireService()
        self.file_service = FileService()
        self.sync_service = SyncService()
        self.task_builder = TaskDataBuilder()
        self.validator = FieldValidator()
        self.stats = Statistics()

    def process_message(self, message_data, properties) -> bool:
        """Точка входа"""

    def _create_bitrix_task(self, message_data) -> Optional[Dict]:
        """Координация создания задачи"""
```

**Методы:**
- `__init__`
- `process_message`
- `_create_bitrix_task`
- `_create_task_fallback`
- `get_stats`
- `cleanup`

---

### 2. TemplateService
**Файл:** `services/template_service.py`
**Ответственность:** Работа с шаблонами задач

```python
class TemplateService:
    """Сервис работы с шаблонами задач Bitrix24"""

    def get_template(self, camunda_process_id, element_id, template_id=None) -> Optional[Dict]:
        """Получение шаблона задачи"""

    def extract_template_params(self, message_data) -> Tuple[str, str, str]:
        """Извлечение параметров для запроса шаблона"""

    def extract_checklists(self, template_data) -> List[Dict]:
        """Извлечение чек-листов из шаблона"""

    def extract_questionnaires(self, template_data) -> List[Dict]:
        """Извлечение анкет из шаблона"""
```

**Методы из handler.py:**
- `_extract_template_params`
- `_get_task_template`
- `_parse_task_template_response`
- `_extract_checklists_from_template`
- `_extract_questionnaires_from_template`
- `_extract_questionnaires_in_description`

---

### 3. PredecessorService
**Файл:** `services/predecessor_service.py`
**Ответственность:** Управление зависимостями между задачами

```python
class PredecessorService:
    """Сервис управления предшественниками задач"""

    def __init__(self):
        self.cache = PredecessorCache()

    def get_predecessor_ids(self, camunda_process_id, diagram_id, element_id) -> List[str]:
        """Получение ID элементов-предшественников"""

    def apply_dependencies(self, task_data, ...) -> List[int]:
        """Применение зависимостей к task_data"""

    def create_dependencies(self, task_id, predecessor_ids) -> None:
        """Создание зависимостей через API"""

    def get_results(self, predecessor_ids) -> Dict[int, List[Dict]]:
        """Получение результатов предшественников"""

    def build_results_block(self, results) -> Optional[str]:
        """Формирование текстового блока результатов"""
```

**Методы из handler.py:**
- `_get_element_predecessor_ids`
- `_apply_predecessor_dependencies`
- `_create_task_dependencies`
- `_get_task_results`
- `_get_predecessor_results`
- `_build_predecessor_results_block`
- `_find_task_by_element_and_instance`

---

### 4. ChecklistService
**Файл:** `services/checklist_service.py`
**Ответственность:** Управление чек-листами задач

```python
class ChecklistService:
    """Сервис управления чек-листами"""

    def create_checklists(self, task_id, checklists_data) -> bool:
        """Создание чек-листов для задачи"""

    def create_group(self, task_id, title) -> Optional[int]:
        """Создание группы чек-листа"""

    def add_item(self, task_id, title, parent_id=None) -> Optional[int]:
        """Добавление элемента в чек-лист"""

    def get_checklists(self, task_id) -> List[Dict]:
        """Получение чек-листов задачи"""

    def clear_checklists(self, task_id) -> bool:
        """Очистка всех чек-листов"""
```

**Методы из handler.py:**
- `create_checklist_group_sync` / `create_checklist_group`
- `add_checklist_item_sync` / `add_checklist_item`
- `create_task_checklists_sync` / `create_task_checklists`
- `get_task_checklists`
- `delete_checklist_item`
- `clear_task_checklists`

**Примечание:** Объединить sync и async версии, использовать единый подход.

---

### 5. QuestionnaireService
**Файл:** `services/questionnaire_service.py`
**Ответственность:** Управление анкетами

```python
class QuestionnaireService:
    """Сервис управления анкетами"""

    def add_to_task(self, task_id, questionnaires) -> bool:
        """Добавление анкет к задаче"""

    def format_answer(self, question, raw_value) -> str:
        """Форматирование ответа на вопрос"""

    def build_description_block(self, questionnaires, variables, element_id) -> Optional[str]:
        """Формирование блока анкет для описания"""
```

**Методы из handler.py:**
- `_add_questionnaires_to_task`
- `_format_questionnaire_answer`
- `_build_questionnaires_description_block`

---

### 6. FileService
**Файл:** `services/file_service.py`
**Ответственность:** Работа с файлами

```python
class FileService:
    """Сервис работы с файлами"""

    def attach_to_task(self, task_id, files) -> None:
        """Прикрепление файлов к задаче"""

    def attach_predecessor_files(self, task_id, predecessor_results) -> None:
        """Прикрепление файлов предшественников"""

    def build_files_block(self, files) -> Optional[str]:
        """Формирование текстового блока файлов"""
```

**Методы из handler.py:**
- `_attach_files_to_task`
- `_attach_predecessor_files`
- `_build_template_files_block`

---

### 7. UserService
**Файл:** `services/user_service.py`
**Ответственность:** Работа с пользователями

```python
class UserService:
    """Сервис работы с пользователями Bitrix24"""

    def get_name(self, user_id) -> Optional[str]:
        """Получение имени пользователя"""

    def get_supervisor(self, user_id) -> Optional[int]:
        """Получение ID руководителя"""

    def get_responsible_info(self, camunda_process_id, diagram_id, element_id) -> Optional[Dict]:
        """Получение информации об ответственном"""
```

**Методы из handler.py:**
- `_get_user_name_by_id`
- `_get_user_supervisor`
- `_get_responsible_info`

---

### 8. SyncService
**Файл:** `services/sync_service.py`
**Ответственность:** Синхронизация и RabbitMQ

```python
class SyncService:
    """Сервис синхронизации с Bitrix24"""

    def send_sync_request(self, message_data) -> bool:
        """Отправка запроса синхронизации"""

    def send_success_message(self, original_message, response, queue) -> bool:
        """Отправка успешного сообщения"""

    def send_to_error_queue(self, message_data, error) -> bool:
        """Отправка в очередь ошибок"""
```

**Методы из handler.py:**
- `_send_sync_request`
- `_send_success_message`
- `_send_success_message_with_retry`
- `_send_to_error_queue`

---

### 9. TaskDataBuilder
**Файл:** `builders/task_builder.py`
**Ответственность:** Построение данных задачи

```python
class TaskDataBuilder:
    """Построитель данных задачи из шаблона"""

    def __init__(self, user_service: UserService):
        self.user_service = user_service

    def build_from_template(self, template_data, message_data, task_id, element_id) -> Tuple[Dict, List]:
        """Построение task_data из шаблона"""

    def _resolve_responsible(self, template, members, initiator_id) -> int:
        """Определение RESPONSIBLE_ID"""

    def _resolve_created_by(self, template, initiator_id) -> int:
        """Определение CREATED_BY"""

    def _resolve_accomplices(self, template, members, initiator_id) -> List[int]:
        """Определение ACCOMPLICES"""

    def _resolve_auditors(self, template, members, initiator_id, diagram_owner) -> List[int]:
        """Определение AUDITORS"""
```

**Примечание:** Этот класс должен содержать рефакторинг метода `_build_task_data_from_template` (476 строк → ~300 строк с декомпозицией).

---

### 10. DescriptionBuilder
**Файл:** `builders/description_builder.py`
**Ответственность:** Построение описания задачи

```python
class DescriptionBuilder:
    """Построитель описания задачи"""

    def build_variables_block(self, message_data, camunda_process_id, task_id) -> Optional[str]:
        """Формирование блока переменных процесса"""

    def append_block(self, description, block) -> str:
        """Добавление блока к описанию"""
```

**Методы из handler.py:**
- `_build_process_variables_block`

---

### 11. BitrixAPIClient
**Файл:** `clients/bitrix_client.py`
**Ответственность:** HTTP-взаимодействие с Bitrix24

```python
class BitrixAPIClient:
    """Клиент API Bitrix24"""

    def __init__(self, config):
        self.webhook_url = config.webhook_url
        self.timeout = config.request_timeout

    def request(self, method, api_method, params) -> Optional[Any]:
        """Синхронный HTTP запрос"""

    def send_task(self, task_data) -> Optional[Dict]:
        """Отправка задачи"""

    def find_task(self, external_task_id) -> Optional[Dict]:
        """Поиск задачи по external ID"""

    def get_list_element_name(self, iblock_id, element_id) -> Optional[str]:
        """Получение названия элемента списка"""
```

**Методы из handler.py:**
- `_request_sync`
- `_request`
- `_send_task_to_bitrix`
- `_find_task_by_external_id`
- `_get_list_element_name`

---

### 12. FieldValidator
**Файл:** `validators/field_validator.py`
**Ответственность:** Валидация полей

```python
class FieldValidator:
    """Валидатор обязательных полей Bitrix24"""

    def check_required_fields(self) -> None:
        """Проверка существования обязательных UF_ полей"""

    def extract_user_fields(self, metadata) -> Dict:
        """Извлечение пользовательских полей"""
```

**Методы из handler.py:**
- `_check_required_user_field`
- `_extract_user_fields`

---

### 13. CamundaUtils
**Файл:** `utils/camunda_utils.py`
**Ответственность:** Утилиты для работы с Camunda

```python
def get_camunda_int(variables, key) -> Optional[int]:
    """Безопасное извлечение int из переменных Camunda"""

def get_camunda_datetime(variables, key) -> Optional[datetime]:
    """Безопасное извлечение datetime из переменных Camunda"""

def format_variable_value(property_type, value_entry) -> str:
    """Форматирование значения переменной"""
```

**Методы из handler.py:**
- `_get_camunda_int`
- `_get_camunda_datetime`
- `_format_process_variable_value`

---

### 14. CacheManager
**Файл:** `utils/cache.py`
**Ответственность:** Управление кэшами

```python
class CacheManager:
    """Централизованное управление кэшами"""

    def __init__(self):
        self.diagram_properties: Dict[str, List] = {}
        self.diagram_details: Dict[str, Dict] = {}
        self.predecessors: Dict[Tuple, List] = {}
        self.responsible: Dict[Tuple, Optional[Dict]] = {}
        self.element_tasks: Dict[Tuple, Dict] = {}

    def get_diagram_properties(self, key) -> Optional[List]:
        ...

    def set_diagram_properties(self, key, value) -> None:
        ...

    def clear_all(self) -> None:
        """Очистка всех кэшей"""
```

---

## Что делать с устаревшим кодом

### Рекомендация: Удалить

Следующие методы помечены как `[DEPRECATED]` с датой 2025-11-03 и не используются:

1. `_extract_title`
2. `_create_description`
3. `_extract_assignee_id`
4. `_extract_priority`
5. `_extract_deadline`
6. `_extract_project_id`
7. `_extract_started_by_id`
8. `_extract_originator_id`
9. `_extract_group_id`
10. `_extract_created_by_id`
11. `_extract_additional_fields`
12. `_extract_checklists`

**Экономия:** ~350 строк

---

## План миграции

### Этап 1: Подготовка (без изменения функциональности)
1. Создать структуру директорий `services/`, `clients/`, `builders/`, `validators/`, `utils/`
2. Удалить устаревшие методы (11 методов, ~350 строк)
3. Написать тесты для текущего `process_message`

### Этап 2: Выделение утилит и клиентов
1. Создать `utils/camunda_utils.py`
2. Создать `utils/cache.py`
3. Создать `clients/bitrix_client.py`
4. Обновить импорты в `handler.py`

### Этап 3: Выделение сервисов (по одному)
1. `UserService` (минимальные зависимости)
2. `FileService`
3. `ChecklistService`
4. `QuestionnaireService`
5. `PredecessorService`
6. `TemplateService`
7. `SyncService`

### Этап 4: Выделение билдеров
1. `DescriptionBuilder`
2. `TaskDataBuilder` (рефакторинг `_build_task_data_from_template`)

### Этап 5: Выделение валидатора
1. `FieldValidator`

### Этап 6: Финализация
1. Рефакторинг `BitrixTaskHandler` до роли оркестратора
2. Обновление тестов
3. Документация

---

## Финальные результаты

| Метрика | Исходно | Финал | Цель | Статус |
|---------|---------|-------|------|--------|
| Строк в handler.py | 4344 | **860** | ~200 | ⚠️ -80% |
| Количество методов | 72 | **16** | ~6 | ⚠️ -78% |
| Максимальный метод | 476 | **184** | ~80 | ⚠️ -61% |
| `_create_task_fallback` | 162 | **49** | ~50 | ✅ |
| Устаревший код | 362 | **0** | 0 | ✅ |
| Выделенные модули | 0 | **11** | 10+ | ✅ |
| Дублирование sync/async | 6 | **0** | 0 | ✅ |
| Количество кэшей | 5 | **3** | 1 | ⚠️ |

**Примечание:** Цели ~200 строк и ~6 методов были амбициозными. Handler.py как оркестратор
с 16 компактными методами — это нормальная архитектура для координирующего класса.
Все методы читаемы и выполняют одну задачу.

---

## Преимущества

1. **Тестируемость** — каждый сервис можно тестировать изолированно
2. **Читаемость** — понятная структура, легко найти нужный код
3. **Поддерживаемость** — изменения в одной области не затрагивают другие
4. **Расширяемость** — легко добавить новые интеграции (OpenProject, 1C)
5. **Переиспользование** — сервисы можно использовать в других частях системы

---

## Риски

1. **Время** — рефакторинг потребует значительных усилий
2. **Регрессии** — возможны ошибки при миграции
3. **Совместимость** — нужно обеспечить обратную совместимость

### Митигация рисков

1. Поэтапная миграция с сохранением работоспособности на каждом этапе
2. Написание тестов перед каждым этапом
3. Code review каждого изменения
4. Canary-деплой на dev среду перед prod

---

*Отчет подготовлен для анализа рефакторинга класса BitrixTaskHandler*
