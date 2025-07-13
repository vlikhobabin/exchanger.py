# Система анализа и инспекции Bitrix24

## Описание

Комплексная система для удаленного анализа и сбора информации об установке Bitrix24 на VPS сервере. Позволяет получить детальную информацию о конфигурации, структуре файлов, модулях и настройках для эффективной разработки кастомизаций.

## Возможности

- ✅ **Универсальная инспекция** системы и Bitrix24
- ✅ **Специализированный анализ** модуля задач
- ✅ **Автоматическая отправка** и запуск инспекторов
- ✅ **Детальные отчеты** в JSON формате
- ✅ **Краткие сводки** для быстрого ознакомления
- ✅ **Безопасное развертывание** с резервным копированием
- ✅ **Анализ рисков** и рекомендации

## Структура компонентов

```
inspection-system/
├── 🔍 Инспекторы
│   ├── bitrix_inspector.py           # Универсальный инспектор
│   ├── bitrix_tasks_inspector.py     # Специализированный анализ задач
│   └── file_analyzer.py              # Анализатор файлов
├── 📤 Система управления
│   ├── send_inspector.py             # Отправка инспекторов на сервер
│   ├── get_report.py                 # Получение отчетов
│   ├── inspect_bitrix.py             # Мастер-скрипт полной инспекции
│   └── safe_deployment_manager.py    # Безопасное развертывание
├── 🔄 Резервное копирование
│   ├── enhanced_backup_manager.py    # Улучшенная система резервирования
│   └── enhanced_restore_manager.py   # Система восстановления
├── 📋 Отчеты
│   └── reports/                      # Папка с отчетами
├── 📝 Конфигурация
│   └── example_deployment_config.json # Пример конфигурации развертывания
└── 📄 README.md                      # Документация
```

## Использование

### Быстрая инспекция (рекомендуется)

```bash
# Полная автоматическая инспекция
python inspect_bitrix.py

# Результат: полный анализ установки за 1-2 минуты
```

### Пошаговая инспекция

```bash
# 1. Отправка инспектора на сервер
python send_inspector.py

# 2. Получение и анализ отчета
python get_report.py

# Автоматически создаст:
# - Детальный JSON отчет
# - Краткую сводку
# - Рекомендации по кастомизации
```

### Специализированный анализ задач

```bash
# Отправка специализированного инспектора
# (замените bitrix_inspector.py на bitrix_tasks_inspector.py в send_inspector.py)
python send_inspector.py
python get_report.py
```

## Типы инспекций

### 🔍 Универсальная инспекция

**Собирает информацию о:**
- Системные данные (ОС, ресурсы, загрузка)
- Версия и структура Bitrix24
- Конфигурация PHP и веб-сервера
- Структура файлов и права доступа
- Информация о шаблонах и модулях
- Места для размещения кастомизаций

### 🎯 Специализированная инспекция задач

**Анализирует:**
- Детальную информацию о модуле tasks
- Пользовательские поля (UF_*)
- Обработчики событий задач
- Кастомные компоненты для задач
- Структуру шаблонов с анализом assets

### 📊 Анализ файлов

**Определяет:**
- Файлы для резервного копирования
- Риски модификации
- Зависимости между файлами
- Приоритеты развертывания

## Структура отчетов

### 📋 Универсальный отчет

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "hostname": "server-name",
  "system_info": {
    "os": "Ubuntu 20.04.6 LTS",
    "kernel": "5.4.0-174-generic",
    "load_avg": "0.15 0.12 0.09"
  },
  "bitrix_info": {
    "main_path": "/home/bitrix/www",
    "version": "24.300.0",
    "version_date": "2024-01-10 12:00:00"
  },
  "customization_files": {
    "local/php_interface/init.php": {
      "exists": true,
      "type": "init_file",
      "size": 1024
    }
  },
  "customization_places": {
    "local/components": {
      "exists": true,
      "recommended": true,
      "writable": true
    }
  }
}
```

### 🎯 Отчет по задачам

```json
{
  "tasks_module": {
    "exists": true,
    "version": "24.300.0",
    "key_files": ["classes/general/task.php"]
  },
  "user_fields": {
    "local/php_interface/init.php": [
      "UF_RESULT_EXPECTED",
      "UF_RESULT_ANSWER"
    ]
  },
  "events_handlers": {
    "local/php_interface/init.php": [
      ["OnBeforeTaskUpdate", "checkTaskResultBeforeComplete"]
    ]
  }
}
```

## Безопасное развертывание

### Автоматическое развертывание

```bash
# Безопасное развертывание с резервным копированием
python safe_deployment_manager.py deploy config.json

# Этапы:
# 1. Предварительная проверка
# 2. Системный анализ
# 3. Создание резервной копии
# 4. Проверка развертывания
# 5. Развертывание
# 6. Пост-проверка
# 7. Очистка
```

### Расширенное резервное копирование

```bash
# Создание умной резервной копии
python enhanced_backup_manager.py create --inspection-report reports/latest.json

# Восстановление с проверкой целостности
python enhanced_restore_manager.py full_system_restore backup_session_id
```

## Результаты анализа

### 📁 Где найти результаты

```
reports/
├── bitrix_inspection_report_20240115_143022.json    # Подробный отчет
├── bitrix_inspection_report_20240115_143022_summary.txt    # Краткая сводка
└── bitrix_tasks_inspection_report_20240115_143022.json    # Отчет по задачам
```

### 💡 Практические применения

#### Перед добавлением обработчика событий
```json
// Из отчета
"events_handlers": {
  "local/php_interface/init.php": [
    ["OnBeforeTaskUpdate", "existingHandler"]
  ]
}
```
**Решение:** Добавить свой обработчик в тот же файл

#### Перед размещением JavaScript
```json
// Из отчета
"templates_info": {
  "local": {
    "bitrix24": {
      "has_assets": true,
      "js_files": ["existing_script.js"]
    }
  }
}
```
**Решение:** Разместить в `/local/templates/bitrix24/assets/js/`

## Настройка и безопасность

### Предварительные требования

- Python 3.6+
- SSH доступ к серверу Bitrix24
- Настроенная аутентификация (ключ или пароль)
- Конфигурация в `../config.json`

### Безопасность

1. **Инспекторы НЕ читают** конфиденциальные данные
2. **Пароли и ключи НЕ передаются** в отчетах
3. **Используется только чтение** системной информации
4. **Нет изменений** в конфигурации Bitrix24

## Устранение проблем

### Типичные ошибки

**Ошибка:** `❌ Bitrix24 не найден`
**Решение:** Проверьте пути в `bitrix_inspector.py` → `find_bitrix_paths()`

**Ошибка:** `❌ SSH клиент не найден`
**Решение:** Установите PuTTY или OpenSSH

**Ошибка:** `❌ Таймаут выполнения`
**Решение:** Увеличьте timeout в скриптах

### Диагностика

```bash
# Проверка подключения
python ../config-utils/check_auth.py

# Тест отправки файла
python send_inspector.py

# Проверка SSH вручную
ssh -i ~/.ssh/key.ppk root@server.com
```

## Интеграция с другими системами

### Автоматическое использование

```python
# Из других модулей
from inspection_system.bitrix_inspector import BitrixInspector

inspector = BitrixInspector()
success = inspector.save_report()
```

### Использование в CI/CD

```bash
# Проверка перед развертыванием
python inspection-system/inspect_bitrix.py
python backup-restore-system/backup_manager.py create
python task-completion-blocker/deploy_and_test.py
```

## Примеры использования

### Анализ новой установки

```bash
# 1. Полная инспекция
python inspect_bitrix.py

# 2. Анализ отчета
# Изучите reports/latest_summary.txt

# 3. Планирование кастомизации
# Используйте рекомендации из отчета
```

### Безопасная модификация

```bash
# 1. Анализ текущего состояния
python inspect_bitrix.py

# 2. Создание резервной копии
python enhanced_backup_manager.py create

# 3. Развертывание изменений
python safe_deployment_manager.py deploy config.json

# 4. Проверка результата
python inspect_bitrix.py
```

---

**Версия:** 2.0  
**Совместимость:** Bitrix24 коробочная версия, Python 3.6+  
**Зависимости:** SSH клиент, права доступа к серверу 