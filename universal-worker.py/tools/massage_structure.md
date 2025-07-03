📨 СООБЩЕНИЕ #1
├─ Delivery Tag: 1
├─ Exchange: camunda.external.tasks
├─ Routing Key: bitrix24.bitrix_create_task
├─ Redelivered: Да
├─ Content Type: application/json
├─ Timestamp: 2025-07-03 13:16:24
├─ Headers: {'camunda_topic': 'bitrix_create_task', 'process_instance_id': 'bae9056d-57f6-11f0-a3a6-00b436387543', 'target_system': 'bitrix24', 'task_id': 'bae97aa5-57f6-11f0-a3a6-00b436387543'}
└─ Содержимое:
   {
  "task_id": "bae97aa5-57f6-11f0-a3a6-00b436387543",
  "topic": "bitrix_create_task",
  "system": "bitrix24",
  "variables": {
    "": null,
    "Input_2khodeq": "TestInputValue"
  },
  "process_instance_id": "bae9056d-57f6-11f0-a3a6-00b436387543",
  "activity_id": "Activity_1u7kiry",
  "activity_instance_id": "Activity_1u7kiry:bae97aa2-57f6-11f0-a3a6-00b436387543",
  "worker_id": "universal-worker",
  "retries": null,
  "created_time": "2025-07-03T10:16:05.792+0000",
  "priority": 0,
  "tenant_id": null,
  "business_key": null,
  "timestamp": 1751537784811,
  "metadata": {
    "extensionProperties": {
      "TestExtensionProperties": "TestValueExtensionProperties"
    },
    "fieldInjections": {
      "TestFieldInjections": "TestValueFieldInjections"
    },
    "inputParameters": {
      "Input_2khodeq": "TestInputValue"
    },
    "outputParameters": {
      "Output_11dfutm": "TestOutputValue"
    },
    "activityInfo": {
      "id": "Activity_1u7kiry",
      "name": "Выполнить задачу в Bitrix24",
      "type": "external",
      "topic": "bitrix_create_task"
    }
  }
}

📨 СООБЩЕНИЕ #2
├─ Delivery Tag: 2
├─ Exchange: camunda.external.tasks
├─ Routing Key: bitrix24.bitrix_create_task
├─ Redelivered: Да
├─ Content Type: application/json
├─ Timestamp: 2025-07-03 13:20:59
├─ Headers: {'camunda_topic': 'bitrix_create_task', 'process_instance_id': None, 'target_system': 'bitrix24', 'task_id': None}
└─ Содержимое:
   {
  "task_id": null,
  "topic": "bitrix_create_task",
  "system": "bitrix24",
  "variables": {
    "": null,
    "Input_2khodeq": "TestInputValue"
  },
  "process_instance_id": null,
  "activity_id": null,
  "activity_instance_id": null,
  "worker_id": null,
  "retries": null,
  "created_time": null,
  "priority": 0,
  "tenant_id": null,
  "business_key": null,
  "timestamp": 1751538059306,
  "metadata": {
    "extensionProperties": {
      "TestExtensionProperties": "TestValueExtensionProperties"
    },
    "fieldInjections": {
      "TestFieldInjections": "TestValueFieldInjections"
    },
    "inputParameters": {
      "Input_2khodeq": "TestInputValue"
    },
    "outputParameters": {
      "Output_11dfutm": "TestOutputValue"
    },
    "activityInfo": {
      "id": "Activity_1u7kiry",
      "name": "Выполнить задачу в Bitrix24",
      "type": "external",
      "topic": "bitrix_create_task"
    }
  }
}