# YAML Конфигурация для start_process.py

## Обзор

Скрипт `start_process.py` теперь поддерживает запуск процессов Camunda с параметрами из YAML-файлов конфигурации. Это упрощает управление сложными конфигурациями и позволяет переиспользовать настройки.

## Основные возможности

- ✅ Загрузка всех параметров процесса из YAML файла
- ✅ Автоматическое определение типов переменных
- ✅ Поддержка явного указания типов переменных (формат Camunda)
- ✅ Поддержка сложных JSON структур и массивов
- ✅ Приоритет параметров командной строки над YAML
- ✅ Возможность переопределения любых параметров из командной строки

## Структура YAML конфигурации

```yaml
# Обязательные поля
process_key: "MyProcess"           # Ключ процесса в Camunda

# Опциональные поля
version: 2                         # Версия процесса
business_key: "ORDER-123"          # Бизнес-ключ экземпляра
description: "Описание процесса"   # Описание (только для документации)

# Переменные процесса
variables:
  # Простые типы (автоматическое определение)
  userName: "John"                 # String
  amount: 100                      # Integer
  price: 99.99                     # Double
  approved: true                   # Boolean
  
  # Явное указание типа (формат Camunda)
  customField:
    value: "some value"
    type: "String"
    
  # JSON объекты и массивы
  complexData:
    key1: "value1"
    key2: 42
    nested:
      subKey: "subValue"
```

## Способы использования

### 1. Запуск только с YAML конфигурацией

```bash
# Все параметры берутся из файла
python start_process.py --config my_process.yaml
```

### 2. Комбинирование YAML и параметров командной строки

```bash
# YAML + переопределение business key
python start_process.py --config my_process.yaml --business-key "OVERRIDE-123"

# YAML + дополнительные переменные
python start_process.py --config my_process.yaml --variables "priority=high,urgent=true"

# YAML + указание конкретной версии
python start_process.py --config my_process.yaml --version 3
```

### 3. Использование process_key из командной строки

```bash
# Если в YAML нет process_key или хотим использовать другой
python start_process.py MyOtherProcess --config variables_only.yaml
```

## Примеры конфигураций

### Простая конфигурация

```yaml
# simple_process.yaml
process_key: "SimpleProcess"
business_key: "SIMPLE-001"
variables:
  userName: "Alice"
  department: "IT"
  approved: true
```

### Конфигурация с комплексными переменными

```yaml
# complex_process.yaml
process_key: "OrderProcessing"
version: 2
business_key: "ORDER-2024-001"
description: "Обработка заказа с комплексными данными"

variables:
  # Переменные с явным типом
  orderId:
    value: "12345"
    type: "String"
    
  totalAmount:
    value: "1599.99"
    type: "String"
  
  # Автоматические типы
  itemCount: 3
  hasDiscount: true
  customerLevel: "premium"
  
  # JSON структуры
  orderItems:
    - name: "Laptop"
      sku: "LAP-001"
      price: 1200.00
      quantity: 1
    - name: "Mouse"
      sku: "MOU-001" 
      price: 25.99
      quantity: 2
      
  customerData:
    name: "John Smith"
    email: "john@example.com"
    preferences:
      newsletter: true
      sms: false
    address:
      street: "123 Main St"
      city: "New York"
      country: "USA"
```

### Конфигурация только с переменными

```yaml
# variables_only.yaml
# Без process_key - будет взят из командной строки
variables:
  environment: "production"
  logLevel: "INFO"
  timeout: 300
  features:
    - "feature1"
    - "feature2"
    - "feature3"
```

## Типы переменных

### Автоматическое определение типов

Система автоматически определяет типы на основе значений YAML:

- `string: "text"` → String
- `number: 42` → Integer  
- `decimal: 3.14` → Double
- `boolean: true` → Boolean
- `object: {...}` → Json
- `array: [...]` → Json

### Явное указание типов

Для точного контроля используйте формат Camunda:

```yaml
variables:
  customField:
    value: "any value"
    type: "String"       # String, Integer, Double, Boolean, Json
```

### Поддерживаемые типы Camunda

- `String` - строковые значения
- `Integer` - целые числа
- `Double` - числа с плавающей точкой
- `Boolean` - логические значения (true/false)
- `Json` - JSON объекты и массивы

## Приоритет параметров

Параметры из командной строки **всегда имеют приоритет** над параметрами из YAML:

1. **Командная строка** (высший приоритет)
2. **YAML файл** (базовые значения)

Пример:
```yaml
# config.yaml
business_key: "YAML-123"
variables:
  env: "staging"
```

```bash
# Итоговый business_key будет "CMD-456"
python start_process.py --config config.yaml --business-key "CMD-456"
```

## Команды для диагностики

### Просмотр конфигурации без запуска

```bash
# Показать что будет отправлено (dry run)
python start_process.py --config my_process.yaml --dry-run
```

### Просмотр информации о процессе

```bash
# Информация о процессе без запуска
python start_process.py --config my_process.yaml --info
```

### Просмотр всех версий процесса

```bash
# Список всех версий процесса
python start_process.py --config my_process.yaml --list-versions
```

## Обработка ошибок

### Типичные ошибки и решения

1. **Файл не найден**
   ```
   FileNotFoundError: Конфигурационный файл 'config.yaml' не найден
   ```
   → Проверьте путь к файлу

2. **Некорректный YAML**
   ```
   ValueError: Ошибка парсинга YAML файла
   ```
   → Проверьте синтаксис YAML

3. **Отсутствует process_key**
   ```
   ValueError: В конфигурации отсутствует обязательное поле 'process_key'
   ```
   → Добавьте process_key в YAML или укажите в командной строке

## Лучшие практики

### 1. Структура файлов
```
project/
├── configs/
│   ├── production/
│   │   ├── order_process.yaml
│   │   └── payment_process.yaml
│   ├── staging/
│   │   └── test_process.yaml
│   └── examples/
│       └── process_config_example.yaml
```

### 2. Именование файлов
- Используйте описательные имена: `order_processing.yaml`
- Группируйте по окружениям: `prod_payment.yaml`, `test_payment.yaml`
- Включайте версию при необходимости: `process_v2.yaml`

### 3. Документирование
```yaml
# order_processing.yaml
# Описание: Процесс обработки заказов в e-commerce системе
# Автор: Team Name
# Последнее обновление: 2024-01-15
# Версия процесса: 2

process_key: "OrderProcessing"
description: "Полный цикл обработки заказа от создания до доставки"
# ...
```

### 4. Переменные окружения в YAML
```yaml
# Для разных окружений используйте разные файлы или переопределяйте параметры
variables:
  apiUrl: "https://api.production.com"  # В prod_config.yaml
  # apiUrl: "https://api.staging.com"   # В staging_config.yaml
```

## Примеры использования в CI/CD

### GitHub Actions
```yaml
- name: Deploy Process
  run: |
    python start_process.py --config configs/production/deploy.yaml \
                           --business-key "DEPLOY-${{ github.run_id }}" \
                           --variables "gitCommit=${{ github.sha }},branch=${{ github.ref_name }}"
```

### Разные окружения
```bash
# Продакшн
python start_process.py --config configs/prod/order.yaml

# Тестовое окружение с переопределением
python start_process.py --config configs/prod/order.yaml \
                       --variables "environment=test,debugMode=true"
```

## Совместимость

- ✅ Полная обратная совместимость с существующими командами
- ✅ Все старые параметры работают как раньше
- ✅ YAML - дополнительная опция, не заменяет существующую функциональность

## Зависимости

- `PyYAML >= 6.0.1` (уже включена в requirements.txt)

---

Для дополнительных примеров смотрите файл `process_config_example.yaml`. 