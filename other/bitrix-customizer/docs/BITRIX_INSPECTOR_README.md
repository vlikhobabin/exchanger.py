# Bitrix24 Inspector - Система анализа установки

## Описание

Комплексная система для удаленного анализа и сбора информации об установке Bitrix24 на VPS сервере. Позволяет получить детальную информацию о конфигурации, структуре файлов, модулях и настройках для эффективной разработки кастомизаций.

## Компоненты системы

### 🔍 Основные инспекторы

1. **`bitrix_inspector.py`** - Универсальный инспектор
   - Системная информация (ОС, ресурсы, загрузка)
   - Версия и структура Bitrix24
   - Конфигурация PHP и веб-сервера
   - Структура файлов и права доступа
   - Информация о шаблонах и модулях

2. **`bitrix_tasks_inspector.py`** - Специализированный анализ модуля задач
   - Детальная информация о модуле tasks
   - Пользовательские поля (UF_*)
   - Обработчики событий задач
   - Кастомные компоненты для задач
   - Структура шаблонов с анализом assets

### 📤 Система деплоя

3. **`send_inspector.py`** - Отправка и запуск инспекторов
   - Загрузка скриптов на сервер
   - Удаленное выполнение инспекции
   - Поддержка SSH ключей и паролей
   - Вывод результатов в реальном времени

4. **`get_report.py`** - Получение и анализ отчетов
   - Скачивание отчетов с сервера
   - Автоматический анализ данных
   - Создание краткой сводки
   - Структурированный вывод результатов

### 🚀 Управляющие скрипты

5. **`inspect_bitrix.py`** - Мастер-скрипт полной инспекции
   - Автоматический цикл: отправка → выполнение → получение → анализ
   - Проверка предварительных требований
   - Таймеры и статистика выполнения
   - Обработка ошибок и рекомендации

## Структура отчетов

### 📋 Универсальный отчет (`bitrix_inspection_report.json`)

```json
{
  "timestamp": "2024-01-15T10:30:00",
  "hostname": "server-name",
  "system_info": {
    "os": "Ubuntu 20.04.6 LTS",
    "kernel": "5.4.0-174-generic",
    "load_avg": "0.15 0.12 0.09",
    "disk_usage": "/dev/sda1 20G 8.5G 10G 47%"
  },
  "bitrix_info": {
    "main_path": "/home/bitrix/www",
    "version": "24.300.0",
    "version_date": "2024-01-10 12:00:00",
    "has_settings": true,
    "has_dbconn": true,
    "has_license": true
  },
  "php_info": {
    "version": "PHP 8.1.2-1ubuntu2.14",
    "modules": ["mysqli", "mbstring", "gd", "curl", "..."],
    "settings": {
      "memory_limit": "512M",
      "max_execution_time": "300",
      "upload_max_filesize": "64M"
    }
  },
  "web_server": {
    "apache": "Apache/2.4.41 (Ubuntu)",
    "apache_modules": ["mod_rewrite", "mod_ssl", "..."]
  },
  "file_structure": {
    "bitrix": {
      "exists": true,
      "dirs_count": 15,
      "files_count": 45
    },
    "local": {
      "exists": true,
      "dirs_count": 8,
      "files_count": 12
    }
  },
  "templates": {
    "local": ["bitrix24", "custom_template"],
    "bitrix": ["landing24", "eshop_adapt", "..."]
  },
  "permissions": {
    "/": {"mode": "755", "owner": "bitrix", "group": "bitrix"},
    "bitrix": {"mode": "755", "owner": "bitrix", "group": "bitrix"}
  }
}
```

### 🎯 Отчет по задачам (`bitrix_tasks_inspection_report.json`)

```json
{
  "tasks_module": {
    "exists": true,
    "version": "24.300.0",
    "key_files": [
      "classes/general/task.php",
      "lib/item/task.php"
    ]
  },
  "user_fields": {
    "local/php_interface/init.php": [
      "UF_RESULT_EXPECTED",
      "UF_RESULT_ANSWER",
      "UF_RESULT_QUESTION"
    ]
  },
  "events_handlers": {
    "local/php_interface/init.php": [
      ["OnBeforeTaskUpdate", "checkTaskResultBeforeComplete"],
      ["OnTaskAdd", "logTaskCreation"]
    ]
  },
  "templates_info": {
    "local": {
      "bitrix24": {
        "has_assets": true,
        "js_files": ["global_task_modifier.js"],
        "css_files": ["custom_styles.css"]
      }
    }
  }
}
```

## Установка и настройка

### Предварительные требования

- Python 3.6+
- SSH доступ к серверу Bitrix24
- Настроенная аутентификация (ключ или пароль)
- Рабочий файл `config.json`

### Быстрый старт

1. **Убедитесь в корректности конфигурации:**
   ```bash
   python config-utils/check_auth.py
   ```

2. **Запуск полной инспекции:**
   ```bash
   python inspection-system/inspect_bitrix.py
   ```

3. **Только анализ задач:**
   ```bash
   python inspection-system/send_inspector.py  # отправить bitrix_tasks_inspector.py
   python inspection-system/get_report.py      # получить результат
   ```

### Ручной режим

```bash
# Отправка и запуск основного инспектора
python inspection-system/send_inspector.py

# Получение отчета
python inspection-system/get_report.py

# Отправка специализированного инспектора задач
# (нужно заменить bitrix_inspector.py на bitrix_tasks_inspector.py в send_inspector.py)
```

## Использование результатов

### 📊 Анализ системы

Полученная информация поможет:

- **Понять архитектуру** установки Bitrix24
- **Определить версии** компонентов и модулей
- **Найти пути** для размещения кастомизаций
- **Проверить права доступа** и структуру файлов
- **Выявить существующие** обработчики и компоненты

### 🎯 Разработка кастомизаций

На основе отчетов можно:

1. **Определить правильные пути** для размещения файлов
2. **Найти существующие UF поля** для использования
3. **Понять структуру шаблонов** для интеграции JS/CSS
4. **Выявить конфликты** с существующими обработчиками
5. **Спланировать размещение** новых компонентов

### 📋 Примеры использования

#### Размещение обработчика событий задач

Из отчета видно:
```
"init_files": {
  "local": {"exists": true, "has_task_handlers": false}
}
```

**Решение:** Можно добавить обработчик в `/local/php_interface/init.php`

#### Интеграция JavaScript

Из отчета видно:
```
"templates_info": {
  "local": {
    "bitrix24": {
      "has_assets": true,
      "js_files": ["existing_script.js"]
    }
  }
}
```

**Решение:** Разместить новый скрипт в `/local/templates/bitrix24/assets/js/`

#### Работа с пользовательскими полями

Из отчета видно:
```
"user_fields": {
  "local/php_interface/init.php": [
    "UF_RESULT_EXPECTED",
    "UF_RESULT_ANSWER"
  ]
}
```

**Решение:** Поля уже существуют, можно использовать в коде

## Структура файлов проекта

```
bitrix-customizer/
├── �� Инспекторы
│   ├── inspection-system/
│   │   ├── bitrix_inspector.py           # Основной инспектор
│   │   ├── bitrix_tasks_inspector.py     # Инспектор модуля задач
│   │   ├── send_inspector.py             # Отправка на сервер
│   │   ├── get_report.py                 # Получение отчетов
│   │   └── inspect_bitrix.py             # Мастер-скрипт
├── 🎯 Кастомизация
│   └── task-customization/
│       ├── deploy.py                     # Деплой
│       └── ...
├── ⚙️ Утилиты
│   └── config-utils/
│       ├── setup.py                      # Настройка
│       ├── check_auth.py                 # Проверка auth
│       └── config.example.json           # Пример конфигурации
├── 📚 Документация
│   └── docs/
│       ├── BITRIX_INSPECTOR_README.md    # Эта документация
│       ├── README.md                     # Основная документация
│       └── SECURITY.md                   # Рекомендации по безопасности
├── 📋 Отчеты
│   └── reports/                          # Папка с отчетами
│       ├── bitrix_inspection_report_YYYYMMDD_HHMMSS.json
│       └── bitrix_inspection_report_YYYYMMDD_HHMMSS_summary.txt
├── ⚙️ Конфигурация
│   ├── config.json                       # Настройки подключения
│   └── .gitignore                        # Игнорируемые файлы
```

## Безопасность

### 🔐 Важные принципы

1. **Инспекторы НЕ читают** конфиденциальные данные
2. **Пароли и ключи НЕ передаются** в отчетах
3. **Используется только чтение** системной информации
4. **Нет изменений** в конфигурации Bitrix24

### 🛡️ Рекомендации

- Храните `config.json` в безопасном месте
- Не добавляйте приватные ключи в репозиторий  
- Регулярно проверяйте отчеты перед передачей третьим лицам
- Используйте принцип минимальных привилегий для SSH доступа

## Устранение проблем

### ❌ Типичные ошибки

**Ошибка:** `❌ Файл ключа не найден`
**Решение:** Проверьте путь к ключу в `config.json`

**Ошибка:** `❌ Bitrix24 не найден`
**Решение:** Проверьте пути в `bitrix_inspector.py` → `find_bitrix_paths()`

**Ошибка:** `❌ SSH клиент не найден`
**Решение:** Установите PuTTY или OpenSSH

**Ошибка:** `❌ Таймаут выполнения`
**Решение:** Увеличьте timeout в скриптах или проверьте нагрузку сервера

### 🔧 Диагностика

```bash
# Проверка подключения
python config-utils/check_auth.py

# Тест отправки простого файла
python task-customization/deploy.py

# Проверка SSH подключения вручную
ssh -i C:/Users/User/.ssh/key.ppk root@31.129.105.41
```

## Расширение функциональности

### 🔧 Добавление новых инспекторов

1. Создайте новый файл `custom_inspector.py`
2. Наследуйтесь от базового класса или создайте аналогичную структуру
3. Добавьте специфичные методы анализа
4. Модифицируйте `send_inspector.py` для отправки нового инспектора

### 📊 Добавление новых метрик

1. Добавьте новый метод в класс инспектора
2. Обновите структуру отчета
3. Добавьте обработку в `get_report.py`
4. Обновите документацию

## Техническая поддержка

При возникновении проблем:

1. Запустите `python config-utils/check_auth.py` для диагностики
2. Проверьте логи выполнения скриптов
3. Убедитесь в корректности `config.json`
4. Проверьте доступность сервера и права доступа

---

**Версия документации:** 1.0  
**Последнее обновление:** 2024-01-15  
**Совместимость:** Bitrix24 коробочная версия, Python 3.6+ 