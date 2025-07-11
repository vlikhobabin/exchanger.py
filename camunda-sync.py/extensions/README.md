# 🔧 BPMN Converter Extensions

Система расширений для кастомной обработки конкретных BPMN процессов.

## 📖 Описание

Расширения позволяют создавать специфичную логику обработки для отдельных процессов без изменения основного кода конвертера. Каждый процесс может иметь свой собственный модуль с кастомными преобразованиями.

## 📁 Структура

```
extensions/
├── README.md                      # Эта документация
├── __init__.py                    # Инициализация модуля
└── {Process_ID}/                  # Папка для конкретного процесса
    ├── __init__.py                # Инициализация процесса
    └── process_extension.py       # Основной модуль расширения
```

## 🎯 Принцип работы

1. **Определение процесса**: Конвертер извлекает ID процесса из BPMN XML (`<bpmn:process id="...">`)
2. **Поиск расширения**: Ищет папку `extensions/{Process_ID}/process_extension.py`
3. **Загрузка модуля**: Динамически импортирует модуль расширения
4. **Предобработка**: Вызывает `pre_process()` ДО стандартных преобразований
5. **Стандартная обработка**: Выполняет все стандартные алгоритмы конвертации
6. **Постобработка**: Вызывает `post_process()` ПОСЛЕ стандартных преобразований

## 📝 Создание расширения

### 1. Создание структуры

```bash
# Создать папку для процесса (замените YOUR_PROCESS_ID на реальный ID)
mkdir -p extensions/YOUR_PROCESS_ID

# Создать файлы
touch extensions/YOUR_PROCESS_ID/__init__.py
touch extensions/YOUR_PROCESS_ID/process_extension.py
```

### 2. Шаблон модуля расширения

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Расширение для процесса: YOUR_PROCESS_ID
Название: Ваше описание процесса
"""

import xml.etree.ElementTree as ET
from typing import Optional, Any


def pre_process(root: ET.Element, converter) -> None:
    """
    Предобработка схемы процесса (выполняется ДО стандартных преобразований)
    
    Args:
        root: Корневой элемент BPMN XML
        converter: Экземпляр BPMNConverter для доступа к методам и namespaces
    """
    print("🔧 [EXTENSION] Предобработка процесса YOUR_PROCESS_ID...")
    
    # ВАШ КОД ПРЕДОБРАБОТКИ ЗДЕСЬ
    
    print("   ✅ Предобработка завершена")


def post_process(root: ET.Element, converter) -> None:
    """
    Постобработка схемы процесса (выполняется ПОСЛЕ стандартных преобразований)
    
    Args:
        root: Корневой элемент BPMN XML (уже обработанный стандартными алгоритмами)
        converter: Экземпляр BPMNConverter для доступа к методам и namespaces
    """
    print("🔧 [EXTENSION] Постобработка процесса YOUR_PROCESS_ID...")
    
    # ВАШ КОД ПОСТОБРАБОТКИ ЗДЕСЬ
    
    print("   ✅ Постобработка завершена")


# Метаданные расширения (опционально)
EXTENSION_INFO = {
    "process_id": "YOUR_PROCESS_ID",
    "process_name": "Название вашего процесса",
    "version": "1.0.0",
    "description": "Описание кастомных преобразований",
    "author": "Ваше имя",
    "created": "2024-01-15"
}
```

## 🛠️ Доступные возможности

### Через параметр `converter`:

- `converter.namespaces` - словарь с BPMN namespaces
- `converter._make_request()` - вспомогательные методы конвертера
- `converter.assignees_data` - данные об ответственных (если загружены)
- `converter.removed_elements` - множество удаленных элементов
- `converter.removed_flows` - множество удаленных потоков

### Через параметр `root`:

- Корневой элемент BPMN XML для прямой модификации
- Доступ ко всем элементам схемы через XPath

## 💡 Примеры использования

### Предобработка: Добавление кастомных атрибутов

```python
def pre_process(root: ET.Element, converter) -> None:
    # Найти все userTask и добавить специальные атрибуты
    user_tasks = root.findall('.//bpmn:userTask', converter.namespaces)
    for task in user_tasks:
        task_name = task.get('name', '')
        if 'согласование' in task_name.lower():
            task.set('camunda:assignee', 'approver-group')
            task.set('camunda:candidateGroups', 'managers')
```

### Постобработка: Настройка сгенерированных serviceTask

```python
def post_process(root: ET.Element, converter) -> None:
    # Добавить retry политику ко всем внешним задачам
    service_tasks = root.findall('.//bpmn:serviceTask', converter.namespaces)
    for task in service_tasks:
        if task.get(f'{{{converter.namespaces["camunda"]}}}type') == 'external':
            task.set(f'{{{converter.namespaces["camunda"]}}}asyncBefore', 'true')
            task.set(f'{{{converter.namespaces["camunda"]}}}retries', '3')
```

### Работа с условными выражениями

```python
def post_process(root: ET.Element, converter) -> None:
    # Изменить логику условий для специфичных потоков
    for flow in root.findall('.//bpmn:sequenceFlow', converter.namespaces):
        flow_name = flow.get('name', '').lower()
        if flow_name == 'специальное условие':
            # Удалить старое условие
            old_condition = flow.find('bpmn:conditionExpression', converter.namespaces)
            if old_condition is not None:
                flow.remove(old_condition)
            
            # Добавить новое условие
            condition = ET.SubElement(flow, f'{{{converter.namespaces["bpmn"]}}}conditionExpression')
            condition.set(f'{{{converter.namespaces["xsi"]}}}type', 'bpmn:tFormalExpression')
            condition.text = '${customVariable == "special_value"}'
```

## 🚨 Важные замечания

1. **Обработка ошибок**: Расширения выполняются в try-catch блоках, ошибки не прерывают основную конвертацию
2. **Порядок выполнения**: pre_process → стандартные алгоритмы → post_process
3. **Изоляция**: Каждый процесс имеет свое собственное расширение
4. **Совместимость**: Расширения должны быть совместимы с основными алгоритмами конвертера

## 📊 Существующие расширения

- `Process_1d4oa6g46/` - Разработка и получение разрешительной документации

## 🔍 Отладка

Все операции расширений логируются с префиксом `[EXTENSION]` для простой идентификации в выводе конвертера.

Пример вывода:
```
🔍 Обнаружен процесс с ID: Process_1d4oa6g46
🔧 Загружаем расширение для процесса Process_1d4oa6g46...
   📋 Название: Разработка и получение разрешительной документации
   📦 Версия: 1.0.0
   ✅ Расширение загружено успешно
🔧 [EXTENSION] Предобработка процесса Process_1d4oa6g46...
   ✅ Предобработка завершена
... стандартная обработка ...
🔧 [EXTENSION] Постобработка процесса Process_1d4oa6g46...
   ✅ Постобработка завершена
``` 