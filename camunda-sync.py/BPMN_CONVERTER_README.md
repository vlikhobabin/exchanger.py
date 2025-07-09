# 🔄 BPMN Converter - StormBPMN → Camunda

Инструмент для автоматической конвертации BPMN схем из формата **StormBPMN** в формат **Camunda**.

## 📖 Описание

Данный инструмент выполняет комплексное преобразование BPMN диаграмм согласно требованиям Camunda Platform:

### ✅ Что делает конвертер:

1. **Добавляет Camunda namespaces** (`xmlns:camunda`, `xmlns:xsi`)
2. **Обновляет атрибуты процесса** (`isExecutable="true"`, Camunda-специфичные атрибуты)
3. **Удаляет collaboration секции** (участники, аннотации, группы)
4. **Удаляет ВСЕ промежуточные события** (`intermediateCatchEvent`, `intermediateThrowEvent`)
5. **Перенаправляет потоки** вокруг удаленных элементов
6. **Преобразует задачи в serviceTask** (все типы: `userTask`, `manualTask`, `callActivity` и др.)
   - Добавляет атрибуты: `camunda:type="external"`, `camunda:topic="bitrix_create_task"`
7. **Добавляет условные выражения** к потокам с названиями "да"/"нет"
8. **Исправляет порядок элементов** внутри BPMN узлов согласно спецификации
9. **Устраняет конфликты default flow** в эксклюзивных шлюзах
10. **Очищает диаграммные элементы** для удаленных объектов
11. **Сохраняет форматирование** и читаемость XML

### ❌ Что НЕ изменяется:

- ID процессов (остаются оригинальными)
- exporterVersion (остается из исходной схемы)
- default атрибуты в exclusiveGateway (сохраняются)
- endEvent элементы (не удаляются)
- Названия процессов (берутся из исходной схемы)

## 🚀 Использование

### Простой запуск

```bash
python convert.py <input_file.bpmn>
```

### Примеры

```bash
# Конвертация файла в текущей директории
python convert.py my_process.bpmn

# Конвертация файла из родительской директории
python convert.py ../diagram.bpmn

# Конвертация файла с полным путем
python convert.py /path/to/your/process.bpmn
```

### Результат

Скрипт создаст новый файл в той же папке, что и исходный, с префиксом `camunda_`:

```
Исходный файл: my_process.bpmn
Результат:     camunda_my_process.bpmn
```

## 📁 Структура файлов

```
camunda-sync.py/
├── bpmn_converter.py      # Основной класс BPMNConverter
├── convert.py             # Скрипт-обертка для запуска
└── BPMN_CONVERTER_README.md  # Документация
```

## 🔧 Технические детали

### Обрабатываемые элементы

#### 🗑️ Удаляемые элементы:
- `<bpmn:collaboration>` со всем содержимым
- `<bpmn:intermediateCatchEvent>` (все типы)
- `<bpmn:intermediateThrowEvent>` (все типы)
- `<bpmn:messageEventDefinition>`
- `<bpmn:timerEventDefinition>`
- Связанные `<bpmn:sequenceFlow>`
- Диаграммные элементы (`<bpmndi:BPMNShape>`, `<bpmndi:BPMNEdge>`)

#### 🔄 Преобразуемые элементы:
- `<bpmn:userTask>` → `<bpmn:serviceTask>`
- `<bpmn:manualTask>` → `<bpmn:serviceTask>`
- `<bpmn:callActivity>` → `<bpmn:serviceTask>`
- `<bpmn:businessRuleTask>` → `<bpmn:serviceTask>`
- `<bpmn:scriptTask>` → `<bpmn:serviceTask>`
- `<bpmn:sendTask>` → `<bpmn:serviceTask>`
- `<bpmn:receiveTask>` → `<bpmn:serviceTask>`
- `<bpmn:task>` → `<bpmn:serviceTask>`

#### ➕ Добавляемые элементы:
- Camunda namespaces в корневой элемент
- `camunda:historyTimeToLive="1"` в процесс  
- `camunda:type="external"` и `camunda:topic="bitrix_create_task"` в serviceTask
- `<bpmn:conditionExpression>` для потоков "да"/"нет"

### Логика перенаправления потоков

Когда удаляется промежуточное событие:

1. **Находятся входящие потоки** (`targetRef` = ID события)
2. **Находятся исходящие потоки** (`sourceRef` = ID события)
3. **Входящие потоки перенаправляются** на цели исходящих потоков
4. **Все связанные потоки удаляются**

Пример:
```
Task_A → IntermediateEvent → Task_B
```
Становится:
```
Task_A → Task_B
```

### Условные выражения

Для потоков с названиями "да" или "нет" добавляются условия:

```xml
<!-- Для name="да" -->
<bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">${result == "ok"}</bpmn:conditionExpression>

<!-- Для name="нет" -->
<bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">${result != "ok"}</bpmn:conditionExpression>
```

### Исправление порядка элементов

Согласно BPMN спецификации, элементы внутри узлов должны следовать определенному порядку:

#### Для обычных элементов процесса:
1. `<extensionElements>` (если есть)
2. `<ioSpecification>` (если есть)  
3. `<property>` (если есть)
4. `<dataInputAssociation>` / `<dataOutputAssociation>` (если есть)
5. `<resourceRole>` (если есть)
6. `<loopCharacteristics>` (если есть)
7. Все `<incoming>` элементы
8. Все `<outgoing>` элементы
9. Остальные элементы

#### Для sequenceFlow:
1. `<extensionElements>` (если есть)
2. `<conditionExpression>` (если есть)
3. Остальные элементы

**Неправильно:**
```xml
<bpmn:exclusiveGateway id="Gateway_1">
  <bpmn:incoming>Flow_1</bpmn:incoming>
  <bpmn:outgoing>Flow_2</bpmn:outgoing>
  <bpmn:incoming>Flow_3</bpmn:incoming> <!-- ❌ incoming после outgoing -->
</bpmn:exclusiveGateway>
```

**Правильно:**
```xml
<bpmn:exclusiveGateway id="Gateway_1">
  <bpmn:incoming>Flow_1</bpmn:incoming>
  <bpmn:incoming>Flow_3</bpmn:incoming>
  <bpmn:outgoing>Flow_2</bpmn:outgoing>
</bpmn:exclusiveGateway>
```

### Исправление конфликтов default flow

В BPMN диаграммах **эксклюзивные шлюзы (exclusiveGateway)** могут иметь **default flow** - поток по умолчанию, который выполняется, если не выполнилось ни одно условие других исходящих потоков.

#### ❌ Проблема:
По стандарту BPMN, **default flow не должен иметь условие**. Это приводит к ошибке:
```
ENGINE-09005 Exclusive Gateway 'Gateway_1' has outgoing sequence flow 'Flow_1' 
which is the default flow but has a condition too.
```

#### ✅ Решение:
Конвертер автоматически **убирает атрибут `default`** у шлюзов, если соответствующий поток имеет условие.

**Было (неправильно):**
```xml
<bpmn:exclusiveGateway id="Gateway_1" default="Flow_YES">
  <bpmn:outgoing>Flow_YES</bpmn:outgoing>
  <bpmn:outgoing>Flow_NO</bpmn:outgoing>
</bpmn:exclusiveGateway>

<bpmn:sequenceFlow id="Flow_YES" sourceRef="Gateway_1" targetRef="Task_1">
  <bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">${result == "ok"}</bpmn:conditionExpression>
</bpmn:sequenceFlow>
```

**Стало (правильно):**
```xml
<bpmn:exclusiveGateway id="Gateway_1">
  <bpmn:outgoing>Flow_YES</bpmn:outgoing>
  <bpmn:outgoing>Flow_NO</bpmn:outgoing>
</bpmn:exclusiveGateway>

<bpmn:sequenceFlow id="Flow_YES" sourceRef="Gateway_1" targetRef="Task_1">
  <bpmn:conditionExpression xsi:type="bpmn:tFormalExpression">${result == "ok"}</bpmn:conditionExpression>
</bpmn:sequenceFlow>
```

## 🛠️ Требования

- Python 3.6+
- Стандартная библиотека Python (xml.etree.ElementTree, pathlib, и др.)

Никаких дополнительных зависимостей не требуется.

## 📊 Примеры вывода

### Успешная конвертация:
```
🔄 BPMN Converter - StormBPMN → Camunda
==================================================
📖 Парсинг файла: my_process.bpmn
🔄 Применение преобразований...
   📝 Добавление Camunda namespaces...
   🔧 Обновление атрибутов процесса...
      Process name: Разработка и получение разрешительной документации
   🗑️ Удаление collaboration секции...
      Collaboration секция удалена
   🎯 Удаление промежуточных событий...
      Найдено промежуточных событий: 12
      Перенаправление потоков для Event_1abc123: входящих=1, исходящих=1
        Поток Flow_1def456 перенаправлен на Task_1ghi789
   🔄 Преобразование задач в serviceTask...
      userTask 'Проверка документов' → serviceTask (camunda:type="external", camunda:topic="bitrix_create_task")
      manualTask 'Ручная проверка' → serviceTask (camunda:type="external", camunda:topic="bitrix_create_task")
      Преобразовано задач: 15
   ➕ Добавление условных выражений...
      Добавлено условие для потока 'да': ${result == "ok"}
      Добавлено условие для потока 'нет': ${result != "ok"}
      Добавлено условных выражений: 8
   🔧 Исправление порядка элементов...
      Исправлен порядок элементов в 23 узлах
   🧹 Очистка диаграммных элементов...
      Удалено диаграммных элементов: 25
💾 Сохранение результата: camunda_my_process.bpmn
✅ Конвертация завершена успешно!

🎉 Конвертация завершена успешно!
📁 Исходный файл: my_process.bpmn
📁 Результат: camunda_my_process.bpmn
📊 Размер исходного файла: 245,678 байт
📊 Размер результата: 198,432 байт
```

### Ошибка:
```
🔄 BPMN Converter - StormBPMN → Camunda
==================================================
❌ Файл не найден: nonexistent.bpmn
```

## 🚨 Важные замечания

1. **Резервные копии**: Всегда делайте резервные копии исходных файлов перед конвертацией
2. **Валидация**: После конвертации проверьте результат в Camunda Modeler
3. **Тестирование**: Протестируйте сконвертированные процессы перед развертыванием
4. **Кодировка**: Все файлы сохраняются в UTF-8 кодировке

## 🐛 Устранение неполадок

### Проблема: "Файл не найден"
**Решение**: Проверьте правильность пути к файлу и его существование

### Проблема: "XML parsing error"
**Решение**: Убедитесь, что исходный файл является корректным XML/BPMN файлом

### Проблема: "Permission denied"
**Решение**: Проверьте права доступа к директории и файлам

## 📞 Поддержка

При возникновении проблем:
1. Проверьте журнал ошибок в выводе скрипта
2. Убедитесь в корректности исходного BPMN файла
3. Проверьте права доступа к файлам и директориям 