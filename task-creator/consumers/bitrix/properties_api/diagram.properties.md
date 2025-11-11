imena.camunda.diagram.properties.list

**Файл:** `/local/modules/imena.camunda/lib/Rest/DiagramPropertiesHandler.php`

**Назначение:** Возвращает список параметров диаграммы Storm, связанной с процессом Camunda.

**Параметры запроса:**

- `camundaProcessId` — обязательный ключ процесса Camunda (например: `Process_0jsi939`)

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
        "CAMUNDA_PROCESS_ID": "Process_0jsi939"
      },
      "properties": [
        {
          "ID": 101,
          "CODE": "EMPLOYEE_EMAIL",
          "NAME": "Электронная почта сотрудника",
          "TYPE": "string",
          "IS_REQUIRED": "Y",
          "SORT": 100,
          "DEFAULT_VALUE": null
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

GET /rest/1/tip76z85stzjop28/imena.camunda.diagram.properties.list?camundaProcessId=Process_qunad56t0 HTTP/1.1
Accept: */*
Accept-Encoding: deflate, gzip
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 YaBrowser/25.8.0.0 Safari/537.36
Host: bx-dev.eg-holding.ru

Ответ: 
```json
{
    "result": {
        "success": true,
        "data": {
            "diagram": {
                "ID": "e3935fcf-2e14-41be-ad08-c56d01b17122",
                "TITLE": "Camunda test2",
                "TYPE": "BPMN",
                "PROCESS_TYPE": "ASIS",
                "STATUS": "NEW",
                "CAMUNDA_PROCESS_ID": "Process_qunad56t0",
                "CAMUNDA_VERSION": "2"
            },
            "properties": [{
                "ID": "1",
                "CODE": "CUSTOMER_NAME",
                "NAME": "Имя клиента",
                "TYPE": "string",
                "IS_REQUIRED": "Y",
                "SORT": "100",
                "DESCRIPTION": "ФИО сотрудника",
                "DEFAULT_VALUE": "Иванов Иван Иванович",
                "ENUM_OPTIONS": [],
                "CREATED_AT": {},
                "UPDATED_AT": {}
            }, {
                "ID": "2",
                "CODE": "APPROVAL_REQUIRED",
                "NAME": "Требуется согласование",
                "TYPE": "boolean",
                "IS_REQUIRED": "N",
                "SORT": "200",
                "DESCRIPTION": "Флаг необходимости согласования",
                "DEFAULT_VALUE": false,
                "ENUM_OPTIONS": false,
                "CREATED_AT": {},
                "UPDATED_AT": {}
            }, {
                "ID": "3",
                "CODE": "DEADLINE_DATE",
                "NAME": "Плановая дата завершения",
                "TYPE": "date",
                "IS_REQUIRED": "N",
                "SORT": "300",
                "DESCRIPTION": "Дата завершения процесса",
                "DEFAULT_VALUE": false,
                "ENUM_OPTIONS": false,
                "CREATED_AT": {},
                "UPDATED_AT": {}
            }, {
                "ID": "7",
                "CODE": "START_DATE",
                "NAME": "Дата начала",
                "TYPE": "date",
                "IS_REQUIRED": "Y",
                "SORT": "500",
                "DESCRIPTION": "Дата начала командировки",
                "DEFAULT_VALUE": "",
                "ENUM_OPTIONS": [],
                "CREATED_AT": {},
                "UPDATED_AT": {}
            }, {
                "ID": "8",
                "CODE": "END_DATE",
                "NAME": "Дата завершения",
                "TYPE": "date",
                "IS_REQUIRED": "Y",
                "SORT": "600",
                "DESCRIPTION": "Дата завершения командировки",
                "DEFAULT_VALUE": "",
                "ENUM_OPTIONS": [],
                "CREATED_AT": {},
                "UPDATED_AT": {}
            }, {
                "ID": "9",
                "CODE": "COMPANY",
                "NAME": "Организация",
                "TYPE": "enum",
                "IS_REQUIRED": "N",
                "SORT": "700",
                "DESCRIPTION": "Организация, в которой работает сотрудник",
                "DEFAULT_VALUE": "",
                "ENUM_OPTIONS": ["ИМЕНА, ООО", "ИМЕНА. УПРАВЛЕНИЕ  ПРОЕКТАМИ, ООО"],
                "CREATED_AT": {},
                "UPDATED_AT": {}
            }],
            "meta": {
                "camundaProcessId": "Process_qunad56t0",
                "propertyCount": 6
            }
        }
    },
    "time": {
        "start": 1762792988.816858,
        "finish": 1762792988.846827,
        "duration": 0.029968976974487305,
        "processing": 0.005474090576171875,
        "date_start": "2025-11-10T11:43:08-05:00",
        "date_finish": "2025-11-10T11:43:08-05:00"
    }
}
```