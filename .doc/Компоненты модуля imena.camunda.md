# Компоненты модуля imena.camunda - Полная документация

## Обзор

Каталог `imena.camunda` содержит набор компонентов для работы с данными Camunda BPM Engine в Bitrix24. Все компоненты построены на архитектуре D7 и следуют принципам модуля `imena.sample`.

**Версия:** 1.0  
**Автор:** vlikhobabin@gmail.com  
**Модуль:** imena.camunda  
**Совместимость:** Bitrix24 20.0.0+, PHP 7.4+

---

## Структура каталога

```
imena.camunda/
├── camunda.processinstance.list/          # Список экземпляров процессов
├── camunda.processinstance.details/      # Детали экземпляра процесса
├── camunda.processdefinition.list/       # Список определений процессов
├── camunda.processdefinition.details/     # Детали определения процесса
├── camunda.processdefinition.startform/   # Стартовая форма процесса
├── camunda.externaltask.list/            # Список внешних задач
├── camunda.externaltask.details/         # Детали внешней задачи
├── camunda.processvariable.list/         # Список переменных процессов
└── .cursorrules                          # Правила разработки
```

---

## Компоненты

### 1. camunda.processinstance.list

**Назначение:** Компонент для отображения списка экземпляров процессов Camunda с Grid интерфейсом, фильтрацией и массовыми операциями.

**Класс:** `CamundaProcessListComponent`

**Основные возможности:**
- Grid отображение с 16 колонками процессов
- Расширенная фильтрация (8 полей, 6 пресетов)
- Контекстные действия (suspend, resume, terminate, delete)
- Массовые операции для групп процессов
- Экспорт в Excel/CSV
- AJAX обновление без перезагрузки
- Интеграция с SidePanel для деталей

**AJAX действия:**
- `suspendAction(string $processId)` - приостановка процесса
- `resumeAction(string $processId)` - возобновление процесса
- `deleteAction(string $processId, string $reason)` - удаление процесса
- `syncWithCamundaAction()` - полная синхронизация с Camunda
- `exportAction(array $params)` - экспорт данных
- `reloadAction()` - перезагрузка данных Grid

**Параметры компонента:**
- `GRID_ID` - идентификатор Grid (по умолчанию: `CAMUNDA_PROCESS_LIST`)
- `FILTER_ID` - идентификатор фильтра (по умолчанию: `CAMUNDA_PROCESS_FILTER`)
- `PAGE_SIZE` - размер страницы (по умолчанию: 25)
- `PROCESS_DEFINITION_KEY` - фильтр по ключу процесса
- `STATUS` - фильтр по статусу процесса
- `PATH_TO_DETAIL` - путь к детальной странице
- `SHOW_FILTER` - показывать фильтр (Y/N)
- `SHOW_ACTION_PANEL` - показывать панель действий (Y/N)
- `ALLOW_EXPORT` - разрешить экспорт (Y/N)

**Интеграция:**
- Использует `ProcessTable` (ORM) для загрузки данных
- Интегрируется с `CamundaGrid` для отображения
- Использует `CamundaFilter` для фильтрации
- Проверяет права через `CamundaAccessController`
- Выполняет команды через `CamundaProcessController`

**Пример использования:**
```php
$APPLICATION->IncludeComponent(
    'imena.camunda:camunda.processinstance.list',
    '',
    [
        'GRID_ID' => 'CAMUNDA_PROCESS_LIST',
        'FILTER_ID' => 'CAMUNDA_PROCESS_FILTER',
        'PAGE_SIZE' => 25,
        'PATH_TO_DETAIL' => '/local/pages/camunda/process/detail.php?ID=#ID#',
        'SHOW_FILTER' => 'Y',
        'SHOW_ACTION_PANEL' => 'Y',
    ]
);
```

**Особенности:**
- Поддержка предустановленных фильтров по `PROCESS_DEFINITION_KEY` и `STATUS`
- Автоматическая точечная синхронизация после действий (suspend/resume/delete)
- Ленивая загрузка данных с пагинацией
- Интеграция с `FullSyncService` для синхронизации

---

### 2. camunda.processinstance.details

**Назначение:** Компонент для детального просмотра и редактирования экземпляра процесса Camunda через Entity Editor.

**Класс:** `CamundaProcessDetailComponent`

**Основные возможности:**
- Просмотр детальной информации о процессе
- Редактирование через Entity Editor (режим read-only по умолчанию)
- Создание новых процессов (ID=0)
- AJAX сохранение с валидацией
- SidePanel интеграция
- Полная локализация

**AJAX действия:**
- `saveAction(array $fields)` - сохранение процесса
- `loadDataAction(int $processId)` - загрузка данных процесса

**Параметры компонента:**
- `PROCESS_ID` - ID процесса для редактирования (0 = новый)
- `PATH_TO_LIST` - URL для возврата к списку
- `SHOW_TITLE` - показывать заголовок страницы (Y/N)
- `EDITOR_CONFIG_ID` - ID конфигурации Entity Editor
- `USE_SIDEPANEL` - использовать SidePanel (Y/N)
- `SIDEPANEL_WIDTH` - ширина SidePanel (по умолчанию: 900)
- `AUTO_CLOSE_ON_SAVE` - автоматически закрывать после сохранения (Y/N)
- `CHECK_PERMISSIONS` - проверять права доступа (Y/N)

**Интеграция:**
- Использует `ProcessTable` для загрузки/сохранения данных
- Использует `ProcessProvider` для конфигурации Entity Editor
- Проверяет права через `CamundaAccessController`
- Выполняет команды через `CommandBus` (CreateProcessCommand, UpdateProcessCommand)

**Пример использования:**
```php
$APPLICATION->IncludeComponent(
    'imena.camunda:camunda.processinstance.details',
    '',
    [
        'PROCESS_ID' => $_REQUEST['ID'] ?? '0',
        'PATH_TO_LIST' => '/local/pages/camunda/process/',
        'USE_SIDEPANEL' => 'Y',
        'AUTO_CLOSE_ON_SAVE' => 'Y',
    ]
);
```

**Особенности:**
- Режим read-only для существующих процессов (управление через Camunda API)
- Поддержка создания новых процессов
- Валидация полей перед сохранением
- Интеграция с Command Layer для безопасности

---

### 3. camunda.processdefinition.list

**Назначение:** Компонент для отображения списка определений процессов Camunda с возможностью управления (suspend, activate, delete, start).

**Класс:** `CamundaProcessDefinitionListComponent`

**Основные возможности:**
- Grid отображение определений процессов
- Фильтрация и поиск
- Управление определениями (suspend, activate, delete)
- Запуск новых экземпляров процессов
- Синхронизация с Camunda
- Экспорт данных
- Отображение только последних версий процессов

**AJAX действия:**
- `suspendAction(string $definitionId, bool $includeInstances)` - приостановка определения
- `activateAction(string $definitionId, bool $includeInstances)` - активация определения
- `deleteAction(string $definitionId, bool $cascade)` - удаление определения
- `syncWithCamundaAction()` - полная синхронизация определений
- `syncDefinitionAction(string $definitionId)` - точечная синхронизация определения
- `syncAction(array $ID)` - групповая синхронизация
- `deleteGroupAction(array $ID, bool $cascade)` - групповое удаление
- `startProcessInstanceAction(string $definitionId, string $businessKey)` - запуск процесса
- `exportAction(array $params)` - экспорт данных

**Параметры компонента:**
- `GRID_ID` - идентификатор Grid (по умолчанию: `CAMUNDA_DEFINITION_LIST`)
- `FILTER_ID` - идентификатор фильтра (по умолчанию: `CAMUNDA_DEFINITION_FILTER`)
- `PAGE_SIZE` - размер страницы (по умолчанию: 25)
- `PATH_TO_DETAIL` - путь к детальной странице определения
- `SHOW_ROW_ACTIONS` - показывать действия строк (Y/N)
- `ENABLE_LIVE_SEARCH` - включить живой поиск (Y/N)

**Интеграция:**
- Использует `ProcessDefinitionTable` для загрузки данных
- Использует `getLatestVersions()` для отображения только последних версий
- Интегрируется с `CamundaGrid` и `CamundaFilter`
- Использует `FullSyncService` для синхронизации

**Пример использования:**
```php
$APPLICATION->IncludeComponent(
    'imena.camunda:camunda.processdefinition.list',
    '',
    [
        'GRID_ID' => 'CAMUNDA_DEFINITION_LIST',
        'FILTER_ID' => 'CAMUNDA_DEFINITION_FILTER',
        'PAGE_SIZE' => 25,
        'PATH_TO_DETAIL' => '/local/pages/camunda/definition/detail.php?ID=#ID#',
    ]
);
```

**Особенности:**
- Отображает только последние версии процессов (latestVersion=true)
- Поддержка каскадного удаления с экземплярами
- Автоматическое добавление переменной `startedBy` при запуске процесса
- Сохранение запущенных экземпляров в локальную БД

---

### 4. camunda.processdefinition.details

**Назначение:** Компонент для детального просмотра определения процесса Camunda через Entity Editor.

**Класс:** `CamundaProcessDefinitionDetailsComponent`

**Основные возможности:**
- Просмотр детальной информации об определении процесса
- Read-only режим (определения управляются через Camunda API)
- Интеграция с Entity Editor
- SidePanel поддержка

**AJAX действия:**
- Нет (компонент только для просмотра)

**Параметры компонента:**
- `DEFINITION_ID` - ID определения процесса
- `PATH_TO_LIST` - URL для возврата к списку
- `SHOW_TITLE` - показывать заголовок страницы (Y/N)
- `EDITOR_CONFIG_ID` - ID конфигурации Entity Editor
- `CACHE_TYPE` - тип кеширования
- `CACHE_TIME` - время кеширования

**Интеграция:**
- Использует `ProcessDefinitionTable` для загрузки данных
- Использует `ProcessDefinitionProvider` для конфигурации Entity Editor

**Пример использования:**
```php
$APPLICATION->IncludeComponent(
    'imena.camunda:camunda.processdefinition.details',
    '',
    [
        'DEFINITION_ID' => $_REQUEST['ID'] ?? '',
        'PATH_TO_LIST' => '/local/pages/camunda/definition/',
    ]
);
```

**Особенности:**
- Только просмотр (read-only режим)
- Автоматическое форматирование дат и булевых полей
- Интеграция с SidePanel

---

### 5. camunda.processdefinition.startform

**Назначение:** Компонент для отображения стартовой формы процесса с динамическими полями на основе свойств из Storm диаграммы.

**Класс:** `CamundaProcessDefinitionStartFormComponent`

**Основные возможности:**
- Динамическое построение формы на основе свойств процесса
- Валидация входных данных
- Запуск процесса в Camunda
- Сохранение экземпляра в локальную БД
- Интеграция с модулем `imena.storm` для получения свойств

**AJAX действия:**
- `startProcessAction()` - запуск процесса с параметрами

**Параметры компонента:**
- `PROCESS_KEY` - ключ процесса для запуска (обязательный)

**Интеграция:**
- Использует `PropertyResolver` для получения свойств процесса
- Использует `ProcessDefinitionClient` для запуска процесса
- Сохраняет экземпляр через `ProcessTable::add()`
- Интегрируется с модулем `imena.storm` для получения диаграмм

**Пример использования:**
```php
$APPLICATION->IncludeComponent(
    'imena.camunda:camunda.processdefinition.startform',
    '',
    [
        'PROCESS_KEY' => $_REQUEST['KEY'] ?? '',
    ]
);
```

**Алгоритм работы:**
1. Получение контекста процесса через `PropertyResolver::getProcessContext()`
2. Построение формы на основе свойств из Storm диаграммы
3. Валидация входных данных через `PropertyResolver::buildVariables()`
4. Запуск процесса через `ProcessDefinitionClient::startInstanceByKey()`
5. Сохранение экземпляра в локальную БД

**Особенности:**
- Динамические поля на основе свойств Storm диаграммы
- Автоматическое добавление переменной `startedBy` (ID пользователя Bitrix24)
- Обработка ошибок подключения к Camunda
- Логирование ошибок в файл

---

### 6. camunda.externaltask.list

**Назначение:** Компонент для отображения списка внешних задач Camunda (External Task Worker API) с возможностью управления.

**Класс:** `CamundaExternalTaskListComponent`

**Основные возможности:**
- Grid отображение внешних задач (10 колонок)
- Фильтрация по 12 полям
- 4 пресета фильтрации (Available, Locked, WithErrors, HighPriority)
- Действия над задачами (complete, unlock, view)
- Синхронизация с Camunda
- Экспорт данных
- Поддержка фильтрации по экземпляру процесса

**AJAX действия:**
- `completeAction(string $taskId, string $workerId, array $variables, ?array $localVariables)` - завершение задачи
- `unlockAction(string $taskId, string $reason)` - разблокировка задачи
- `syncWithCamundaAction()` - полная синхронизация задач
- `exportAction(string $type)` - экспорт данных

**Параметры компонента:**
- `GRID_ID` - идентификатор Grid (по умолчанию: `CAMUNDA_EXTERNALTASK_LIST`)
- `FILTER_ID` - идентификатор фильтра (по умолчанию: `CAMUNDA_EXTERNALTASK_FILTER`)
- `PAGE_SIZE` - размер страницы (по умолчанию: 25)
- `PROCESS_INSTANCE_ID` - фильтр по экземпляру процесса
- `PATH_TO_DETAIL` - путь к детальной странице задачи
- `SHOW_FILTER` - показывать фильтр (Y/N)
- `SHOW_ACTION_PANEL` - показывать панель действий (Y/N)

**Интеграция:**
- Использует `ExternalTaskTable` для загрузки данных
- Использует `ExternalTaskClient` для работы с Camunda API
- Использует `CompleteTaskCommand` и `UnlockTaskCommand` для действий
- Интегрируется с `CamundaGrid` и `CamundaFilter`

**Пример использования:**
```php
$APPLICATION->IncludeComponent(
    'imena.camunda:camunda.externaltask.list',
    '',
    [
        'GRID_ID' => 'CAMUNDA_EXTERNALTASK_LIST',
        'FILTER_ID' => 'CAMUNDA_EXTERNALTASK_FILTER',
        'PAGE_SIZE' => 25,
        'PROCESS_INSTANCE_ID' => $_REQUEST['PROCESS_INSTANCE_ID'] ?? '',
        'PATH_TO_DETAIL' => '/local/pages/camunda/task/detail.php?ID=#ID#',
    ]
);
```

**Особенности:**
- Поддержка предустановленного фильтра по `PROCESS_INSTANCE_ID`
- Полная замена данных при синхронизации (очистка таблицы)
- Использование Command Layer для завершения задач
- Автоматическая точечная синхронизация после завершения задачи

---

### 7. camunda.externaltask.details

**Назначение:** Компонент для детального просмотра внешней задачи Camunda через Entity Editor.

**Класс:** `CamundaExternalTaskDetailsComponent`

**Основные возможности:**
- Просмотр детальной информации о внешней задаче
- Read-only режим (задачи управляются через Camunda API)
- Интеграция с Entity Editor
- SidePanel поддержка

**AJAX действия:**
- Нет (компонент только для просмотра)

**Параметры компонента:**
- `TASK_ID` - ID внешней задачи
- `PATH_TO_LIST` - URL для возврата к списку
- `SHOW_TITLE` - показывать заголовок страницы (Y/N)
- `EDITOR_CONFIG_ID` - ID конфигурации Entity Editor
- `CACHE_TYPE` - тип кеширования
- `CACHE_TIME` - время кеширования

**Интеграция:**
- Использует `ExternalTaskTable` для загрузки данных
- Использует `ExternalTaskProvider` для конфигурации Entity Editor

**Пример использования:**
```php
$APPLICATION->IncludeComponent(
    'imena.camunda:camunda.externaltask.details',
    '',
    [
        'TASK_ID' => $_REQUEST['ID'] ?? '',
        'PATH_TO_LIST' => '/local/pages/camunda/task/',
    ]
);
```

**Особенности:**
- Только просмотр (read-only режим)
- Автоматическое форматирование дат и булевых полей
- Интеграция с SidePanel

---

### 8. camunda.processvariable.list

**Назначение:** Компонент для отображения списка переменных процессов Camunda с Grid интерфейсом и фильтрацией.

**Класс:** `CamundaProcessVariableListComponent`

**Основные возможности:**
- Grid отображение переменных процессов
- Фильтрация по процессу, определению, коду, типу, статусу синхронизации
- 2 пресета фильтрации (Recent Sync, With Errors)
- Сортировка и пагинация
- Интеграция с `ProcessVariableDataProvider`

**AJAX действия:**
- `reloadAction()` - перезагрузка данных Grid

**Параметры компонента:**
- `GRID_ID` - идентификатор Grid (по умолчанию: `CAMUNDA_PROCESS_VARIABLE_LIST`)
- `FILTER_ID` - идентификатор фильтра (по умолчанию: `CAMUNDA_PROCESS_VARIABLE_FILTER`)
- `PAGE_SIZE` - размер страницы (по умолчанию: 25)
- `PROCESS_INSTANCE_ID` - фильтр по экземпляру процесса
- `PROCESS_DEFINITION_KEY` - фильтр по ключу определения процесса
- `SHOW_FILTER` - показывать фильтр (Y/N)
- `SHOW_ACTION_PANEL` - показывать панель действий (Y/N)

**Интеграция:**
- Использует `ProcessVariableDataProvider` для загрузки данных
- Интегрируется с системой Grid и Filter Bitrix24

**Пример использования:**
```php
$APPLICATION->IncludeComponent(
    'imena.camunda:camunda.processvariable.list',
    '',
    [
        'GRID_ID' => 'CAMUNDA_PROCESS_VARIABLE_LIST',
        'FILTER_ID' => 'CAMUNDA_PROCESS_VARIABLE_FILTER',
        'PAGE_SIZE' => 25,
        'PROCESS_INSTANCE_ID' => $_REQUEST['PROCESS_INSTANCE_ID'] ?? '',
    ]
);
```

**Колонки Grid:**
- `CODE` - код переменной
- `NAME` - название переменной
- `VALUE` - значение переменной
- `TYPE` - тип переменной (string, integer, boolean, date, enum)
- `PROCESS_INSTANCE_ID` - ID экземпляра процесса
- `PROCESS_DEFINITION_KEY` - ключ определения процесса
- `SYNC_STATUS` - статус синхронизации
- `LAST_SYNC_DATE` - дата последней синхронизации

**Особенности:**
- Поддержка фильтрации по типу переменной
- Отображение статуса синхронизации
- Интеграция с системой переменных процессов

---

## Общие архитектурные принципы

### 1. Структура компонентов

Все компоненты следуют единой архитектуре:

```php
class ComponentName extends CBitrixComponent implements Controllerable, Errorable
{
    // Инициализация
    public function __construct($component = null)
    
    // Подготовка параметров
    public function onPrepareComponentParams($arParams): array
    
    // Выполнение компонента
    public function executeComponent(): void
    
    // AJAX действия
    public function configureActions(): array
    public function actionNameAction(...): array|AjaxJson
}
```

### 2. Интеграция с модулем

Все компоненты используют классы модуля `imena.camunda`:

- **ORM таблицы:** `ProcessTable`, `ProcessDefinitionTable`, `ExternalTaskTable`
- **Grid системы:** `CamundaGrid` для каждого типа сущности
- **Filter системы:** `CamundaFilter` для каждого типа сущности
- **Access Control:** `CamundaAccessController` для проверки прав
- **Command Layer:** Команды для безопасных операций
- **Sync Services:** `FullSyncService` для синхронизации

### 3. Безопасность

Все компоненты реализуют многоуровневую защиту:

1. **Prefilters в configureActions():**
   - `ActionFilter\Authentication` - проверка авторизации
   - `ActionFilter\Csrf` - защита от CSRF атак
   - `ActionFilter\HttpMethod` - ограничение методов HTTP

2. **Access Control:**
   - Проверка прав через `CamundaAccessController`
   - Использование `CamundaActionDictionary` для действий

3. **Command Layer:**
   - Все операции выполняются через команды
   - Валидация перед выполнением
   - Логирование всех операций

### 4. Обработка ошибок

Все компоненты используют `ErrorCollection` для обработки ошибок:

```php
protected $errorCollection;

public function getErrors(): array
{
    return $this->errorCollection->toArray();
}
```

### 5. Локализация

Все текстовые элементы локализованы через `Loc::getMessage()`:

```php
Loc::loadMessages(__FILE__);
$message = Loc::getMessage('CAMUNDA_MESSAGE_KEY');
```

---

## Интеграция компонентов

### Связи между компонентами

```
camunda.processdefinition.list
    ├── → camunda.processdefinition.details (просмотр определения)
    ├── → camunda.processdefinition.startform (запуск процесса)
    └── → camunda.processinstance.list (список экземпляров)

camunda.processinstance.list
    ├── → camunda.processinstance.details (просмотр экземпляра)
    └── → camunda.externaltask.list (задачи экземпляра)

camunda.processinstance.details
    ├── → camunda.externaltask.list (задачи процесса)
    └── → camunda.processvariable.list (переменные процесса)

camunda.externaltask.list
    └── → camunda.externaltask.details (просмотр задачи)
```

### Примеры интеграции

**1. Список процессов с деталями:**
```php
// Список
$APPLICATION->IncludeComponent(
    'imena.camunda:camunda.processinstance.list',
    '',
    [
        'PATH_TO_DETAIL' => '/local/pages/camunda/process/detail.php?ID=#ID#',
    ]
);

// Детали (открываются в SidePanel)
$APPLICATION->IncludeComponent(
    'imena.camunda:camunda.processinstance.details',
    '',
    [
        'PROCESS_ID' => $_REQUEST['ID'] ?? '0',
    ]
);
```

**2. Список определений с запуском:**
```php
// Список определений
$APPLICATION->IncludeComponent(
    'imena.camunda:camunda.processdefinition.list',
    '',
    []
);

// Стартовая форма (открывается при клике на "Start")
$APPLICATION->IncludeComponent(
    'imena.camunda:camunda.processdefinition.startform',
    '',
    [
        'PROCESS_KEY' => $_REQUEST['KEY'] ?? '',
    ]
);
```

**3. Детали процесса с задачами:**
```php
// Детали процесса
$APPLICATION->IncludeComponent(
    'imena.camunda:camunda.processinstance.details',
    '',
    [
        'PROCESS_ID' => $_REQUEST['ID'] ?? '',
    ]
);

// Задачи процесса (встроены в детали)
$APPLICATION->IncludeComponent(
    'imena.camunda:camunda.externaltask.list',
    '',
    [
        'PROCESS_INSTANCE_ID' => $_REQUEST['ID'] ?? '',
    ]
);
```

---

## Параметры компонентов

### Общие параметры

Все компоненты поддерживают следующие общие параметры:

| Параметр | Тип | Описание |
|----------|-----|----------|
| `GRID_ID` | string | Идентификатор Grid для настроек |
| `FILTER_ID` | string | Идентификатор фильтра для сохранения состояния |
| `PAGE_SIZE` | int | Размер страницы (10, 25, 50, 100) |
| `PATH_TO_DETAIL` | string | Шаблон URL для детальной страницы |
| `LIST_URL` | string | URL списка для возврата |
| `SHOW_FILTER` | Y/N | Показывать фильтр |
| `SHOW_ACTION_PANEL` | Y/N | Показывать панель действий |
| `CACHE_TYPE` | A/Y/N | Тип кеширования |
| `CACHE_TIME` | int | Время кеширования в секундах |

### Специфичные параметры

**camunda.processinstance.list:**
- `PROCESS_DEFINITION_KEY` - фильтр по ключу процесса
- `STATUS` - фильтр по статусу процесса
- `PROCESS_DEFINITION_ID` - фильтр по ID определения (legacy)

**camunda.externaltask.list:**
- `PROCESS_INSTANCE_ID` - фильтр по экземпляру процесса
- `IS_IFRAME_MODE` - режим iframe
- `IFRAME_TYPE` - тип iframe

**camunda.processvariable.list:**
- `PROCESS_INSTANCE_ID` - фильтр по экземпляру процесса
- `PROCESS_DEFINITION_KEY` - фильтр по ключу определения

---

## AJAX API

### Общие принципы

Все AJAX действия используют стандартную архитектуру Bitrix24 D7:

```php
public function configureActions(): array
{
    return [
        'actionName' => [
            'prefilters' => [
                new ActionFilter\Authentication(),
                new ActionFilter\Csrf(),
            ],
        ],
    ];
}

public function actionNameAction(...): array|AjaxJson
{
    // Логика действия
    return AjaxJson::createSuccess($data);
}
```

### Вызов из JavaScript

```javascript
// Стандартный способ
BX.ajax.runComponentAction(
    'imena.camunda:camunda.processinstance.list',
    'suspend',
    {
        mode: 'class',
        data: { processId: 'process_123' }
    }
).then(function(response) {
    if (response.data.success) {
        // Успешное выполнение
    } else {
        // Обработка ошибок
        console.error(response.data.errors);
    }
});
```

---

## Интеграция с Sync Services

Все компоненты интегрируются с сервисами синхронизации модуля:

### FullSyncService

Используется для полной синхронизации данных:

```php
$fullSync = new \ImenaCamunda\Sync\Service\FullSyncService();

// Синхронизация всех определений
$result = $fullSync->syncAllDefinitions();

// Точечная синхронизация по определению
$result = $fullSync->syncByDefinition($definitionId);
```

### Точечная синхронизация

После действий над процессами выполняется автоматическая синхронизация:

```php
// После suspend/resume/delete
$fullSync = new \ImenaCamunda\Sync\Service\FullSyncService();
$syncResult = $fullSync->syncByDefinition($definitionId);
```

---

## Локализация

Все компоненты поддерживают полную локализацию на русском языке.

**Структура языковых файлов:**
```
lang/ru/
├── class.php              # Языковые константы класса
├── .parameters.php        # Языковые константы параметров
└── .description.php       # Языковые константы описания
```

**Примеры констант:**
- `CAMUNDA_PROCESS_LIST_*` - для списка процессов
- `CAMUNDA_PROCESS_DETAIL_*` - для деталей процесса
- `CAMUNDA_DEFINITION_*` - для определений процессов
- `CAMUNDA_EXTERNALTASK_*` - для внешних задач

---

## Производительность

### Оптимизации

1. **Ленивая загрузка данных:**
   - Использование `setRawRowsWithLazyLoadPagination()`
   - Калькулятор общего количества записей

2. **Кеширование:**
   - Настройки Grid и Filter кешируются
   - Результаты ORM запросов кешируются

3. **Пагинация:**
   - Серверная пагинация для больших объемов данных
   - Настраиваемый размер страницы

4. **Оптимизация запросов:**
   - Использование `select` для выбора только нужных полей
   - Индексы БД для фильтрации и сортировки

---

## Безопасность

### Многоуровневая защита

1. **Аутентификация:**
   - Все AJAX действия требуют авторизации
   - Проверка через `ActionFilter\Authentication`

2. **CSRF защита:**
   - Все POST/PUT/DELETE действия защищены CSRF токенами
   - Проверка через `ActionFilter\Csrf`

3. **Права доступа:**
   - Проверка через `CamundaAccessController`
   - Использование `CamundaActionDictionary` для действий

4. **Валидация данных:**
   - Валидация входных параметров
   - Проверка типов данных
   - Санитизация пользовательского ввода

---

## Обработка ошибок

### Стандартизированная обработка

Все компоненты используют `ErrorCollection`:

```php
protected $errorCollection;

// Добавление ошибки
$this->errorCollection->setError(new Error($message, $code));

// Получение ошибок
$errors = $this->errorCollection->toArray();
```

### Логирование

Все операции логируются с префиксом `CAMUNDA_DEBUG:`:

```php
error_log("CAMUNDA DEBUG: Operation: " . $operation);
error_log("CAMUNDA ERROR: " . $e->getMessage());
```

---

## Примеры использования

### 1. Полная страница списка процессов

```php
<?php
require($_SERVER["DOCUMENT_ROOT"]."/bitrix/header.php");

$APPLICATION->SetTitle("Процессы Camunda");

$APPLICATION->IncludeComponent(
    'imena.camunda:camunda.processinstance.list',
    '',
    [
        'GRID_ID' => 'CAMUNDA_PROCESS_LIST',
        'FILTER_ID' => 'CAMUNDA_PROCESS_FILTER',
        'PAGE_SIZE' => 25,
        'PATH_TO_DETAIL' => '/local/pages/camunda/process/detail.php?ID=#ID#',
        'SHOW_FILTER' => 'Y',
        'SHOW_ACTION_PANEL' => 'Y',
    ]
);

require($_SERVER["DOCUMENT_ROOT"]."/bitrix/footer.php");
?>
```

### 2. Детальная страница в SidePanel

```php
<?php
require($_SERVER["DOCUMENT_ROOT"]."/bitrix/header.php");

$APPLICATION->IncludeComponent(
    'bitrix:ui.sidepanel.wrapper',
    '',
    [
        'POPUP_COMPONENT_NAME' => 'imena.camunda:camunda.processinstance.details',
        'POPUP_COMPONENT_PARAMS' => [
            'PROCESS_ID' => $_REQUEST['ID'] ?? '0',
            'PATH_TO_LIST' => '/local/pages/camunda/process/',
        ],
        'USE_UI_TOOLBAR' => 'Y',
        'POPUP_COMPONENT_USE_BITRIX24_THEME' => 'Y',
    ]
);

require($_SERVER["DOCUMENT_ROOT"]."/bitrix/footer.php");
?>
```

### 3. Список задач процесса

```php
<?php
$APPLICATION->IncludeComponent(
    'imena.camunda:camunda.externaltask.list',
    '',
    [
        'PROCESS_INSTANCE_ID' => $_REQUEST['PROCESS_INSTANCE_ID'] ?? '',
        'PATH_TO_DETAIL' => '/local/pages/camunda/task/detail.php?ID=#ID#',
        'SHOW_FILTER' => 'Y',
    ]
);
?>
```

---

## Расширение компонентов

### Добавление нового действия

1. **Добавить в configureActions():**
```php
public function configureActions(): array
{
    return [
        'newAction' => [
            'prefilters' => [
                new ActionFilter\Authentication(),
                new ActionFilter\Csrf(),
            ],
        ],
    ];
}
```

2. **Реализовать метод действия:**
```php
public function newActionAction(string $param): array
{
    try {
        // Логика действия
        return [
            'success' => true,
            'message' => 'Действие выполнено',
        ];
    } catch (\Exception $e) {
        $this->errorCollection->setError(new Error($e->getMessage()));
        return [];
    }
}
```

### Добавление нового поля в Grid

1. **Обновить Grid Column Provider:**
```php
// В соответствующем Grid классе
$result[] = $this->createColumn('NEW_FIELD')
    ->setName('Новое поле')
    ->setDefault(true)
    ->setSort('NEW_FIELD');
```

2. **Добавить локализацию:**
```php
// В lang/ru/class.php
Loc::getMessage('CAMUNDA_COLUMN_NEW_FIELD') ?: 'Новое поле';
```

---

## Тестирование

### Рекомендации по тестированию

1. **Unit-тесты:**
   - Тестирование методов компонентов
   - Тестирование валидации параметров
   - Тестирование обработки ошибок

2. **Integration-тесты:**
   - Тестирование интеграции с Grid/Filter
   - Тестирование AJAX действий
   - Тестирование синхронизации

3. **Functional-тесты:**
   - Тестирование пользовательских сценариев
   - Тестирование работы в SidePanel
   - Тестирование экспорта данных

---

## Совместимость

### Требования

- **Bitrix24:** 20.0.0+
- **PHP:** 7.4+
- **MySQL:** 5.7+

### Зависимости

- Модуль `imena.camunda` - основной модуль
- Модуль `imena.storm` - для стартовой формы (опционально)
- Модуль `main` - базовые компоненты Bitrix24
- Модуль `ui` - UI компоненты Bitrix24

---

## Поддержка

Для получения поддержки или сообщения об ошибках обращайтесь к разработчику: **vlikhobabin@gmail.com**

---

## Дополнительная документация

- [Модуль imena.camunda](../../modules/imena.camunda/README.md)
- [Sync Services](../../modules/imena.camunda/lib/Sync/README.md)
- [Rest API](../../modules/imena.camunda/lib/Rest/README.md)
- [ProcessInstance](../../modules/imena.camunda/lib/ProcessInstance/README.md)
- [ExternalTask](../../modules/imena.camunda/lib/ExternalTask/README.md)

---

**Автор:** vlikhobabin@gmail.com  
**Версия:** 1.0  
**Дата:** 2024

