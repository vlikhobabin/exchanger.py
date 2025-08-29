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
8. **Встраивает ответственных** в serviceTask как camunda:properties (если есть JSON файл)
9. **Исправляет порядок элементов** внутри BPMN узлов согласно спецификации
10. **Устраняет конфликты default flow** в эксклюзивных шлюзах
11. **Очищает диаграммные элементы** для удаленных объектов
12. **Сохраняет форматирование** и читаемость XML

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
├── bpmn_converter.py           # Основной класс BPMNConverter
├── convert.py                  # Скрипт-обертка для запуска
├── checklist_parser.py         # Парсер чек-листов из StormBPMN
├── bitrix_checklist_integration.py  # Интеграция чек-листов с Bitrix24
└── BPMN_CONVERTER_README.md    # Документация
```

## 📋 Парсинг чек-листов из StormBPMN

### 🎯 Назначение

Новый функционал для извлечения чек-листов из описаний активностей в StormBPMN диаграммах и автоматического создания их в задачах Bitrix24.

### ✨ Возможности

#### 📖 Поддерживаемые форматы чек-листов:

1. **🌟 Оптимальный HTML формат** (рекомендуемый):
   ```html
   <p>ЧЕКЛИСТ: Название чек-листа</p>
   <ul>
     <li>Первый пункт</li>
     <li>Второй пункт</li>
   </ul>
   ```

2. **🔗 Загрузка из Bitrix24** (новая функция):
   ```html
   <p>ЧЕКЛИСТ: <a href="https://bx.eg-holding.ru/tasks/task/view/1566/">ссылка на шаблонную задачу</a></p>
   ```
   - Автоматически загружает чек-листы из указанной задачи Bitrix24
   - Использует API методы: `tasks.task.get` и `task.checklistitem.getlist`
   - Сохраняет иерархическую структуру чек-листов

3. **📝 Текстовый формат**:
   ```
   ЧЕКЛИСТ: Название
   • Первый пункт
   • Второй пункт
   ```

4. **🔄 Совместимость со старыми форматами**:
   - `** Название ** [список]` (двойные звездочки)
   - `@ Название [параграфы]` (символ @)
   - `# Название [списки]` (символ #)
   - `– Название [элементы]` (тире)

#### 🛡️ Строгие правила парсинга:

- ✅ Пункты должны идти **сразу** после заголовка чек-листа
- ❌ Чек-листы без пунктов **игнорируются**
- ❌ Пункты без заголовка "ЧЕКЛИСТ:" **игнорируются**
- ❌ Посторонний текст между заголовком и пунктами **не допускается**

### 🚀 Использование

#### 1. Парсинг чек-листов из JSON файла:

```bash
python checklist_parser.py "Процессы УУ. Модель для автоматизации_assignees.json"
```

**Результат:**
```json
[
  {
    "element_id": "Activity_1nptpu5",
    "element_name": "Проведение выручки по договорам ДДУ и ДКП в УУ",
    "checklists": [
      {
        "title": "Запрос данных",
        "items": [
          {"text": "брони", "is_complete": false},
          {"text": "ДДУ и ДКП", "is_complete": false}
        ]
      }
    ]
  }
]
```

#### 2. Интеграция с Bitrix24 (добавление чек-листов к задачам):

```bash
python bitrix_checklist_integration.py 1234 assignees.json Activity_123
```

#### 3. Программное использование:

```python
from checklist_parser import ChecklistParser
from bitrix_checklist_integration import add_checklists_from_file

# Парсинг чек-листов
parser = ChecklistParser()
checklists = parser.parse_assignees_file("assignees.json")

# Добавление к задаче Bitrix24
success = add_checklists_from_file(
    task_id=1234, 
    assignees_json_file="assignees.json",
    element_id="Activity_123"
)
```

### 🔗 Интеграция с существующими модулями

#### ⚙️ Автоматическое использование конфигурации:

Парсер автоматически интегрируется с конфигурацией Bitrix24:

```python
# Автоматический импорт из task-creator.py
from consumers.bitrix.config import bitrix_config

# Использование настроек
webhook_url = bitrix_config.webhook_url
timeout = bitrix_config.request_timeout
```

#### 🔄 API методы (совместимые с существующими модулями):

- `tasks.task.get` (GET) - получение информации о задаче
- `task.checklistitem.getlist` (GET) - получение чек-листов 
- `tasks.task.checklist.add` (POST) - добавление пунктов чек-листа

### 📊 Пример полного процесса:

1. **StormBPMN**: Создается диаграмма с активностями, содержащими чек-листы в описании
2. **get_diagram_assignees.py**: Получает JSON с ответственными и описаниями
3. **checklist_parser.py**: Извлекает чек-листы из описаний (локально или из Bitrix24)
4. **convert.py**: Конвертирует BPMN в формат Camunda
5. **task-creator.py**: Создает задачи в Bitrix24
6. **bitrix_checklist_integration.py**: Добавляет чек-листы к созданным задачам

### 📋 Требования для парсинга чек-листов:

- Python 3.6+
- requests (для загрузки из Bitrix24)
- Конфигурация Bitrix24 (автоматически используется из task-creator.py при наличии)
- Альтернативно: `BITRIX_WEBHOOK_URL` и `BITRIX_REQUEST_TIMEOUT` из переменных окружения

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
- `<camunda:properties>` с информацией об ответственных в serviceTask

### Встраивание ответственных

Если рядом с BPMN файлом найден JSON файл с ответственными (с суффиксом `_assignees.json`), конвертер автоматически встраивает информацию об ответственных в соответствующие serviceTask элементы.

**Пример встраивания:**
```xml
<bpmn:serviceTask id="Activity_14qyrmj" name="Отправить сообщение" camunda:type="external" camunda:topic="bitrix_create_task">
  <bpmn:extensionElements>
    <camunda:properties>
      <camunda:property name="assigneeName" value="Рук.отд. инж.коммуникаций" />
      <camunda:property name="assigneeId" value="15299256" />
    </camunda:properties>
  </bpmn:extensionElements>
  <bpmn:incoming>Flow_1</bpmn:incoming>
  <bpmn:outgoing>Flow_2</bpmn:outgoing>
</bpmn:serviceTask>
```

**Логика встраивания:**
1. Анализируется JSON файл с ответственными
2. Для каждого ответственного находится соответствующий serviceTask по `elementId`
3. Создается (или дополняется) секция `<bpmn:extensionElements>`
4. Добавляется `<camunda:properties>` с двумя свойствами:
   - `assigneeName` - имя ответственного
   - `assigneeId` - ID ответственного

**Примечания:**
- Если для элемента назначено несколько ответственных, встраивается только первый
- Если JSON файл не найден, конвертация продолжается без ответственных
- Если есть ошибки в JSON файле, они логируются, но не прерывают конвертацию

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

### Успешная конвертация BPMN:
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

### Успешный парсинг чек-листов:
```
✅ Используется конфигурация Bitrix24 из task-creator.py
🔗 Bitrix24 URL: https://bx.eg-holding.ru/rest/1/...
🔗 Загружаем чек-листы из задачи Bitrix24: 1566
📋 Запрос чек-листов для задачи 1566...
📝 Получено 14 элементов чек-листов для задачи 1566
✅ Загружено 4 чек-листов из задачи 1566

[STDOUT содержит JSON с чек-листами]
```

### Успешная интеграция чек-листов с Bitrix24:
```
🚀 Добавление чек-листов к задаче 1234 из файла assignees.json
   Фильтр по element_id: Activity_123
✅ Используется конфигурация Bitrix24 из task-creator.py
🔄 Обрабатываем чек-листы для элемента: Проведение выручки по договорам ДДУ и ДКП в УУ
📋 Добавляем чек-лист 'Запрос данных' с 2 пунктами в задачу 1234
  ✅ Добавлен пункт: брони
  ✅ Добавлен пункт: ДДУ и ДКП
📋 Добавляем чек-лист 'Доначисление по УУ' с 1 пунктами в задачу 1234
  ✅ Добавлен пункт: брони
✅ Все чек-листы добавлены в задачу 1234: 10/10
✅ Чек-листы успешно добавлены к задаче 1234
```

### Ошибки:
```
🔄 BPMN Converter - StormBPMN → Camunda
==================================================
❌ Файл не найден: nonexistent.bpmn
```

```
⚠️ BITRIX_WEBHOOK_URL не настроен, пропускаем загрузку из задачи 1566
[]
```

```
❌ Не удалось извлечь Task ID из URL: https://invalid-url.com
[]
```

## 🚨 Важные замечания

### 🔄 BPMN конвертация:
1. **Резервные копии**: Всегда делайте резервные копии исходных файлов перед конвертацией
2. **Валидация**: После конвертации проверьте результат в Camunda Modeler
3. **Тестирование**: Протестируйте сконвертированные процессы перед развертыванием
4. **Кодировка**: Все файлы сохраняются в UTF-8 кодировке

### 📋 Парсинг чек-листов:
1. **Формат описаний**: Используйте рекомендуемый HTML формат для максимальной совместимости
2. **Bitrix24 доступ**: Убедитесь, что webhook имеет права на чтение задач и чек-листов
3. **Валидация ссылок**: Проверяйте корректность ссылок на шаблонные задачи Bitrix24
4. **Кодировка**: Все текстовые данные обрабатываются в UTF-8
5. **API лимиты**: Учитывайте ограничения Bitrix24 API при массовых операциях

## 🐛 Устранение неполадок

### 🔄 Проблемы BPMN конвертации:

#### Проблема: "Файл не найден"
**Решение**: Проверьте правильность пути к файлу и его существование

#### Проблема: "XML parsing error"
**Решение**: Убедитесь, что исходный файл является корректным XML/BPMN файлом

#### Проблема: "Permission denied"
**Решение**: Проверьте права доступа к директории и файлам

### 📋 Проблемы парсинга чек-листов:

#### Проблема: "BITRIX_WEBHOOK_URL не настроен"
**Решение**: 
- Настройте переменную окружения `BITRIX_WEBHOOK_URL`
- Или убедитесь, что доступна конфигурация task-creator.py

#### Проблема: "401 Client Error: Unauthorized"
**Решение**: 
- Проверьте корректность webhook URL в Bitrix24
- Убедитесь, что webhook активен и имеет права на чтение задач

#### Проблема: "Не удалось извлечь Task ID из URL"
**Решение**: 
- Используйте полные ссылки на задачи Bitrix24
- Формат: `https://bx.eg-holding.ru/workgroups/group/43/tasks/task/view/1566/`

#### Проблема: "Получено 0 чек-листов из задачи"
**Решение**: 
- Убедитесь, что в шаблонной задаче Bitrix24 есть чек-листы
- Проверьте права webhook на чтение чек-листов
- Убедитесь, что чек-листы не пустые

#### Проблема: "Чек-листы не найдены в описании"
**Решение**: 
- Проверьте формат чек-листов в описании активности
- Используйте рекомендуемый HTML формат: `<p>ЧЕКЛИСТ: Название</p><ul><li>Пункт</li></ul>`
- Убедитесь, что между заголовком и пунктами нет постороннего текста

#### Проблема: "Ошибка добавления чек-листа к задаче"
**Решение**: 
- Проверьте права webhook на создание чек-листов
- Убедитесь, что задача с указанным ID существует
- Проверьте корректность данных чек-листа

## 📞 Поддержка

### 🔄 При проблемах с BPMN конвертацией:
1. Проверьте журнал ошибок в выводе скрипта
2. Убедитесь в корректности исходного BPMN файла
3. Проверьте права доступа к файлам и директориям

### 📋 При проблемах с чек-листами:
1. **Диагностика конфигурации**:
   ```bash
   python -c "from task-creator.py.consumers.bitrix.config import bitrix_config; print(bitrix_config.webhook_url)"
   ```

2. **Проверка доступа к Bitrix24**:
   ```bash
   curl -X GET "ваш_webhook_url/tasks.task.get.json?taskId=1566"
   ```

3. **Тестирование парсера**:
   ```bash
   python checklist_parser.py test_file.json 2>errors.log
   ```

4. **Анализ логов**: Все диагностические сообщения выводятся в stderr
   - ✅ - успешные операции
   - ⚠️ - предупреждения
   - ❌ - ошибки
   - 🔗 - сетевые операции

### 📊 Полезные команды диагностики:
```bash
# Проверка структуры JSON файла
python -m json.tool assignees.json

# Тестирование API Bitrix24
python -c "import requests; print(requests.get('webhook_url/user.current.json').json())"

# Проверка прав webhook в Bitrix24
python -c "import requests; r=requests.get('webhook_url/tasks.task.list.json'); print('OK' if r.status_code == 200 else 'ERROR')"
``` 