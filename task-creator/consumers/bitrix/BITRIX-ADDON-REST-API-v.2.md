# Руководство по добавлению REST API методов в кастомный модуль Bitrix24

## 📋 Оглавление
1. [Введение](#введение)
2. [Архитектура REST API в Bitrix24](#архитектура-rest-api-в-bitrix24)
3. [Пошаговая инструкция](#пошаговая-инструкция)
4. [Справочник API методов](#справочник-api-методов)
   - [SyncHandler - Синхронизация процессов](#synchandler---синхронизация-процессов)
   - [DiagramPropertiesHandler - Параметры диаграмм](#diagrampropertieshandler---параметры-диаграмм)
   - [DiagramResponsibleHandler - Ответственные за диаграммы](#diagramresponsiblehandler---ответственные-за-диаграммы)
   - [UserFieldsHandler - Пользовательские поля задач](#userfieldshandler---пользовательские-поля-задач)
   - [UserSupervisorHandler - Руководители пользователей](#usersupervisorhandler---руководители-пользователей)
   - [TaskTemplateHandler - Шаблоны задач](#tasktemplatehandler---шаблоны-задач)
   - [TaskQuestionnaireHandler - Анкеты задач](#taskquestionnairehandler---анкеты-задач)
   - [TaskDependencyHandler - Зависимости задач](#taskdependencyhandler---зависимости-задач)
5. [Примеры использования](#примеры-использования)
6. [Тестирование](#тестирование)
7. [Решение проблем](#решение-проблем)

---

## Введение

Это руководство описывает, как добавить собственные REST API методы в кастомный модуль Bitrix24, которые можно вызывать через входящие вебхуки.

### Зачем это нужно?

- ✅ Интеграция с внешними системами (например, Camunda, 1C, другие сервисы)
- ✅ Создание webhook-endpoints для приема данных от внешних систем
- ✅ Расширение функциональности модуля через REST API
- ✅ Безопасный доступ к функциям модуля без прямого доступа к серверу

---

## Архитектура REST API в Bitrix24

### Как это работает?

```
┌─────────────────────┐
│ Внешняя система     │
│ (Camunda, webhook)  │
└──────────┬──────────┘
           │ HTTP POST/GET
           ↓
┌─────────────────────────────────────────┐
│ Входящий webhook Bitrix24               │
│ /rest/{user_id}/{webhook_code}/         │
└──────────┬──────────────────────────────┘
           │
           ↓
┌─────────────────────────────────────────┐
│ REST API Bitrix24                       │
│ (проверка прав, маршрутизация)          │
└──────────┬──────────────────────────────┘
           │
           ↓
┌─────────────────────────────────────────┐
│ OnRestServiceBuildDescription           │
│ (регистрация методов модуля)            │
└──────────┬──────────────────────────────┘
           │
           ↓
┌─────────────────────────────────────────┐
│ Ваш REST обработчик                     │
│ (бизнес-логика)                         │
└─────────────────────────────────────────┘
```

### Ключевые компоненты:

1. **Scope** - область видимости методов (обычно ID модуля, например `imena.camunda`)
2. **Method** - название метода (например `imena.camunda.sync`)
3. **Handler** - класс-обработчик, который реализует логику метода
4. **Event Registration** - регистрация события `OnRestServiceBuildDescription` в базе данных

---

## Пошаговая инструкция

### Шаг 1: Создание класса REST-обработчика

**Путь:** `/local/modules/{module_id}/lib/Rest/YourHandler.php`

**Пример для модуля `imena.camunda`:**

```php
<?php
/**
 * YourHandler - REST-обработчик для вашего функционала
 * #vlikhobabin@gmail.com
 */

declare(strict_types=1);

namespace ImenaCamunda\Rest;

use Bitrix\Main\Loader;

/**
 * REST-обработчик
 * 
 * @package ImenaCamunda\Rest
 */
class YourHandler extends \IRestService
{
    /**
     * Регистрация REST-методов модуля
     * 
     * @return array Описание REST-методов
     */
    public static function OnRestServiceBuildDescription()
    {
        return [
            'imena.camunda' => [  // Scope (обычно совпадает с ID модуля)
                'your.method' => [__CLASS__, 'yourMethodAction'],
                'another.method' => [
                    'callback' => [__CLASS__, 'anotherMethodAction'],
                    'options' => [], // Опционально: дополнительные настройки
                ],
            ],
        ];
    }
    
    /**
     * Обработка метода your.method
     * 
     * @param array $query Данные запроса (GET/POST параметры)
     * @param array $nav Навигационные параметры
     * @param \CRestServer $server REST сервер (может быть null)
     * @return array Ответ метода
     */
    public static function yourMethodAction($query, $nav, \CRestServer $server = null)
    {
        try {
            // 1. Валидация входных данных
            $requiredParam = $query['required_param'] ?? null;
            
            if (empty($requiredParam)) {
                return [
                    'success' => false,
                    'error' => 'Missing required parameter: required_param'
                ];
            }
            
            // 2. Подключаем модуль если нужно
            if (!Loader::includeModule('imena.camunda')) {
                throw new \Exception('Module imena.camunda is not available');
            }
            
            // 3. Выполняем бизнес-логику
            // ... ваш код ...
            
            // 4. Возвращаем результат
            return [
                'success' => true,
                'data' => [
                    'param' => $requiredParam,
                    'timestamp' => date('Y-m-d H:i:s')
                ]
            ];
            
        } catch (\Exception $e) {
            error_log("YourHandler: Error - " . $e->getMessage());
            
            return [
                'success' => false,
                'error' => 'Internal server error: ' . $e->getMessage()
            ];
        }
    }
    
    /**
     * Обработка метода another.method
     */
    public static function anotherMethodAction($query, $nav, \CRestServer $server = null)
    {
        // Ваша логика для другого метода
        return ['success' => true];
    }
}
```

### Шаг 2: Регистрация обработчика в установщике модуля

**Путь:** `/local/modules/{module_id}/install/index.php`

**В методе `DoInstall()` добавьте:**

```php
public function DoInstall()
{
    global $APPLICATION;
    
    if (CheckVersion(ModuleManager::getVersion("main"), "20.0.0")) {
        ModuleManager::registerModule($this->MODULE_ID);
        $this->InstallFiles();
        $this->InstallDB();
        
        // ✅ ВАЖНО: Регистрация REST-обработчика для webhook
        RegisterModuleDependences(
            'rest',                                      // FROM_MODULE_ID
            'OnRestServiceBuildDescription',             // MESSAGE_ID
            $this->MODULE_ID,                           // TO_MODULE_ID (например, 'imena.camunda')
            '\\ImenaCamunda\\Rest\\YourHandler',        // CLASS_NAME (с полным namespace)
            'OnRestServiceBuildDescription'             // METHOD_NAME
        );
        
        $APPLICATION->IncludeAdminFile(
            Loc::getMessage('IMENA_CAMUNDA_INSTALL_TITLE'),
            $this->GetPath() . "/install/step1.php"
        );
    } else {
        $APPLICATION->ThrowException(
            Loc::getMessage('IMENA_CAMUNDA_INSTALL_ERROR_VERSION')
        );
    }

    return false;
}
```

**В методе `DoUninstall()` добавьте:**

```php
public function DoUninstall()
{
    global $APPLICATION;

    // ✅ Удаление регистрации REST-обработчика
    UnRegisterModuleDependences(
        'rest',
        'OnRestServiceBuildDescription',
        $this->MODULE_ID,
        '\\ImenaCamunda\\Rest\\YourHandler',
        'OnRestServiceBuildDescription'
    );

    $this->UnInstallDB();
    $this->UnInstallFiles();
    ModuleManager::unRegisterModule($this->MODULE_ID);

    $APPLICATION->IncludeAdminFile(
        Loc::getMessage('IMENA_CAMUNDA_UNINSTALL_TITLE'),
        $this->GetPath() . "/install/unstep1.php"
    );

    return false;
}
```

### Шаг 3: Переустановка модуля

После добавления REST-обработчика **обязательно** переустановите модуль:

1. Перейдите в админку: `/bitrix/admin/partner_modules.php?lang=ru`
2. Найдите ваш модуль
3. Нажмите **"Действия" → "Удалить"** (данные можно сохранить)
4. Нажмите **"Действия" → "Установить"**

### Шаг 4: Создание входящего webhook

1. Перейдите: **Приложения → Разработчикам → Другое → Входящий вебхук**
2. Создайте новый вебхук
3. В настройках прав выберите:
   - Ваш модуль (например, `imena.camunda`)
   - Другие необходимые модули (например, `Пользователи`)
4. Скопируйте URL вебхука (например: `https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/`)

### Шаг 5: Проверка регистрации методов

Откройте в браузере или через `curl`:

```bash
curl https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/methods
```

**Ожидаемый результат:**

```json
{
  "result": [
    "batch",
    "scope",
    "methods",
    "your.method",        // ✅ Ваш метод должен быть в списке
    "another.method",     // ✅ И другие ваши методы
    "user.get",
    ...
  ]
}
```

Также проверьте scope:

```bash
curl https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/scope
```

**Ожидаемый результат:**

```json
{
  "result": [
    "imena.camunda",  // ✅ Ваш scope должен быть в списке
    "user",
    ...
  ]
}
```

---

## Справочник API методов

Этот раздел содержит полное описание всех доступных REST API методов модуля `imena.camunda`, организованных по классам-обработчикам.

### SyncHandler - Синхронизация процессов

**Файл:** `/local/modules/imena.camunda/lib/Rest/SyncHandler.php`  
**Назначение:** Обработка webhook от Camunda и запуск синхронизации процессов.

#### Метод: `imena.camunda.sync`

**Описание:** Принимает webhook от Camunda и запускает точечную синхронизацию процесса по `processInstanceId`.

**Параметры запроса:**
- `processInstanceId` (обязательный) - ID экземпляра процесса в Camunda
- `processDefinitionKey` (обязательный) - Ключ определения процесса в Camunda

**Пример вызова:**
```bash
curl -X POST "https://{portal}/rest/{user_id}/{webhook_code}/imena.camunda.sync" \
  -H "Content-Type: application/json" \
  -d '{
    "processDefinitionKey": "Process_qunad56t0",
    "processInstanceId": "49b3b068-aff0-11f0-b47d-00b436387543"
  }'
```

**Пример ответа:**
```json
{
  "result": {
    "success": true,
    "message": "Webhook received",
    "processInstanceId": "49b3b068-aff0-11f0-b47d-00b436387543",
    "processDefinitionKey": "Process_qunad56t0",
    "timestamp": "2025-10-23 07:12:54"
  }
}
```

**Особенности:**
- Возвращает немедленный ответ "OK" для подтверждения получения webhook
- Синхронизация выполняется синхронно после формирования ответа
- Выполняет каскадную синхронизацию: definition → instance → tasks

---

### DiagramPropertiesHandler - Параметры диаграмм

**Файл:** `/local/modules/imena.camunda/lib/Rest/DiagramPropertiesHandler.php`  
**Назначение:** Получение параметров диаграммы Storm, связанной с процессом Camunda.

#### Метод: `imena.camunda.diagram.properties.list`

**Описание:** Возвращает список параметров диаграммы Storm по `CAMUNDA_PROCESS_ID`.

**Параметры запроса:**
- `camundaProcessId` (обязательный) - Ключ процесса Camunda (например: `Process_0jsi939`)

**Пример вызова:**
```bash
curl "https://{portal}/rest/{user_id}/{webhook_code}/imena.camunda.diagram.properties.list?camundaProcessId=Process_0jsi939"
```

**Пример ответа:**
```json
{
  "result": {
    "success": true,
    "data": {
      "diagram": {
        "ID": "storm-diagram-uuid",
        "TITLE": "Onboarding Process",
        "STATUS": "IN_PROGRESS",
        "CAMUNDA_PROCESS_ID": "Process_0jsi939",
        "CAMUNDA_VERSION": "1"
      },
      "properties": [
        {
          "ID": 101,
          "CODE": "EMPLOYEE_EMAIL",
          "NAME": "Электронная почта сотрудника",
          "TYPE": "string",
          "IS_REQUIRED": "Y",
          "SORT": 100,
          "DEFAULT_VALUE": null,
          "ENUM_OPTIONS": null
        }
      ],
      "meta": {
        "camundaProcessId": "Process_0jsi939",
        "propertyCount": 1
      }
    }
  }
}
```

**Особенности:**
- Требует модуль `imena.storm`
- Возвращает полную информацию о диаграмме и всех её параметрах
- Параметры отсортированы по полю `SORT`

---

### DiagramResponsibleHandler - Ответственные за диаграммы

**Файл:** `/local/modules/imena.camunda/lib/Rest/DiagramResponsibleHandler.php`  
**Назначение:** Получение списка ответственных (assignees) для диаграммы Storm.

#### Метод: `imena.camunda.diagram.responsible.list`

**Описание:** Возвращает список ответственных диаграммы Storm по `CAMUNDA_PROCESS_ID` (рекомендуемый вариант) или по `DIAGRAM_ID`.

**Параметры запроса (укажите хотя бы один идентификатор):**
- `camundaProcessId` — `CAMUNDA_PROCESS_ID` диаграммы из таблицы `b_imena_storm_diagrams`
- `diagramId` — ID диаграммы Storm (например: `storm-diagram-uuid`)

**Пример вызова (через camundaProcessId):**
```bash
curl "https://{portal}/rest/{user_id}/{webhook_code}/imena.camunda.diagram.responsible.list?camundaProcessId=Process_tvkt6gpec"
```

**Пример ответа:**
```json
{
  "result": {
    "success": true,
    "data": {
      "responsibles": [
        {
          "ID": 3311,
          "DIAGRAM_ID": "a3e6a21f-2686-4a3f-a05e-3badbd04b33c",
          "ASSIGNEE_EDGE_ID": null,
          "ASSIGNEE_ID": null,
          "ELEMENT_ID": "Activity_02iom23",
          "ELEMENT_NAME": "Заполнить заявку на командировку",
          "DESCRIPTION": null,
          "DIAGRAM_NAME": "Создание заявки на командировку. Автоматизация",
          "DIAGRAM_STATUS": null,
          "ASSIGNEE_TYPE": "HUMAN",
          "ASSIGNEE_NAME": null,
          "USER_ID": null,
          "TEMPLATE_ID": 3332,
          "COLOR": null,
          "DURATION": null,
          "DURATION_STRING": null,
          "EXTERNAL_LINK": null,
          "CREATED_ON": "2025-11-24 03:08:08",
          "UPDATED_ON": "2025-11-24 03:08:08",
          "UPDATED_BY": null,
          "VERSION_NUMBER": 1,
          "SORT_INDEX": 240000210,
          "PREDECESSOR_IDS": [],
          "CAMUNDA_PROCESS_ID": "Process_tvkt6gpec"
        },
        {
          "ID": 3312,
          "DIAGRAM_ID": "a3e6a21f-2686-4a3f-a05e-3badbd04b33c",
          "ASSIGNEE_EDGE_ID": null,
          "ASSIGNEE_ID": null,
          "ELEMENT_ID": "Activity_0qu7rkw",
          "ELEMENT_NAME": "Согласовать служебную записку на командировку",
          "DESCRIPTION": null,
          "DIAGRAM_NAME": "Создание заявки на командировку. Автоматизация",
          "DIAGRAM_STATUS": null,
          "ASSIGNEE_TYPE": "HUMAN",
          "ASSIGNEE_NAME": null,
          "USER_ID": null,
          "TEMPLATE_ID": 3333,
          "COLOR": null,
          "DURATION": null,
          "DURATION_STRING": null,
          "EXTERNAL_LINK": null,
          "CREATED_ON": "2025-11-24 03:08:08",
          "UPDATED_ON": "2025-11-24 03:08:08",
          "UPDATED_BY": null,
          "VERSION_NUMBER": 1,
          "SORT_INDEX": 390000210,
          "PREDECESSOR_IDS": ["Activity_02iom23"],
          "CAMUNDA_PROCESS_ID": "Process_tvkt6gpec"
        }
      ],
      "meta": {
        "diagramId": "a3e6a21f-2686-4a3f-a05e-3badbd04b33c",
        "camundaProcessId": "Process_tvkt6gpec",
        "count": 8
      }
    }
  },
  "time": {
    "start": 1763978123.682,
    "finish": 1763978123.7311,
    "duration": 0.04902195930481,
    "processing": 0.01017689704895,
    "date_start": "2025-11-24T04:55:23-05:00",
    "date_finish": "2025-11-24T04:55:23-05:00"
  }
}
```

#### Метод: `imena.camunda.diagram.responsible.get`

**Описание:** Возвращает одну запись ответственного по `CAMUNDA_PROCESS_ID` (или `DIAGRAM_ID`) и `ELEMENT_ID`.

**Параметры запроса:**
- `camundaProcessId` — CAMUNDA_PROCESS_ID диаграммы (рекомендуемый способ)
- `diagramId` — ID диаграммы Storm (опциональный параметр)
- `elementId` (обязательный) — ID элемента диаграммы (Activity)

**Пример вызова (через camundaProcessId):**
```bash
curl "https://{portal}/rest/{user_id}/{webhook_code}/imena.camunda.diagram.responsible.get?camundaProcessId=Process_tvkt6gpec&elementId=Activity_0qu7rkw"
```

**Пример ответа:**
```json
{
  "result": {
    "success": true,
    "data": {
      "responsible": {
        "ID": 3312,
        "DIAGRAM_ID": "a3e6a21f-2686-4a3f-a05e-3badbd04b33c",
        "ASSIGNEE_EDGE_ID": null,
        "ASSIGNEE_ID": null,
        "ELEMENT_ID": "Activity_0qu7rkw",
        "ELEMENT_NAME": "Согласовать служебную записку на командировку",
        "DESCRIPTION": null,
        "DIAGRAM_NAME": "Создание заявки на командировку. Автоматизация",
        "DIAGRAM_STATUS": null,
        "ASSIGNEE_TYPE": "HUMAN",
        "ASSIGNEE_NAME": null,
        "USER_ID": null,
        "TEMPLATE_ID": 3333,
        "COLOR": null,
        "DURATION": null,
        "DURATION_STRING": null,
        "EXTERNAL_LINK": null,
        "CREATED_ON": "2025-11-24 03:08:08",
        "UPDATED_ON": "2025-11-24 03:08:08",
        "UPDATED_BY": null,
        "VERSION_NUMBER": 1,
        "SORT_INDEX": 390000210,
        "PREDECESSOR_IDS": ["Activity_02iom23"],
        "CAMUNDA_PROCESS_ID": "Process_tvkt6gpec"
      },
      "meta": {
        "diagramId": "a3e6a21f-2686-4a3f-a05e-3badbd04b33c",
        "camundaProcessId": "Process_tvkt6gpec",
        "elementId": "Activity_0qu7rkw"
      }
    }
  }
}
```

**Описание полей:**
- `ID` - Уникальный идентификатор записи
- `DIAGRAM_ID` - ID диаграммы Storm
- `ELEMENT_ID` - ID элемента диаграммы (Activity)
- `ELEMENT_NAME` - Название элемента
- `TEMPLATE_ID` - ID шаблона задачи из `b_imena_tasks_templates`
- `ASSIGNEE_TYPE` - Тип назначения (`HUMAN`, `ROLE`, `GROUP`, `SYSTEM`)
- `USER_ID` - ID пользователя Bitrix24 (если назначен)
- `CAMUNDA_PROCESS_ID` - ID процесса Camunda, к которому относится диаграмма
- `CREATED_ON` - Дата создания в формате `Y-m-d H:i:s`
- `UPDATED_ON` - Дата обновления в формате `Y-m-d H:i:s`
- `SORT_INDEX` - Индекс сортировки элементов по координатам на диаграмме
- `PREDECESSOR_IDS` - Массив ID предшествующих элементов (например: `["Activity_02iom23"]`)

**Особенности:**
- Требует модуль `imena.storm`
- Возвращает записи из таблицы `b_imena_storm_responsible`
- Сортировка по `SORT_INDEX` (ASC) и `ELEMENT_NAME` (ASC)
- Даты нормализуются в строковый формат `Y-m-d H:i:s`
- `PREDECESSOR_IDS` парсится из JSON строки в массив
- Пустые значения возвращаются как `null`
- Можно передавать `camundaProcessId` вместо `diagramId` — обработчик автоматически объединяет `b_imena_storm_responsible` и `b_imena_storm_diagrams` по `DIAGRAM_ID`

---

### UserFieldsHandler - Пользовательские поля задач

**Файл:** `/local/modules/imena.camunda/lib/Rest/UserFieldsHandler.php`  
**Назначение:** Работа с пользовательскими полями задач Bitrix24 (TASKS_TASK).

#### Метод: `imena.camunda.userfield.list`

**Описание:** Получение списка всех пользовательских полей для задач.

**Параметры запроса:** Нет

**Пример вызова:**
```bash
curl "https://{portal}/rest/{user_id}/{webhook_code}/imena.camunda.userfield.list"
```

**Пример ответа:**
```json
{
  "result": {
    "userFields": [
      {
        "ID": 123,
        "FIELD_NAME": "UF_TASK_CUSTOM_FIELD",
        "USER_TYPE_ID": "string",
        "XML_ID": "",
        "SORT": 100,
        "MULTIPLE": "N",
        "MANDATORY": "Y",
        "SHOW_FILTER": "Y",
        "SHOW_IN_LIST": "Y",
        "EDIT_IN_LIST": "N",
        "IS_SEARCHABLE": "Y",
        "SETTINGS": {},
        "SETTINGS_PARSED": {},
        "ENTITY_ID": "TASKS_TASK",
        "HAS_ENUM_VALUES": false
      }
    ],
    "total": 1,
    "entity": "TASKS_TASK"
  }
}
```

**Особенности:**
- Для полей типа `enumeration` автоматически загружаются значения enum
- Настройки полей парсятся из JSON
- Поля отсортированы по `SORT` и `ID`

---

#### Метод: `imena.camunda.userfield.get`

**Описание:** Получение конкретного пользовательского поля по ID.

**Параметры запроса:**
- `fieldId` (обязательный) - ID пользовательского поля

**Пример вызова:**
```bash
curl "https://{portal}/rest/{user_id}/{webhook_code}/imena.camunda.userfield.get?fieldId=123"
```

**Пример ответа:**
```json
{
  "result": {
    "userField": {
      "ID": 123,
      "FIELD_NAME": "UF_TASK_CUSTOM_FIELD",
      "USER_TYPE_ID": "enumeration",
      "ENUM_VALUES": [
        {
          "ID": 1,
          "VALUE": "Значение 1",
          "DEF": "Y",
          "SORT": 100,
          "XML_ID": "",
          "IS_DEFAULT": true
        }
      ],
      "SETTINGS_PARSED": {},
      "ENTITY_ID": "TASKS_TASK",
      "HAS_ENUM_VALUES": true
    }
  }
}
```

**Ошибки:**
- `404` - Поле не найдено или не принадлежит TASKS_TASK

---

#### Метод: `imena.camunda.userfield.stats`

**Описание:** Получение статистики по пользовательским полям (группировка по типам).

**Параметры запроса:** Нет

**Пример вызова:**
```bash
curl "https://{portal}/rest/{user_id}/{webhook_code}/imena.camunda.userfield.stats"
```

**Пример ответа:**
```json
{
  "result": {
    "stats": {
      "total": 15,
      "by_type": {
        "string": 8,
        "enumeration": 5,
        "boolean": 2
      },
      "types_count": 3,
      "most_common_type": "string",
      "entity": "TASKS_TASK"
    }
  }
}
```

---

#### Метод: `imena.camunda.userfield.types`

**Описание:** Получение информации о поддерживаемых типах пользовательских полей.

**Параметры запроса:** Нет

**Пример вызова:**
```bash
curl "https://{portal}/rest/{user_id}/{webhook_code}/imena.camunda.userfield.types"
```

**Пример ответа:**
```json
{
  "result": {
    "types": {
      "string": {
        "name": "Строка",
        "description": "Текстовое поле",
        "supports_multiple": true,
        "supports_enum": false
      },
      "enumeration": {
        "name": "Список",
        "description": "Выпадающий список с предустановленными значениями",
        "supports_multiple": true,
        "supports_enum": true
      },
      "boolean": {
        "name": "Да/Нет",
        "description": "Логическое поле (да/нет)",
        "supports_multiple": false,
        "supports_enum": false
      }
    }
  }
}
```

---

#### Метод: `imena.camunda.userfield.exists`

**Описание:** Проверка существования пользовательского поля.

**Параметры запроса:**
- `fieldId` (обязательный) - ID пользовательского поля

**Пример вызова:**
```bash
curl "https://{portal}/rest/{user_id}/{webhook_code}/imena.camunda.userfield.exists?fieldId=123"
```

**Пример ответа:**
```json
{
  "result": {
    "exists": true,
    "fieldId": 123
  }
}
```

---

### UserSupervisorHandler - Руководители пользователей

**Файл:** `/local/modules/imena.camunda/lib/Rest/UserSupervisorHandler.php`  
**Назначение:** Получение ID руководителя пользователя через структуру компании.

#### Метод: `imena.camunda.user.supervisor.get`

**Описание:** Возвращает ID руководителя пользователя. Руководитель определяется через структуру компании: если у пользователя есть отдел, возвращается руководитель отдела (UF_HEAD).

**Параметры запроса:**
- `userId` (обязательный) - ID пользователя Bitrix24

**Пример вызова:**
```bash
curl "https://{portal}/rest/{user_id}/{webhook_code}/imena.camunda.user.supervisor.get?userId=107"
```

**Пример ответа (руководитель найден):**
```json
{
  "result": {
    "success": true,
    "data": {
      "userId": 107,
      "supervisorId": 42
    }
  }
}
```

**Пример ответа (руководитель не найден):**
```json
{
  "result": {
    "success": true,
    "data": {
      "userId": 107,
      "supervisorId": null,
      "message": "Supervisor not found for this user"
    }
  }
}
```

**Особенности:**
- Использует первый отдел пользователя (UF_DEPARTMENT[0])
- Ищет отдел в IBLOCK_ID 3 и 1
- Проверяет, что руководитель активен (ACTIVE = 'Y')
- Требует модули: `main`, `intranet`, `iblock`

**Ошибки:**
- `Missing or invalid required parameter: userId` - Не указан или некорректный userId

---

### TaskTemplateHandler - Шаблоны задач

**Файл:** `/local/modules/imena.camunda/lib/Rest/TaskTemplateHandler.php`
**Назначение:** Получение шаблонов задач для создания задач в Bitrix24 по этапам процессов Camunda.

#### Метод: `imena.camunda.tasktemplate.get`

**Описание:** Возвращает полный JSON шаблона задачи по `CAMUNDA_PROCESS_ID` и `ELEMENT_ID`. Используется Camunda 7 для создания задач в Битрикс24 по этапам процессов.

**Параметры запроса:**
- `camundaProcessId` (обязательный) - ID процесса в Camunda (например: `Process_syi17nb19`)
- `elementId` (обязательный) - ID элемента диаграммы (например: `Activity_0tqmi90`)

**Пример вызова:**
```bash
curl "https://{portal}/rest/{user_id}/{webhook_code}/imena.camunda.tasktemplate.get?camundaProcessId=Process_syi17nb19&elementId=Activity_0tqmi90"
```

**Пример ответа:**
```json
{
  "result": {
    "success": true,
    "data": {
      "template": {
        "ID": 1,
        "TITLE": "Название шаблона",
        "DESCRIPTION": "Описание задачи",
        "RESPONSIBLE_ID": 1,
        "...": "другие поля шаблона"
      },
      "members": {
        "all": [...],
        "by_type": {
          "R": [...],
          "A": [...],
          "U": [...]
        }
      },
      "tags": [...],
      "checklists": {
        "items": [...],
        "total": 4,
        "has_tree": true
      },
      "files": [...],
      "questionnaires": {
        "items": [
          {
            "ID": 2,
            "TEMPLATE_ID": 3348,
            "CODE": "it",
            "TITLE": "Техника",
            "SORT": 100,
            "questions": [
              {
                "ID": 2,
                "QUESTIONNAIRE_TEMPLATE_ID": 2,
                "CODE": "note",
                "TEXT": "Нужен ноут?",
                "TYPE": "radio",
                "IS_REQUIRED": "Y",
                "options": [
                  {"ID": 3, "CODE": "yes", "TEXT": "Да", "SORT": 100},
                  {"ID": 4, "CODE": "no", "TEXT": "Нет", "SORT": 200}
                ]
              }
            ]
          }
        ],
        "total": 1,
        "has_codes": true
      },
      "meta": {
        "camundaProcessId": "Process_qunad56t0",
        "elementId": "Activity_1522g7n",
        "templateId": 3348
      }
    }
  }
}
```

**Структура ответа:**

| Поле | Тип | Описание |
|------|-----|----------|
| `template` | object | Основные данные шаблона из `b_imena_tasks_templates` |
| `members` | object | Участники шаблона (ответственные R, соисполнители A, наблюдатели U) |
| `tags` | array | Теги шаблона |
| `checklists` | object | Чек-листы с древовидной структурой |
| `files` | array | Прикрепленные файлы (Bitrix Disk) |
| `questionnaires` | object | **Анкеты с CODE полями для Camunda интеграции** |
| `meta` | object | Метаданные запроса |

**Структура questionnaires (Анкеты):**

| Поле | Тип | Описание |
|------|-----|----------|
| `items` | array | Массив анкет с полной структурой |
| `total` | int | Общее количество анкет |
| `has_codes` | bool | Наличие CODE полей для интеграции с Camunda |

**Структура анкеты (questionnaires.items[]):**

| Поле | Тип | Описание |
|------|-----|----------|
| `ID` | int | ID анкеты шаблона |
| `TEMPLATE_ID` | int | ID шаблона задачи |
| `CODE` | string\|null | Уникальный код анкеты для Camunda |
| `TITLE` | string | Название анкеты |
| `SORT` | int | Сортировка |
| `questions` | array | Массив вопросов |

**Структура вопроса (questions[]):**

| Поле | Тип | Описание |
|------|-----|----------|
| `ID` | int | ID вопроса |
| `CODE` | string\|null | Уникальный код вопроса для Camunda |
| `TEXT` | string | Текст вопроса |
| `TYPE` | string | Тип: `radio` (один ответ) или `checkbox` (несколько) |
| `IS_REQUIRED` | string | Обязательность: `Y` или `N` |
| `options` | array | Массив вариантов ответа |

**Структура варианта ответа (options[]):**

| Поле | Тип | Описание |
|------|-----|----------|
| `ID` | int | ID варианта |
| `CODE` | string\|null | Уникальный код варианта для Camunda |
| `TEXT` | string | Текст варианта |
| `SORT` | int | Сортировка |

**Использование CODE полей в Camunda:**

CODE поля позволяют формировать переменные процесса Camunda в формате:
```
{questionnaire_code}_{question_code} = {option_code}
```

Например, для анкеты с CODE=`it`, вопроса с CODE=`note` и выбранного варианта с CODE=`yes`:
```
it_note = yes
```

Это позволяет использовать результаты анкет в gateway-условиях BPMN:
```
${it_note == 'yes'}
```

**Особенности:**
- Находит шаблон через JOIN: `b_imena_storm_diagrams` → `b_imena_storm_responsible` → `b_imena_tasks_templates`
- Возвращает полную структуру шаблона (теги, чек-листы, участники, файлы, анкеты)
- Анкеты загружаются из модуля `imena.tasks.questionnaire` (#vlikhobabin@gmail.com)

---

### TaskQuestionnaireHandler - Анкеты задач

**Файл:** `/local/modules/imena.camunda/lib/Rest/TaskQuestionnaireHandler.php`
**Назначение:** Добавление и получение анкет для задач. Используется Camunda для добавления анкет из шаблона в созданную задачу.

#### Метод: `imena.camunda.task.questionnaire.add`

**Описание:** Добавляет анкеты в задачу из JSON, полученного через `TaskTemplateHandler`. Позволяет создать анкеты с полной структурой (вопросы, варианты ответов, CODE поля для Camunda).

**Параметры запроса:**
- `taskId` (обязательный) - ID задачи
- `questionnaires` (обязательный) - массив анкет в формате из `TaskTemplateHandler.questionnaires.items`

**Пример вызова:**
```bash
curl -X POST "https://{portal}/rest/{user_id}/{webhook_code}/imena.camunda.task.questionnaire.add" \
  -H "Content-Type: application/json" \
  -d '{
    "taskId": 123,
    "questionnaires": [
      {
        "CODE": "it_equipment",
        "TITLE": "Техника",
        "SORT": 100,
        "questions": [
          {
            "CODE": "need_laptop",
            "TEXT": "Нужен ноутбук?",
            "TYPE": "radio",
            "IS_REQUIRED": "Y",
            "options": [
              {"CODE": "yes", "TEXT": "Да"},
              {"CODE": "no", "TEXT": "Нет"}
            ]
          }
        ]
      }
    ]
  }'
```

**Пример ответа:**
```json
{
  "result": {
    "success": true,
    "data": {
      "taskId": 123,
      "createdIds": [48, 49],
      "totalCreated": 2
    }
  }
}
```

**Структура ответа (add):**

| Поле | Тип | Описание |
|------|-----|----------|
| `taskId` | int | ID задачи |
| `createdIds` | array | Массив ID созданных анкет |
| `totalCreated` | int | Количество созданных анкет |

#### Метод: `imena.camunda.task.questionnaire.list`

**Описание:** Возвращает список анкет задачи с полной структурой.

**Параметры запроса:**
- `taskId` (обязательный) - ID задачи

**Пример вызова:**
```bash
curl "https://{portal}/rest/{user_id}/{webhook_code}/imena.camunda.task.questionnaire.list?taskId=123"
```

**Пример ответа:**
```json
{
  "result": {
    "success": true,
    "data": {
      "taskId": 123,
      "items": [
        {
          "ID": 48,
          "TASK_ID": 123,
          "CODE": "it_equipment",
          "TITLE": "Техника",
          "SORT": 100,
          "questions": [
            {
              "ID": 1,
              "CODE": "need_laptop",
              "TEXT": "Нужен ноутбук?",
              "TYPE": "radio",
              "IS_REQUIRED": "Y",
              "options": [
                {"ID": 1, "CODE": "yes", "TEXT": "Да", "isSelected": false},
                {"ID": 2, "CODE": "no", "TEXT": "Нет", "isSelected": false}
              ],
              "hasAnswer": false
            }
          ]
        }
      ],
      "total": 1,
      "has_codes": true
    }
  }
}
```

**Структура ответа (list):**

| Поле | Тип | Описание |
|------|-----|----------|
| `taskId` | int | ID задачи |
| `items` | array | Массив анкет с полной структурой |
| `total` | int | Количество анкет |
| `has_codes` | bool | Наличие CODE полей для интеграции с Camunda |

**Интеграция с Camunda:**

Типичный сценарий использования:

1. Camunda создаёт задачу через стандартный REST API Bitrix24
2. Camunda вызывает `imena.camunda.tasktemplate.get` для получения шаблона с анкетами
3. Camunda вызывает `imena.camunda.task.questionnaire.add` для добавления анкет в созданную задачу

```javascript
// Пример в Service Task Camunda
// 1. Получаем шаблон с анкетами
const templateResponse = await fetch(
  `${BITRIX_REST_URL}/imena.camunda.tasktemplate.get?` +
  `camundaProcessId=${processId}&elementId=${elementId}`
);
const template = await templateResponse.json();

// 2. Создаём задачу через стандартный API (tasks.task.add)
const taskResponse = await fetch(`${BITRIX_REST_URL}/tasks.task.add`, {
  method: 'POST',
  body: JSON.stringify({ fields: { ... } })
});
const task = await taskResponse.json();

// 3. Добавляем анкеты из шаблона в задачу
if (template.result.data.questionnaires.total > 0) {
  await fetch(`${BITRIX_REST_URL}/imena.camunda.task.questionnaire.add`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      taskId: task.result.task.id,
      questionnaires: template.result.data.questionnaires.items
    })
  });
}
```

**Особенности:**
- Поддерживает CODE поля для интеграции с Camunda
- Сохраняет полную структуру анкет (вопросы, варианты ответов)
- Валидирует существование задачи перед добавлением
- Использует сервис `QuestionnaireService` из модуля `imena.tasks.questionnaire` (#vlikhobabin@gmail.com)

---

### TaskDependencyHandler - Зависимости задач

**Файл:** `/local/modules/imena.camunda/lib/Rest/TaskDependencyHandler.php`
**Назначение:** Управление зависимостями задач (Диаграмма Ганта).

#### Метод: `imena.camunda.task.dependency.add`

**Описание:** Создает связь типа "Конец-Старт" (Finish-Start) между двумя задачами. Текущая задача (`taskId`) начнется после завершения предшествующей (`dependsOnId`).

**Параметры запроса:**
- `taskId` (обязательный) - ID задачи-последователя (которая зависит)
- `dependsOnId` (обязательный) - ID задачи-предшественника (от которой зависят)

**Пример вызова:**
```bash
curl -X POST "https://{portal}/rest/{user_id}/{webhook_code}/imena.camunda.task.dependency.add" \
  -H "Content-Type: application/json" \
  -d '{
    "taskId": 366,
    "dependsOnId": 365
  }'
```

**Пример ответа:**
```json
{
  "result": {
    "success": true,
    "data": {
      "taskId": 366,
      "dependsOnId": 365,
      "type": 2,
      "typeDescription": "Finish-Start"
    }
  }
}
```

**Ошибки:**
- `Invalid taskId/dependsOnId` - Некорректные ID
- `Task cannot depend on itself` - Попытка связать задачу саму с собой
- `ERROR_ADDING_DEPENDENCY` - Внутренняя ошибка при создании связи (циклическая зависимость и т.д.)

---

## Примеры использования

> 💡 **Примечание:** Полное описание всех методов доступно в разделе [Справочник API методов](#справочник-api-методов).

### Пример 1: Получение списка пользовательских полей задач

**Метод:** [`imena.camunda.userfield.list`](#метод-imenacamundauserfieldlist)

```bash
# Простой GET запрос
curl "https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/imena.camunda.userfield.list"

# С форматированием JSON
curl "https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/imena.camunda.userfield.list" | jq
```

### Пример 2: Получение шаблона задачи для Camunda процесса

**Метод:** [`imena.camunda.tasktemplate.get`](#метод-imenacamundatasktemplateget)

```bash
curl "https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/imena.camunda.tasktemplate.get?camundaProcessId=Process_syi17nb19&elementId=Activity_0tqmi90"
```

**Использование в Camunda:**
```javascript
// В Service Task или Script Task Camunda
fetch('https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/imena.camunda.tasktemplate.get', {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json'
  },
  params: {
    camundaProcessId: execution.getProcessDefinitionId(),
    elementId: execution.getCurrentActivityId()
  }
})
.then(response => response.json())
.then(data => {
  // Использование шаблона для создания задачи
  const template = data.result.data;
  // ... создание задачи в Bitrix24
});
```

### Пример 3: Webhook синхронизации от Camunda

**Метод:** [`imena.camunda.sync`](#метод-imenacamundasync)

```bash
curl -X POST "https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/imena.camunda.sync" \
  -H "Content-Type: application/json" \
  -d '{
    "processDefinitionKey": "Process_qunad56t0",
    "processInstanceId": "49b3b068-aff0-11f0-b47d-00b436387543"
  }'
```

**Настройка в Camunda:**
1. Создайте HTTP Connector в Service Task
2. URL: `https://bx-dev.eg-holding.ru/rest/1/{webhook_code}/imena.camunda.sync`
3. Method: POST
4. Body: JSON с `processDefinitionKey` и `processInstanceId`

### Пример 4: Получение руководителя пользователя

**Метод:** [`imena.camunda.user.supervisor.get`](#метод-imenacamundausersupervisorget)

```bash
curl "https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/imena.camunda.user.supervisor.get?userId=107"
```

**Использование в бизнес-логике:**
```php
// В PHP коде модуля
$supervisorId = null;
$response = file_get_contents(
    "https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/imena.camunda.user.supervisor.get?userId={$userId}"
);
$data = json_decode($response, true);
if ($data['result']['success'] && $data['result']['data']['supervisorId']) {
    $supervisorId = $data['result']['data']['supervisorId'];
}
```

### Пример 5: Получение параметров диаграммы

**Метод:** [`imena.camunda.diagram.properties.list`](#метод-imenacamundadiagrampropertieslist)

```bash
curl "https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/imena.camunda.diagram.properties.list?camundaProcessId=Process_0jsi939"
```

### Пример 6: Получение ответственных за диаграмму

**Метод:** [`imena.camunda.diagram.responsible.list`](#метод-imenacamundadiagramresponsiblelist)

```bash
curl "https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/imena.camunda.diagram.responsible.list?camundaProcessId=Process_tvkt6gpec"
```

**Использование для получения всех элементов диаграммы с их шаблонами:**
```bash
# Получаем список ответственных
RESPONSIBLES=$(curl -s "https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/imena.camunda.diagram.responsible.list?camundaProcessId=Process_tvkt6gpec")

# Извлекаем TEMPLATE_ID для каждого элемента
echo "$RESPONSIBLES" | jq '.result.data.responsibles[] | {element: .ELEMENT_ID, template: .TEMPLATE_ID, predecessors: .PREDECESSOR_IDS}'
```

### Пример 7: Получение конкретного ответственного по ID элемента

**Метод:** [`imena.camunda.diagram.responsible.get`](#метод-imenacamundadiagramresponsibleget)

```bash
curl "https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/imena.camunda.diagram.responsible.get?camundaProcessId=Process_tvkt6gpec&elementId=Activity_0qu7rkw"
```

### Пример 8: Проверка существования пользовательского поля

**Метод:** [`imena.camunda.userfield.exists`](#метод-imenacamundauserfieldexists)

```bash
# Проверка существования поля
curl "https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/imena.camunda.userfield.exists?fieldId=123"

# Использование в bash скрипте
FIELD_EXISTS=$(curl -s "https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/imena.camunda.userfield.exists?fieldId=123" | jq -r '.result.exists')
if [ "$FIELD_EXISTS" = "true" ]; then
    echo "Поле существует"
else
    echo "Поле не найдено"
fi
```

---

## Тестирование

### 1. Проверка через браузер

Создайте тестовый файл `/test_rest_api.php`:

```php
<?php
require_once $_SERVER['DOCUMENT_ROOT'] . '/bitrix/modules/main/include/prolog_before.php';

echo "<h1>Тестирование REST API</h1>";

// Загружаем модуль
if (\Bitrix\Main\Loader::includeModule('imena.camunda')) {
    echo "<p style='color: green;'>✅ Модуль загружен</p>";
    
    // Проверяем, что класс существует
    if (class_exists('\\ImenaCamunda\\Rest\\YourHandler')) {
        echo "<p style='color: green;'>✅ Класс YourHandler существует</p>";
        
        // Проверяем метод OnRestServiceBuildDescription
        $result = \ImenaCamunda\Rest\YourHandler::OnRestServiceBuildDescription();
        echo "<h3>Зарегистрированные методы:</h3>";
        echo "<pre>" . print_r($result, true) . "</pre>";
        
        // Тестируем прямой вызов метода
        echo "<h3>Тестовый вызов метода:</h3>";
        $testResult = \ImenaCamunda\Rest\YourHandler::yourMethodAction(
            ['required_param' => 'test_value'],
            [],
            null
        );
        echo "<pre>" . print_r($testResult, true) . "</pre>";
        
    } else {
        echo "<p style='color: red;'>❌ Класс YourHandler не найден</p>";
    }
} else {
    echo "<p style='color: red;'>❌ Модуль не загружен</p>";
}

require_once $_SERVER['DOCUMENT_ROOT'] . '/bitrix/modules/main/include/epilog_after.php';
?>
```

### 2. Проверка через curl

```bash
# Проверка списка методов
curl "https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/methods" | jq '.result[] | select(. | contains("your."))'

# Вызов метода с GET параметрами
curl "https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/your.method?required_param=test"

# Вызов метода с POST параметрами
curl -X POST "https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/your.method" \
  -H "Content-Type: application/json" \
  -d '{"required_param": "test_value"}'

# Проверка с выводом заголовков
curl -v "https://bx-dev.eg-holding.ru/rest/1/tip76z85stzjop28/your.method?required_param=test"
```

### 3. Проверка регистрации в базе данных

```sql
-- Проверка регистрации события
SELECT * FROM b_module_to_module 
WHERE TO_MODULE_ID = 'imena.camunda' 
  AND FROM_MODULE_ID = 'rest';

-- Ожидаемый результат:
-- ID | FROM_MODULE_ID | TO_MODULE_ID    | MESSAGE_ID                      | CLASS_NAME                           | METHOD_NAME
-- ---+----------------+-----------------+---------------------------------+--------------------------------------+-----------------------------
-- XX | rest           | imena.camunda   | OnRestServiceBuildDescription   | \ImenaCamunda\Rest\YourHandler      | OnRestServiceBuildDescription
```

### 4. Проверка логов

```bash
# Проверка логов Apache
tail -f /var/log/httpd/error_log | grep -i "YourHandler"

# Проверка PHP логов
tail -f /var/log/php-fpm/error.log | grep -i "YourHandler"
```

---

## Решение проблем

### Проблема 1: "ERROR_METHOD_NOT_FOUND"

**Симптомы:**
```json
{"error":"ERROR_METHOD_NOT_FOUND","error_description":"Method not found!"}
```

**Решение:**

1. **Проверьте регистрацию в базе данных:**
   ```sql
   SELECT * FROM b_module_to_module 
   WHERE TO_MODULE_ID = 'ваш.модуль' AND FROM_MODULE_ID = 'rest';
   ```
   
   Убедитесь, что:
   - `FROM_MODULE_ID = 'rest'`
   - `TO_MODULE_ID = 'ваш.модуль'` (например, `'imena.camunda'`)
   - `CLASS_NAME` содержит полный namespace с `\\` (например, `'\\ImenaCamunda\\Rest\\YourHandler'`)

2. **Переустановите модуль:**
   - Удалите модуль через админку
   - Установите заново

3. **Проверьте namespace класса:**
   ```php
   // Правильно:
   namespace ImenaCamunda\Rest;
   
   // В регистрации:
   '\\ImenaCamunda\\Rest\\YourHandler'
   ```

4. **Проверьте метод OnRestServiceBuildDescription:**
   ```php
   public static function OnRestServiceBuildDescription()
   {
       return [
           'ваш.модуль' => [  // Scope должен совпадать с ID модуля
               'method.name' => [__CLASS__, 'methodAction'],
           ],
       ];
   }
   ```

5. **Очистите кеш:**
   ```bash
   rm -rf /home/bitrix/www/bitrix/cache/*
   rm -rf /home/bitrix/www/bitrix/managed_cache/*
   ```

### Проблема 2: Webhook не имеет прав на модуль

**Симптомы:**
```json
{"error":"INVALID_CREDENTIALS","error_description":"Invalid request credentials"}
```

**Решение:**

1. Перейдите к настройкам webhook
2. В разделе "Права доступа" убедитесь, что выбран ваш модуль
3. Пересоздайте webhook, выбрав правильные права

### Проблема 3: Класс не найден

**Симптомы:**
- Метод не появляется в списке `/rest/.../methods`
- Ошибки в логах о ненайденном классе

**Решение:**

1. **Проверьте автозагрузку:**
   
   В файле `/local/modules/ваш.модуль/include.php` должна быть регистрация автозагрузчика:
   
   ```php
   \Bitrix\Main\Loader::registerAutoLoadClasses(
       'imena.camunda',
       [
           '\\ImenaCamunda\\Rest\\YourHandler' => 'lib/Rest/YourHandler.php',
       ]
   );
   ```

2. **Проверьте структуру папок:**
   ```
   /local/modules/imena.camunda/
   ├── lib/
   │   └── Rest/
   │       └── YourHandler.php  ✅ Файл должен существовать
   ```

3. **Проверьте namespace:**
   ```php
   <?php
   namespace ImenaCamunda\Rest;  // ✅ Должен совпадать с путем
   ```

### Проблема 4: Методы не обновляются после изменений

**Решение:**

1. **Очистите кеш Bitrix:**
   ```bash
   rm -rf /home/bitrix/www/bitrix/cache/*
   rm -rf /home/bitrix/www/bitrix/managed_cache/*
   ```

2. **Перезапустите PHP-FPM:**
   ```bash
   systemctl restart php-fpm
   ```

3. **Перезапустите Apache:**
   ```bash
   systemctl restart httpd
   ```

4. **Переустановите модуль** через админку

### Проблема 5: Агент не выполняется

**Симптомы:**
- Агент создается, но не выполняется
- Логов выполнения нет

**Решение:**

1. **Проверьте агента в базе данных:**
   ```sql
   SELECT ID, MODULE_ID, NAME, NEXT_EXEC, AGENT_INTERVAL, ACTIVE 
   FROM b_agent 
   WHERE MODULE_ID = 'ваш.модуль' 
   ORDER BY ID DESC;
   ```

2. **Проверьте NEXT_EXEC:**
   - Должна быть дата в будущем или текущее время
   - Если дата в прошлом, агент выполнится при следующем запуске cron

3. **Запустите агенты вручную:**
   ```bash
   php -f /home/bitrix/www/bitrix/modules/main/tools/cron_events.php
   ```

4. **Проверьте логи:**
   ```bash
   tail -f /var/log/httpd/error_log | grep -i "Agent"
   ```

---

## Дополнительные рекомендации

### 1. Безопасность

- ✅ Всегда валидируйте входные данные
- ✅ Используйте prepared statements для SQL
- ✅ Проверяйте права доступа пользователя
- ✅ Логируйте все действия
- ✅ Не возвращайте стек трейсы в production

### 2. Производительность

- ✅ Используйте асинхронную обработку для долгих операций
- ✅ Ограничивайте размер ответа
- ✅ Используйте кеширование где возможно
- ✅ Оптимизируйте запросы к БД

### 3. Логирование

```php
// Используйте error_log для отладки
error_log("YourHandler: Processing request with ID={$id}");

// Или Bitrix Logger
\Bitrix\Main\Diag\Debug::writeToFile(
    ['request' => $query, 'result' => $result],
    'rest_api_call',
    '/log/rest_api.log'
);
```

### 4. Документирование

Создайте файл `README.md` в папке `/lib/Rest/` с описанием:
- Списка доступных методов
- Параметров каждого метода
- Примеров запросов и ответов
- Кодов ошибок

---

## Чек-лист при добавлении нового REST метода

- [ ] Создан класс-обработчик в `/lib/Rest/`
- [ ] Реализован метод `OnRestServiceBuildDescription()`
- [ ] Добавлен `RegisterModuleDependences` в `install/index.php`
- [ ] Добавлен `UnRegisterModuleDependences` в `install/index.php`
- [ ] Модуль переустановлен через админку
- [ ] Создан входящий webhook с правами на модуль
- [ ] Метод появляется в `/rest/.../methods`
- [ ] Метод работает при вызове через curl
- [ ] Добавлено логирование
- [ ] Добавлена валидация параметров
- [ ] Написана документация
- [ ] Проведено тестирование

---

## Полезные ссылки

- [Документация Bitrix REST API](https://dev.1c-bitrix.ru/rest_help/)
- [Создание входящих вебхуков](https://dev.1c-bitrix.ru/rest_help/general/webhooks.php)
- [Регистрация событий в модуле](https://dev.1c-bitrix.ru/api_help/main/functions/module/registermoduledependences.php)
- [D7 ORM](https://dev.1c-bitrix.ru/learning/course/index.php?COURSE_ID=43&LESSON_ID=5753)

---

## Список всех доступных методов

Все методы модуля `imena.camunda` организованы по классам-обработчикам. Полное описание каждого метода доступно в разделе [Справочник API методов](#справочник-api-методов).

### Быстрая навигация по методам:

| Метод | Класс | Описание |
|-------|-------|----------|
| `imena.camunda.sync` | [SyncHandler](#synchandler---синхронизация-процессов) | Webhook синхронизации от Camunda |
| `imena.camunda.diagram.properties.list` | [DiagramPropertiesHandler](#diagrampropertieshandler---параметры-диаграмм) | Параметры диаграммы Storm |
| `imena.camunda.diagram.responsible.list` | [DiagramResponsibleHandler](#diagramresponsiblehandler---ответственные-за-диаграммы) | Список ответственных диаграммы |
| `imena.camunda.diagram.responsible.get` | [DiagramResponsibleHandler](#diagramresponsiblehandler---ответственные-за-диаграммы) | Получение одного ответственного |
| `imena.camunda.userfield.list` | [UserFieldsHandler](#userfieldshandler---пользовательские-поля-задач) | Список пользовательских полей задач |
| `imena.camunda.userfield.get` | [UserFieldsHandler](#userfieldshandler---пользовательские-поля-задач) | Получение поля по ID |
| `imena.camunda.userfield.stats` | [UserFieldsHandler](#userfieldshandler---пользовательские-поля-задач) | Статистика по полям |
| `imena.camunda.userfield.types` | [UserFieldsHandler](#userfieldshandler---пользовательские-поля-задач) | Типы пользовательских полей |
| `imena.camunda.userfield.exists` | [UserFieldsHandler](#userfieldshandler---пользовательские-поля-задач) | Проверка существования поля |
| `imena.camunda.user.supervisor.get` | [UserSupervisorHandler](#usersupervisorhandler---руководители-пользователей) | Получение руководителя пользователя |
| `imena.camunda.tasktemplate.get` | [TaskTemplateHandler](#tasktemplatehandler---шаблоны-задач) | Получение шаблона задачи |
| `imena.camunda.task.questionnaire.add` | [TaskQuestionnaireHandler](#taskquestionnairehandler---анкеты-задач) | Добавление анкет в задачу |
| `imena.camunda.task.questionnaire.list` | [TaskQuestionnaireHandler](#taskquestionnairehandler---анкеты-задач) | Получение списка анкет задачи |
| `imena.camunda.task.dependency.add` | [TaskDependencyHandler](#taskdependencyhandler---зависимости-задач) | Создание зависимости (Gantt) |

### Структура файлов:

```
/local/modules/imena.camunda/lib/Rest/
├── SyncHandler.php                    # Синхронизация процессов
├── DiagramPropertiesHandler.php       # Параметры диаграмм
├── DiagramResponsibleHandler.php      # Ответственные за диаграммы
├── UserFieldsHandler.php              # Пользовательские поля задач
├── UserSupervisorHandler.php          # Руководители пользователей
├── TaskTemplateHandler.php            # Шаблоны задач
├── TaskQuestionnaireHandler.php       # Анкеты задач
├── TaskDependencyHandler.php          # Зависимости задач (Gantt)
└── README.md                          # Эта документация
```

---

**Автор:** vlikhobabin@gmail.com
**Дата:** 2025-12-08
**Версия:** 2.1

**Изменения в версии 2.1:**
- Добавлен новый обработчик `TaskQuestionnaireHandler` для работы с анкетами задач
- Методы `imena.camunda.task.questionnaire.add` и `imena.camunda.task.questionnaire.list`
- Поддержка CODE полей для интеграции с Camunda process variables
- Скрипты регистрации и тестирования handler'а

**Изменения в версии 2.0:**
- ✅ Добавлен новый обработчик `DiagramResponsibleHandler` (`imena.camunda.diagram.responsible.list`)
- ✅ Добавлен справочник API методов с полным описанием всех классов и методов
- ✅ Структурирована документация по классам-обработчикам
- ✅ Обновлены примеры использования с реальными методами
- ✅ Добавлена таблица быстрой навигации по методам
