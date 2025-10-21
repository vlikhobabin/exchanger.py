# 📚 REST API для пользовательских полей задач TASKS_TASK

## 🎯 Обзор

Данное руководство описывает кастомный REST API endpoint для получения информации о пользовательских полях задач в Битрикс24. API дополняет стандартный REST API Битрикс24, заполняя пробел в отсутствии методов для получения списка пользовательских полей.

### Решаемая проблема

Стандартный REST API Битрикс24 не предоставляет удобного способа получения списка всех пользовательских полей для объекта TASKS_TASK с их свойствами и значениями enum полей. Существующие методы (`tasks.task.list`, `tasks.task.get`) возвращают пользовательские поля только в контексте конкретных задач, что неудобно для получения метаинформации о полях.

### Преимущества кастомного API

- ✅ **Полная информация** - возвращает все свойства полей включая enum значения
- ✅ **Удобный доступ** - единый endpoint для получения списка всех полей
- ✅ **Детальная информация** - поддержка получения конкретного поля с полными данными
- ✅ **Статистика** - группировка полей по типам с количественной статистикой
- ✅ **Типизированные ответы** - структурированный JSON с обработкой ошибок
- ✅ **D7 архитектура** - следует принципам Битрикс D7 и PSR-4
- ✅ **Кроссплатформенность** - работает с любыми языками программирования
- ✅ **Разделение ответственности** - API отделен от тестового интерфейса
- ✅ **Простота интеграции** - чистый REST API без зависимостей от GUI

## 🚀 Быстрый старт

### Базовый URL

```
https://your-domain.bitrix24.ru/local/modules/imena.camunda/lib/UserFields/userfields_api.php
```

> **Важно:** Данный API работает через отдельный endpoint файл, а не через стандартный REST API Битрикс24. Это означает, что не требуется webhook URL, но необходимо быть авторизованным в системе Битрикс24.

### Тестовый интерфейс

Для тестирования API доступен GUI интерфейс:
```
https://your-domain.bitrix24.ru/local/modules/imena.camunda/lib/UserFields/userfields_api_test_gui.php
```

### Доступные endpoint'ы

| Метод | URL | Описание |
|-------|-----|----------|
| `list` | `?api=1&method=list` | Получение списка всех полей |
| `get` | `?api=1&method=get&fieldId={id}` | Получение конкретного поля |
| `stats` | `?api=1&method=stats` | Статистика по типам полей |
| `types` | `?api=1&method=types` | Информация о типах полей |
| `exists` | `?api=1&method=checkExists&fieldId={id}` | Проверка существования поля |

### Пример использования (PHP)

```php
<?php
// Конфигурация
$apiUrl = 'https://your-domain.bitrix24.ru/local/modules/imena.camunda/lib/UserFields/userfields_api.php';

// Функция для выполнения запроса
function makeApiRequest($method, $params = []) {
    global $apiUrl;
    
    // Формируем URL с параметрами
    $url = $apiUrl . '?api=1&method=' . $method;
    if (!empty($params)) {
        $url .= '&' . http_build_query($params);
    }
    
    $context = stream_context_create([
        'http' => [
            'method' => 'GET',
            'timeout' => 30,
            'ignore_errors' => true
        ],
        'ssl' => [
            'verify_peer' => false,
            'verify_peer_name' => false
        ]
    ]);

    $response = file_get_contents($url, false, $context);
    return json_decode($response, true);
}

// Получение списка всех полей
$result = makeApiRequest('list');
if ($result['status'] === 'success') {
    foreach ($result['data']['userFields'] as $field) {
        echo "Поле: {$field['FIELD_NAME']} (тип: {$field['USER_TYPE_ID']})\n";
    }
}
?>
```

### Пример использования (Python)

```python
import requests
import json

# Конфигурация
API_URL = 'https://your-domain.bitrix24.ru/local/modules/imena.camunda/lib/UserFields/userfields_api.php'

def make_api_request(method, params=None):
    """Выполняет запрос к API"""
    if params is None:
        params = {}
    
    # Формируем URL с параметрами
    url = f"{API_URL}?api=1&method={method}"
    if params:
        url += '&' + '&'.join([f"{k}={v}" for k, v in params.items()])
    
    response = requests.get(url, timeout=30)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"HTTP {response.status_code}: {response.text}")

# Получение списка всех полей
try:
    result = make_api_request('list')
    if result.get('status') == 'success':
        for field in result['data']['userFields']:
            print(f"Поле: {field['FIELD_NAME']} (тип: {field['USER_TYPE_ID']})")
except Exception as e:
    print(f"Ошибка: {e}")
```

### Пример использования (Node.js)

```javascript
const axios = require('axios');

// Конфигурация
const API_URL = 'https://your-domain.bitrix24.ru/local/modules/imena.camunda/lib/UserFields/userfields_api.php';

async function makeApiRequest(method, params = {}) {
    try {
        // Формируем URL с параметрами
        let url = `${API_URL}?api=1&method=${method}`;
        if (Object.keys(params).length > 0) {
            const searchParams = new URLSearchParams(params);
            url += '&' + searchParams.toString();
        }
        
        const response = await axios.get(url, {
            timeout: 30000
        });
        return response.data;
    } catch (error) {
        throw new Error(`HTTP ${error.response?.status}: ${error.message}`);
    }
}

// Получение списка всех полей
async function getFields() {
    try {
        const result = await makeApiRequest('list');
        if (result.status === 'success') {
            result.data.userFields.forEach(field => {
                console.log(`Поле: ${field.FIELD_NAME} (тип: ${field.USER_TYPE_ID})`);
            });
        }
    } catch (error) {
        console.error('Ошибка:', error.message);
    }
}

getFields();
```

### Пример использования (C#)

```csharp
using System;
using System.Net.Http;
using System.Threading.Tasks;
using Newtonsoft.Json;

public class BitrixApiClient
{
    private readonly HttpClient _httpClient;
    private readonly string _webhookUrl;

    public BitrixApiClient(string webhookUrl)
    {
        _webhookUrl = webhookUrl;
        _httpClient = new HttpClient();
    }

    public async Task<dynamic> MakeApiRequest(string method, object parameters = null)
    {
        var content = new FormUrlEncodedContent(parameters?.ToDictionary() ?? new Dictionary<string, string>());
        var response = await _httpClient.PostAsync($"{_webhookUrl}{method}", content);
        
        if (response.IsSuccessStatusCode)
        {
            var json = await response.Content.ReadAsStringAsync();
            return JsonConvert.DeserializeObject(json);
        }
        else
        {
            throw new Exception($"HTTP {response.StatusCode}: {response.ReasonPhrase}");
        }
    }
}

// Использование
var client = new BitrixApiClient("https://your-domain.bitrix24.ru/rest/1/your-webhook/");
var result = await client.MakeApiRequest("imena.camunda.userfields.list");
```

### Пример использования (JavaScript)

```javascript
// Функция для выполнения запроса
async function makeApiRequest(method, params = {}) {
    const response = await fetch(`https://your-domain.bitrix24.ru/rest/1/your-webhook/${method}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams(params)
    });
    
    return await response.json();
}

// Получение списка всех полей
const result = await makeApiRequest('imena.camunda.userfields.list');
if (result.result) {
    result.result.userFields.forEach(field => {
        console.log(`Поле: ${field.FIELD_NAME} (тип: ${field.USER_TYPE_ID})`);
    });
}
```

### Пример использования (Go)

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "net/http"
    "net/url"
)

type BitrixApiClient struct {
    WebhookURL string
    HTTPClient *http.Client
}

func NewBitrixApiClient(webhookURL string) *BitrixApiClient {
    return &BitrixApiClient{
        WebhookURL: webhookURL,
        HTTPClient: &http.Client{},
    }
}

func (c *BitrixApiClient) MakeApiRequest(method string, params map[string]string) (map[string]interface{}, error) {
    data := url.Values{}
    for key, value := range params {
        data.Set(key, value)
    }
    
    resp, err := c.HTTPClient.PostForm(c.WebhookURL+method, data)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    
    body, err := io.ReadAll(resp.Body)
    if err != nil {
        return nil, err
    }
    
    var result map[string]interface{}
    err = json.Unmarshal(body, &result)
    return result, err
}

func main() {
    client := NewBitrixApiClient("https://your-domain.bitrix24.ru/rest/1/your-webhook/")
    result, err := client.MakeApiRequest("imena.camunda.userfields.list", nil)
    if err != nil {
        fmt.Printf("Ошибка: %v\n", err)
        return
    }
    
    if result["result"] != nil {
        fields := result["result"].(map[string]interface{})["userFields"].([]interface{})
        for _, field := range fields {
            fieldMap := field.(map[string]interface{})
            fmt.Printf("Поле: %s (тип: %s)\n", fieldMap["FIELD_NAME"], fieldMap["USER_TYPE_ID"])
        }
    }
}
```

### Пример использования (cURL)

```bash
# Получение списка всех полей
curl "https://your-domain.bitrix24.ru/local/modules/imena.camunda/lib/UserFields/userfields_api.php?api=1&method=list"

# Получение конкретного поля
curl "https://your-domain.bitrix24.ru/local/modules/imena.camunda/lib/UserFields/userfields_api.php?api=1&method=get&fieldId=114"

# Получение статистики
curl "https://your-domain.bitrix24.ru/local/modules/imena.camunda/lib/UserFields/userfields_api.php?api=1&method=stats"
```

### Пример для конкретного домена (bx-dev.eg-holding.ru)

```bash
# Получение списка всех полей
curl "https://bx-dev.eg-holding.ru/local/modules/imena.camunda/lib/UserFields/userfields_api.php?api=1&method=list"

# Получение конкретного поля
curl "https://bx-dev.eg-holding.ru/local/modules/imena.camunda/lib/UserFields/userfields_api.php?api=1&method=get&fieldId=114"

# Получение статистики
curl "https://bx-dev.eg-holding.ru/local/modules/imena.camunda/lib/UserFields/userfields_api.php?api=1&method=stats"
```

## 📖 Справочник методов

### 1. Получение списка всех полей

**Endpoint:** `?api=1&method=list`

**Описание:** Возвращает полный список всех пользовательских полей для объекта TASKS_TASK с их свойствами. Для enum полей дополнительно загружаются значения списка.

**Параметры запроса:** нет

**Пример ответа:**
```json
{
  "status": "success",
  "data": {
    "userFields": [
      {
        "ID": "6",
        "FIELD_NAME": "UF_CRM_TASK",
        "USER_TYPE_ID": "crm",
        "XML_ID": null,
        "SORT": "100",
        "MULTIPLE": "N",
        "MANDATORY": "N",
        "SHOW_FILTER": "N",
        "SHOW_IN_LIST": "Y",
        "EDIT_IN_LIST": "Y",
        "IS_SEARCHABLE": "N",
        "SETTINGS_PARSED": {
          "ENTITY_TYPE": ["LEAD", "CONTACT", "COMPANY", "DEAL"]
        },
        "ENUM_VALUES": [],
        "ENTITY_ID": "TASKS_TASK",
        "HAS_ENUM_VALUES": false
      },
      {
        "ID": "114",
        "FIELD_NAME": "UF_PROJECT",
        "USER_TYPE_ID": "enumeration",
        "XML_ID": null,
        "SORT": "100",
        "MULTIPLE": "Y",
        "MANDATORY": "N",
        "SHOW_FILTER": "S",
        "SHOW_IN_LIST": "Y",
        "EDIT_IN_LIST": "Y",
        "IS_SEARCHABLE": "N",
        "SETTINGS_PARSED": {},
        "ENUM_VALUES": [
          {
            "ID": "453",
            "VALUE": "Волгоград, пр-т Ленина",
            "DEF": "N",
            "SORT": "100",
            "XML_ID": null,
            "IS_DEFAULT": false
          },
          {
            "ID": "454",
            "VALUE": "Волгоград, Казахская",
            "DEF": "N",
            "SORT": "200",
            "XML_ID": null,
            "IS_DEFAULT": false
          }
        ],
        "ENTITY_ID": "TASKS_TASK",
        "HAS_ENUM_VALUES": true
      }
    ],
    "total": 10,
    "entity": "TASKS_TASK"
  }
}
```

**HTTP метод:** GET  
**Content-Type:** application/json

**Структура ответа:**

| Поле | Тип | Описание |
|------|-----|----------|
| `status` | String | Статус ответа ("success" или "error") |
| `data.userFields` | Array | Массив пользовательских полей |
| `data.total` | Integer | Общее количество полей |
| `data.entity` | String | Идентификатор объекта (всегда "TASKS_TASK") |

**Структура поля:**

| Поле | Тип | Описание |
|------|-----|----------|
| `ID` | String | Уникальный идентификатор поля |
| `FIELD_NAME` | String | Название поля (например, "UF_PROJECT") |
| `USER_TYPE_ID` | String | Тип поля (string, enumeration, boolean, crm, etc.) |
| `XML_ID` | String/null | XML идентификатор поля |
| `SORT` | String | Порядок сортировки |
| `MULTIPLE` | String | Поддержка множественных значений (Y/N) |
| `MANDATORY` | String | Обязательное поле (Y/N) |
| `SHOW_FILTER` | String | Показывать в фильтре (Y/N/I/S) |
| `SHOW_IN_LIST` | String | Показывать в списке (Y/N) |
| `EDIT_IN_LIST` | String | Редактировать в списке (Y/N) |
| `IS_SEARCHABLE` | String | Доступно для поиска (Y/N) |
| `SETTINGS` | Object | Настройки поля |
| `SETTINGS_PARSED` | Object | Распарсенные настройки |
| `ENUM_VALUES` | Array | Значения для enum полей |
| `ENTITY_ID` | String | Идентификатор объекта |
| `HAS_ENUM_VALUES` | Boolean | Есть ли enum значения |

**Структура enum значения:**

| Поле | Тип | Описание |
|------|-----|----------|
| `ID` | String | Идентификатор значения |
| `VALUE` | String | Текстовое значение |
| `DEF` | String | Значение по умолчанию (Y/N) |
| `SORT` | String | Порядок сортировки |
| `XML_ID` | String/null | XML идентификатор |
| `IS_DEFAULT` | Boolean | Является ли значением по умолчанию |

### 2. Получение конкретного поля

**Endpoint:** `?api=1&method=get&fieldId={id}`

**Описание:** Возвращает детальную информацию о конкретном пользовательском поле включая значения enum и распарсенные настройки.

**Параметры запроса:**
- `fieldId` (int, обязательный) - ID пользовательского поля

**Пример запроса:**
```php
$result = makeApiRequest('get', ['fieldId' => 114]);
```

**Пример ответа:**
```json
{
  "status": "success",
  "data": {
    "userField": {
      "ID": "114",
      "FIELD_NAME": "UF_PROJECT",
      "USER_TYPE_ID": "enumeration",
      "XML_ID": null,
      "SORT": "100",
      "MULTIPLE": "Y",
      "MANDATORY": "N",
      "SHOW_FILTER": "S",
      "SHOW_IN_LIST": "Y",
      "EDIT_IN_LIST": "Y",
      "IS_SEARCHABLE": "N",
      "SETTINGS_PARSED": {},
      "ENUM_VALUES": [
        {
          "ID": "453",
          "VALUE": "Волгоград, пр-т Ленина",
          "DEF": "N",
          "SORT": "100",
          "XML_ID": null,
          "IS_DEFAULT": false
        }
      ],
      "ENTITY_ID": "TASKS_TASK",
      "HAS_ENUM_VALUES": true
    }
  }
}
```

**Коды ошибок:**
- `400` - Неверный ID пользовательского поля
- `404` - Пользовательское поле не найдено
- `500` - Внутренняя ошибка сервера

### 3. Статистика по типам полей

**Endpoint:** `?api=1&method=stats`

**Описание:** Возвращает общую статистику: количество полей и группировку по типам.

**Параметры запроса:** нет

**Пример ответа:**
```json
{
  "status": "success",
  "data": {
    "stats": {
      "total": 10,
      "by_type": {
        "crm": 1,
        "enumeration": 2,
        "string": 3,
        "boolean": 1,
        "disk_file": 1,
        "iblock_element": 1,
        "mail_message": 1
      },
      "entity": "TASKS_TASK",
      "types_count": 7,
      "most_common_type": "string"
    }
  }
}
```

### 4. Информация о типах полей

**Endpoint:** `?api=1&method=types`

**Описание:** Возвращает описание всех поддерживаемых типов пользовательских полей.

**Параметры запроса:** нет

**Пример ответа:**
```json
{
  "status": "success",
  "data": {
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
      },
      "crm": {
        "name": "CRM",
        "description": "Связь с элементами CRM",
        "supports_multiple": true,
        "supports_enum": false
      },
      "disk_file": {
        "name": "Файл",
        "description": "Файловое поле",
        "supports_multiple": true,
        "supports_enum": false
      },
      "iblock_element": {
        "name": "Элемент инфоблока",
        "description": "Связь с элементами инфоблоков",
        "supports_multiple": true,
        "supports_enum": false
      },
      "mail_message": {
        "name": "Почтовое сообщение",
        "description": "Связь с почтовыми сообщениями",
        "supports_multiple": false,
        "supports_enum": false
      }
    }
  }
}
```

### 5. Проверка существования поля

**Endpoint:** `?api=1&method=checkExists&fieldId={id}`

**Описание:** Проверяет существование пользовательского поля по ID.

**Параметры запроса:**
- `fieldId` (int, обязательный) - ID пользовательского поля

**Пример запроса:**
```php
$result = makeApiRequest('checkExists', ['fieldId' => 114]);
```

**Пример ответа:**
```json
{
  "status": "success",
  "data": {
    "exists": true,
    "fieldId": 114
  }
}
```

## 📊 Типы пользовательских полей

| Тип | Название | Описание | Множественное | Enum значения |
|-----|----------|----------|---------------|---------------|
| `string` | Строка | Текстовое поле | ✅ | ❌ |
| `enumeration` | Список | Выпадающий список с предустановленными значениями | ✅ | ✅ |
| `boolean` | Да/Нет | Логическое поле (да/нет) | ❌ | ❌ |
| `crm` | CRM | Связь с элементами CRM | ✅ | ❌ |
| `disk_file` | Файл | Файловое поле | ✅ | ❌ |
| `iblock_element` | Элемент инфоблока | Связь с элементами инфоблоков | ✅ | ❌ |
| `mail_message` | Почтовое сообщение | Связь с почтовыми сообщениями | ❌ | ❌ |

### Особенности типов

#### Enumeration (Список)
- Поддерживает множественные значения
- Имеет предустановленный список значений
- Значения имеют сортировку и могут быть помечены как значения по умолчанию
- Доступны через поле `ENUM_VALUES` в ответе API

#### CRM
- Связывает задачи с элементами CRM (лиды, контакты, компании, сделки)
- Настройки доступны в поле `SETTINGS_PARSED`
- Поддерживает множественные связи

#### Boolean (Да/Нет)
- Простое логическое поле
- Не поддерживает множественные значения
- Значения: `Y` (да) или `N` (нет)

## 🔧 Примеры интеграции

### Получение списка проектов для фильтрации

```php
<?php
// Получаем поле UF_PROJECT (enumeration)
$result = makeApiRequest('imena.camunda.userfields.get', ['fieldId' => 114]);

if ($result['result']['userField']['USER_TYPE_ID'] === 'enumeration') {
    $projects = [];
    foreach ($result['result']['userField']['ENUM_VALUES'] as $value) {
        $projects[] = [
            'id' => $value['ID'],
            'name' => $value['VALUE']
        ];
    }
    
    // Используем для создания фильтра
    echo "Доступные проекты:\n";
    foreach ($projects as $project) {
        echo "- {$project['name']} (ID: {$project['id']})\n";
    }
}
?>
```

### Создание динамического фильтра (Python)

```python
import requests

def create_dynamic_filter():
    """Создает динамический фильтр на основе пользовательских полей"""
    
    # Получаем все поля
    result = make_api_request('imena.camunda.userfields.list')
    
    if not result.get('result'):
        return []
    
    filters = []
    for field in result['result']['userFields']:
        # Показываем только поля, доступные для фильтрации
        if field['SHOW_FILTER'] in ['Y', 'I', 'S']:
            filter_config = {
                'name': field['FIELD_NAME'],
                'type': field['USER_TYPE_ID'],
                'multiple': field['MULTIPLE'] == 'Y',
                'mandatory': field['MANDATORY'] == 'Y'
            }
            
            # Для enum полей добавляем варианты
            if field['USER_TYPE_ID'] == 'enumeration' and field.get('ENUM_VALUES'):
                filter_config['options'] = [
                    {'id': val['ID'], 'value': val['VALUE']} 
                    for val in field['ENUM_VALUES']
                ]
            
            filters.append(filter_config)
    
    return filters

# Использование
filters = create_dynamic_filter()
for filter_config in filters:
    print(f"Фильтр: {filter_config['name']} (тип: {filter_config['type']})")
```

### Интеграция с внешними системами (Node.js)

```javascript
const axios = require('axios');

class BitrixUserFieldsManager {
    constructor(webhookUrl) {
        this.webhookUrl = webhookUrl;
    }
    
    async getFieldOptions(fieldName) {
        try {
            // Получаем все поля
            const result = await this.makeApiRequest('imena.camunda.userfields.list');
            
            // Ищем нужное поле
            const field = result.result.userFields.find(f => f.FIELD_NAME === fieldName);
            
            if (!field) {
                throw new Error(`Поле ${fieldName} не найдено`);
            }
            
            if (field.USER_TYPE_ID === 'enumeration' && field.ENUM_VALUES) {
                return field.ENUM_VALUES.map(val => ({
                    id: val.ID,
                    value: val.VALUE,
                    isDefault: val.IS_DEFAULT
                }));
            }
            
            return [];
        } catch (error) {
            console.error('Ошибка получения опций поля:', error.message);
            return [];
        }
    }
    
    async validateFieldValue(fieldName, value) {
        const options = await this.getFieldOptions(fieldName);
        
        if (options.length === 0) {
            return true; // Не enum поле, валидация не нужна
        }
        
        // Проверяем, что значение есть в списке опций
        return options.some(option => option.id === value || option.value === value);
    }
    
    async makeApiRequest(method, params = {}) {
        const response = await axios.post(`${this.webhookUrl}${method}`, params, {
            timeout: 30000,
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        });
        return response.data;
    }
}

// Использование
const manager = new BitrixUserFieldsManager('https://your-domain.bitrix24.ru/rest/1/your-webhook/');

// Получаем опции для поля проекта
manager.getFieldOptions('UF_PROJECT').then(options => {
    console.log('Доступные проекты:', options);
});

// Валидируем значение поля
manager.validateFieldValue('UF_PROJECT', '453').then(isValid => {
    console.log('Значение валидно:', isValid);
});
```

### Синхронизация с внешними системами (Go)

```go
package main

import (
    "encoding/json"
    "fmt"
    "log"
    "net/http"
    "net/url"
)

type FieldOption struct {
    ID        string `json:"ID"`
    Value     string `json:"VALUE"`
    IsDefault bool   `json:"IS_DEFAULT"`
}

type UserField struct {
    ID            string        `json:"ID"`
    FieldName     string        `json:"FIELD_NAME"`
    UserTypeID    string        `json:"USER_TYPE_ID"`
    Multiple      string        `json:"MULTIPLE"`
    Mandatory     string        `json:"MANDATORY"`
    ShowFilter    string        `json:"SHOW_FILTER"`
    ShowInList    string        `json:"SHOW_IN_LIST"`
    EnumValues    []FieldOption `json:"ENUM_VALUES"`
    HasEnumValues bool          `json:"HAS_ENUM_VALUES"`
}

type FieldsResponse struct {
    Result struct {
        UserFields []UserField `json:"userFields"`
        Total      int         `json:"total"`
        Entity     string      `json:"entity"`
    } `json:"result"`
}

type BitrixSync struct {
    webhookURL string
    httpClient *http.Client
}

func NewBitrixSync(webhookURL string) *BitrixSync {
    return &BitrixSync{
        webhookURL: webhookURL,
        httpClient: &http.Client{},
    }
}

func (bs *BitrixSync) SyncFieldOptions(fieldName string) ([]FieldOption, error) {
    // Получаем все поля
    result, err := bs.makeApiRequest("imena.camunda.userfields.list", nil)
    if err != nil {
        return nil, err
    }
    
    var fieldsResp FieldsResponse
    if err := json.Unmarshal(result, &fieldsResp); err != nil {
        return nil, err
    }
    
    // Ищем нужное поле
    for _, field := range fieldsResp.Result.UserFields {
        if field.FieldName == fieldName {
            if field.UserTypeID == "enumeration" && field.HasEnumValues {
                return field.EnumValues, nil
            }
            return []FieldOption{}, nil
        }
    }
    
    return nil, fmt.Errorf("поле %s не найдено", fieldName)
}

func (bs *BitrixSync) makeApiRequest(method string, params map[string]string) ([]byte, error) {
    data := url.Values{}
    for key, value := range params {
        data.Set(key, value)
    }
    
    resp, err := bs.httpClient.PostForm(bs.webhookURL+method, data)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    
    // Читаем ответ
    body := make([]byte, 0)
    buffer := make([]byte, 1024)
    for {
        n, err := resp.Body.Read(buffer)
        if n > 0 {
            body = append(body, buffer[:n]...)
        }
        if err != nil {
            break
        }
    }
    
    return body, nil
}

func main() {
    sync := NewBitrixSync("https://your-domain.bitrix24.ru/rest/1/your-webhook/")
    
    options, err := sync.SyncFieldOptions("UF_PROJECT")
    if err != nil {
        log.Fatal(err)
    }
    
    fmt.Printf("Найдено %d опций для поля UF_PROJECT:\n", len(options))
    for _, option := range options {
        fmt.Printf("- %s (ID: %s)\n", option.Value, option.ID)
    }
}
```

### Фильтрация задач по пользовательским полям

```php
<?php
// Получаем все поля для создания динамического фильтра
$result = makeApiRequest('imena.camunda.userfields.list');

$filters = [];
foreach ($result['result']['userFields'] as $field) {
    if ($field['SHOW_FILTER'] === 'Y' || $field['SHOW_FILTER'] === 'S') {
        $filters[] = [
            'name' => $field['FIELD_NAME'],
            'type' => $field['USER_TYPE_ID'],
            'multiple' => $field['MULTIPLE'] === 'Y'
        ];
    }
}

echo "Поля доступные для фильтрации:\n";
foreach ($filters as $filter) {
    echo "- {$filter['name']} (тип: {$filter['type']})\n";
}
?>
```

### Создание динамического интерфейса

```javascript
// Получаем все поля и создаем динамическую форму
async function createDynamicForm() {
    const result = await makeApiRequest('imena.camunda.userfields.list');
    
    const form = document.createElement('form');
    
    result.result.userFields.forEach(field => {
        const div = document.createElement('div');
        div.className = 'form-group';
        
        const label = document.createElement('label');
        label.textContent = field.FIELD_NAME;
        label.setAttribute('for', field.FIELD_NAME);
        
        let input;
        
        switch (field.USER_TYPE_ID) {
            case 'enumeration':
                input = document.createElement('select');
                input.name = field.FIELD_NAME;
                input.multiple = field.MULTIPLE === 'Y';
                
                field.ENUM_VALUES.forEach(enumValue => {
                    const option = document.createElement('option');
                    option.value = enumValue.ID;
                    option.textContent = enumValue.VALUE;
                    input.appendChild(option);
                });
                break;
                
            case 'boolean':
                input = document.createElement('input');
                input.type = 'checkbox';
                input.name = field.FIELD_NAME;
                break;
                
            case 'string':
            default:
                input = document.createElement('input');
                input.type = 'text';
                input.name = field.FIELD_NAME;
                break;
        }
        
        div.appendChild(label);
        div.appendChild(input);
        form.appendChild(div);
    });
    
    document.body.appendChild(form);
}
```

## 🚨 Обработка ошибок

### Стандартные коды ошибок

| Код | Описание | Пример |
|-----|----------|---------|
| `400` | Неверные параметры запроса | Неверный ID поля |
| `401` | Не авторизован | Отсутствует авторизация |
| `404` | Ресурс не найден | Поле не существует |
| `500` | Внутренняя ошибка сервера | Ошибка базы данных |

### Пример обработки ошибок

```php
<?php
$result = makeApiRequest('imena.camunda.userfields.get', ['fieldId' => 999]);

if (isset($result['error'])) {
    $error = $result['error'];
    switch ($error['error_description']) {
        case 'Пользовательское поле с ID 999 не найдено':
            echo "Поле не найдено\n";
            break;
        case 'Неверный ID пользовательского поля':
            echo "Неверный формат ID\n";
            break;
        default:
            echo "Ошибка: " . $error['error_description'] . "\n";
    }
} else {
    // Обработка успешного результата
    $field = $result['result']['userField'];
    echo "Поле найдено: {$field['FIELD_NAME']}\n";
}
?>
```

### JavaScript обработка ошибок

```javascript
async function handleApiCall(method, params = {}) {
    try {
        const result = await makeApiRequest(method, params);
        
        if (result.error) {
            console.error('API Error:', result.error.error_description);
            return null;
        }
        
        return result.result;
    } catch (error) {
        console.error('Network Error:', error.message);
        return null;
    }
}

// Использование
const fields = await handleApiCall('imena.camunda.userfields.list');
if (fields) {
    console.log('Получено полей:', fields.total);
}
```

## 🔍 Отладка и тестирование

### GUI Тестовый интерфейс

Для удобного тестирования API создан веб-интерфейс `userfields_api_test_gui.php`, который:

- ✅ Тестирует все доступные endpoint'ы через веб-интерфейс
- ✅ Выводит детальную информацию о полях в удобном формате
- ✅ Показывает статистику и визуализацию данных
- ✅ Автоматически запускает все тесты при загрузке страницы
- ✅ Демонстрирует примеры использования API

### Доступ к тестовому интерфейсу

```
https://your-domain.bitrix24.ru/local/modules/imena.camunda/lib/UserFields/userfields_api_test_gui.php
```

### Тестовый скрипт

Для тестирования API создан специальный скрипт `test_userfields_api.php`, который:

- Тестирует все доступные endpoint'ы
- Выводит детальную информацию о полях
- Сравнивает результаты с ожидаемыми данными из БД
- Показывает красивые таблицы с результатами

### Запуск тестирования

```bash
php test_userfields_api.php
```

### Проверка соответствия с БД

Скрипт автоматически сравнивает полученные данные с ожидаемыми полями из базы данных:

```php
// Ожидаемые поля (10 шт.)
$expectedFields = [
    6 => ['name' => 'UF_CRM_TASK', 'type' => 'crm'],
    55 => ['name' => 'UF_TASK_WEBDAV_FILES', 'type' => 'disk_file'],
    63 => ['name' => 'UF_MAIL_MESSAGE', 'type' => 'mail_message'],
    114 => ['name' => 'UF_PROJECT', 'type' => 'enumeration'],
    115 => ['name' => 'UF_STRING_TEST', 'type' => 'string'],
    116 => ['name' => 'UF_CAMUNDA_ID_EXTERNAL_TASK', 'type' => 'string'],
    120 => ['name' => 'UF_ORGANIZATION', 'type' => 'iblock_element'],
    121 => ['name' => 'UF_RESULT_EXPECTED', 'type' => 'boolean'],
    122 => ['name' => 'UF_RESULT_QUESTION', 'type' => 'string'],
    124 => ['name' => 'UF_RESULT_ANSWER', 'type' => 'enumeration']
];
```

## 🛠️ Устранение неполадок

### Частые проблемы

#### 1. Ошибка "Method not found"

**Проблема:** API возвращает ошибку "Method not found"

**Решение:**
- Проверьте правильность написания метода
- Убедитесь, что модуль `imena.camunda` установлен и активен
- Проверьте автозагрузку классов в `include.php`

#### 2. Ошибка авторизации

**Проблема:** API возвращает ошибку авторизации

**Решение:**
- Убедитесь, что пользователь авторизован в системе
- Проверьте корректность webhook URL
- Убедитесь, что у пользователя есть права на доступ к задачам

#### 3. Пустой результат

**Проблема:** API возвращает пустой список полей

**Решение:**
- Проверьте, что в системе есть пользовательские поля для TASKS_TASK
- Убедитесь, что поля не скрыты или не удалены
- Проверьте подключение к базе данных

### Логирование

Для отладки можно включить логирование в контроллере:

```php
// В UserFieldsController.php
\Bitrix\Main\Diag\Debug::writeToFile(
    "API Call: " . $method . " with params: " . json_encode($params),
    '',
    '/local/logs/userfields_api.log'
);
```

### Проверка базы данных

Для проверки данных в БД можно выполнить прямой SQL запрос:

```sql
SELECT 
    ID, FIELD_NAME, USER_TYPE_ID, SORT, MULTIPLE, MANDATORY, 
    SHOW_FILTER, SHOW_IN_LIST, EDIT_IN_LIST
FROM b_user_field 
WHERE ENTITY_ID = 'TASKS_TASK' 
ORDER BY SORT ASC, ID ASC;
```

## 📈 Производительность

### Кэширование

API не использует кэширование по умолчанию, но можно добавить кэширование результатов:

```php
// В UserFieldsService.php
use Bitrix\Main\Data\Cache;

public function getFieldsList(array $select = []): Result
{
    $cache = Cache::createInstance();
    $cacheKey = 'userfields_list_' . md5(serialize($select));
    
    if ($cache->initCache(3600, $cacheKey, '/userfields/')) {
        $result = $cache->getVars();
        return $result;
    }
    
    // Получение данных из БД...
    
    if ($cache->startDataCache()) {
        $cache->endDataCache($result);
    }
    
    return $result;
}
```

### Оптимизация запросов

- Используйте конкретные поля в параметре `select` для уменьшения объема данных
- Для больших объемов данных рассмотрите пагинацию
- Индексируйте поля `ENTITY_ID` и `USER_TYPE_ID` в таблице `b_user_field`

## 🔐 Безопасность

### Авторизация

Все методы API требуют авторизации пользователя:

```php
'prefilters' => [
    new \Bitrix\Main\Engine\ActionFilter\Authentication(),
]
```

### Валидация данных

API выполняет валидацию всех входящих параметров:

- Проверка типов данных
- Валидация ID полей
- Санитизация параметров запроса

### Ограничения доступа

- API доступен только для авторизованных пользователей
- Нет дополнительных ограничений по правам доступа
- Все операции только для чтения (безопасно)

## 🚀 Развитие API

### Планируемые улучшения

1. **Пагинация** - для больших списков полей
2. **Фильтрация** - по типу поля, статусу и другим параметрам
3. **Сортировка** - настраиваемая сортировка результатов
4. **Кэширование** - автоматическое кэширование результатов
5. **Версионирование** - поддержка разных версий API

### Расширение функционала

API можно легко расширить для поддержки других объектов:

```php
// Добавление поддержки других объектов
const SUPPORTED_ENTITIES = [
    'TASKS_TASK',
    'CRM_LEAD', 
    'CRM_DEAL',
    'USER'
];

public function getFieldsList(string $entity = 'TASKS_TASK'): Result
{
    if (!in_array($entity, self::SUPPORTED_ENTITIES)) {
        // Ошибка валидации
    }
    
    // Получение полей для указанного объекта
}
```

## 🎯 Лучшие практики

### 1. Кэширование результатов

```python
import time
from functools import lru_cache

class CachedBitrixAPI:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        self._cache = {}
        self._cache_ttl = 3600  # 1 час
    
    @lru_cache(maxsize=128)
    def get_fields_list(self):
        """Кэшированное получение списка полей"""
        return self._make_request('imena.camunda.userfields.list')
    
    def get_field_by_id(self, field_id):
        """Получение конкретного поля с кэшированием"""
        cache_key = f"field_{field_id}"
        
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return cached_data
        
        result = self._make_request('imena.camunda.userfields.get', {'fieldId': field_id})
        self._cache[cache_key] = (result, time.time())
        return result
```

### 2. Обработка ошибок

```javascript
class BitrixAPIError extends Error {
    constructor(message, code, details) {
        super(message);
        this.name = 'BitrixAPIError';
        this.code = code;
        this.details = details;
    }
}

async function makeApiRequest(method, params = {}) {
    try {
        const response = await fetch(`${WEBHOOK_URL}${method}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams(params)
        });
        
        if (!response.ok) {
            throw new BitrixAPIError(
                `HTTP ${response.status}: ${response.statusText}`,
                response.status
            );
        }
        
        const data = await response.json();
        
        if (data.error) {
            throw new BitrixAPIError(
                data.error.error_description || 'Unknown API error',
                data.error.error_code || 'UNKNOWN_ERROR',
                data.error
            );
        }
        
        return data;
    } catch (error) {
        if (error instanceof BitrixAPIError) {
            throw error;
        }
        throw new BitrixAPIError(
            `Network error: ${error.message}`,
            'NETWORK_ERROR',
            { originalError: error.message }
        );
    }
}
```

### 3. Валидация данных

```go
type FieldValidator struct {
    fields map[string]UserField
}

func NewFieldValidator(apiClient *BitrixAPI) *FieldValidator {
    return &FieldValidator{
        fields: make(map[string]UserField),
    }
}

func (fv *FieldValidator) LoadFields() error {
    result, err := fv.apiClient.GetFieldsList()
    if err != nil {
        return err
    }
    
    for _, field := range result.Result.UserFields {
        fv.fields[field.FieldName] = field
    }
    
    return nil
}

func (fv *FieldValidator) ValidateFieldValue(fieldName, value string) error {
    field, exists := fv.fields[fieldName]
    if !exists {
        return fmt.Errorf("поле %s не найдено", fieldName)
    }
    
    switch field.UserTypeID {
    case "enumeration":
        if !fv.validateEnumValue(field, value) {
            return fmt.Errorf("недопустимое значение для поля %s", fieldName)
        }
    case "boolean":
        if value != "Y" && value != "N" {
            return fmt.Errorf("булево поле %s должно иметь значение Y или N", fieldName)
        }
    case "string":
        if len(value) > 255 {
            return fmt.Errorf("строка для поля %s слишком длинная", fieldName)
        }
    }
    
    return nil
}
```

### 4. Мониторинг и логирование

```python
import logging
import time
from functools import wraps

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bitrix_api.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('BitrixAPI')

def log_api_calls(func):
    """Декоратор для логирования вызовов API"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        method_name = func.__name__
        
        logger.info(f"Вызов API: {method_name}")
        
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"API {method_name} выполнен за {duration:.2f}с")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Ошибка API {method_name} после {duration:.2f}с: {e}")
            raise
    return wrapper

class MonitoredBitrixAPI:
    @log_api_calls
    def get_fields_list(self):
        # Реализация получения полей
        pass
    
    @log_api_calls
    def get_field_by_id(self, field_id):
        # Реализация получения поля
        pass
```

### 5. Тестирование

```python
import unittest
from unittest.mock import patch, MagicMock

class TestBitrixUserFieldsAPI(unittest.TestCase):
    def setUp(self):
        self.api = BitrixUserFieldsAPI('https://test.bitrix24.ru/rest/1/test/')
    
    @patch('requests.post')
    def test_get_fields_list_success(self, mock_post):
        # Мокаем успешный ответ
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'result': {
                'userFields': [
                    {
                        'ID': '114',
                        'FIELD_NAME': 'UF_PROJECT',
                        'USER_TYPE_ID': 'enumeration'
                    }
                ],
                'total': 1,
                'entity': 'TASKS_TASK'
            }
        }
        mock_post.return_value = mock_response
        
        result = self.api.get_fields_list()
        
        self.assertEqual(result['result']['total'], 1)
        self.assertEqual(len(result['result']['userFields']), 1)
        self.assertEqual(result['result']['userFields'][0]['FIELD_NAME'], 'UF_PROJECT')
    
    @patch('requests.post')
    def test_get_fields_list_error(self, mock_post):
        # Мокаем ошибку
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_post.return_value = mock_response
        
        with self.assertRaises(BitrixAPIError):
            self.api.get_fields_list()

if __name__ == '__main__':
    unittest.main()
```

## ❓ Часто задаваемые вопросы

### Q: Нужен ли webhook URL для API?

A: Нет, webhook URL не требуется. API работает через тестовый файл и использует авторизацию текущего пользователя Битрикс24. Просто используйте базовый URL с параметрами.

### Q: Можно ли использовать API без авторизации?

A: Нет, все методы API требуют авторизации пользователя. Это обеспечивает безопасность данных.

### Q: Как часто можно вызывать API?

A: Ограничения зависят от настроек вашего Битрикс24. Рекомендуется:
- Не более 1 запроса в секунду для обычных операций
- Использовать кэширование для часто запрашиваемых данных
- Избегать массовых запросов в короткий период

### Q: Поддерживает ли API другие объекты кроме TASKS_TASK?

A: В текущей версии API работает только с объектом TASKS_TASK. В будущих версиях планируется поддержка других объектов (CRM_LEAD, CRM_DEAL, USER).

### Q: Как обрабатывать ошибки API?

A: Все ошибки возвращаются в стандартном формате:
```json
{
  "error": {
    "error_code": "ERROR_CODE",
    "error_description": "Описание ошибки"
  }
}
```

### Q: Можно ли использовать API в production?

A: Да, API готов для production использования. Рекомендуется:
- Настроить мониторинг и логирование
- Использовать кэширование
- Обрабатывать все возможные ошибки
- Тестировать интеграцию перед развертыванием

## 📞 Поддержка

При возникновении проблем:

1. **Проверьте логи ошибок** в `/local/logs/`
2. **Запустите тестовый скрипт** `test_userfields_api.php`
3. **Проверьте соответствие с данными в БД**
4. **Убедитесь в правильности webhook URL и авторизации**
5. **Проверьте версию модуля** `imena.camunda`

### Полезные команды для диагностики

```bash
# Проверка статуса модуля
php -r "echo CModule::IncludeModule('imena.camunda') ? 'Модуль активен' : 'Модуль не найден';"

# Проверка автозагрузки классов
php -r "echo class_exists('ImenaCamunda\\UserFields\\Controller\\UserFieldsController') ? 'Классы загружены' : 'Ошибка загрузки';"

# Тестирование API через cURL
curl "https://your-domain.bitrix24.ru/local/modules/imena.camunda/lib/UserFields/userfields_api.php?api=1&method=list"
```

### Контакты

- **Автор:** #vlikhobabin@gmail.com
- **Версия:** 1.0
- **Дата:** 2025-01-19
- **Лицензия:** MIT

---

## 🎉 Заключение

Данный REST API предоставляет удобный и универсальный способ работы с пользовательскими полями задач в Битрикс24. API спроектирован с учетом современных принципов разработки и поддерживает интеграцию с любыми языками программирования.

### Ключевые преимущества:

- ✅ **Универсальность** - работает с любыми языками программирования
- ✅ **Простота** - понятный REST API с JSON ответами
- ✅ **Надежность** - обработка ошибок и валидация данных
- ✅ **Производительность** - оптимизированные запросы к БД
- ✅ **Безопасность** - авторизация и валидация параметров
- ✅ **Документированность** - подробные примеры и описания

### Следующие шаги:

1. **Изучите примеры** для вашего языка программирования
2. **Настройте webhook** в админке Битрикс24
3. **Протестируйте API** с помощью тестового скрипта
4. **Интегрируйте** в ваше приложение
5. **Настройте мониторинг** и логирование

Удачной разработки! 🚀
