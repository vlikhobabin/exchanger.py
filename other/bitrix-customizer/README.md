# Bitrix24 Customizer - Комплексная система кастомизации

## Описание

Bitrix24 Customizer - это мощная экосистема инструментов для безопасной разработки, анализа и развертывания кастомизаций для Bitrix24 коробочной версии. Система включает в себя инструменты для анализа установки, резервного копирования, конфигурирования и развертывания модификаций.

## Архитектура системы

```
bitrix-customizer/
├── 📊 inspection-system/      # Система анализа и инспекции Bitrix24
├── 📦 backup-restore-system/  # Резервное копирование и восстановление
├── ⚙️ config-utils/           # Утилиты конфигурации
├── 🚫 task-completion-blocker/ # Блокировщик завершения задач
├── 📁 old-task-customization/ # Старые версии (deprecated)
├── 📄 config.json            # Главная конфигурация проекта
├── 📄 requirements.txt       # Зависимости Python
└── 📄 README.md              # Эта документация
```

## Основные возможности

### 🔍 Анализ и инспекция
- Автоматический анализ установки Bitrix24
- Детальные отчеты о системе и конфигурации
- Специализированный анализ модуля задач
- Рекомендации по размещению кастомизаций

### 🔧 Безопасное развертывание
- Автоматическое резервное копирование перед изменениями
- Проверка целостности файлов
- Пошаговое восстановление при ошибках
- Безопасная настройка конфигурации

### 🎯 Кастомизация задач
- Блокировка завершения задач без результата
- Модификация интерфейса задач
- Интеграция с пользовательскими полями
- Автоматическое сохранение результатов

## Подсистемы

### 📊 [Система анализа и инспекции](inspection-system/README.md)

**Назначение:** Комплексный анализ установки Bitrix24

**Основные компоненты:**
- `bitrix_inspector.py` - универсальный инспектор системы
- `bitrix_tasks_inspector.py` - анализ модуля задач
- `safe_deployment_manager.py` - безопасное развертывание
- `enhanced_backup_manager.py` - улучшенная система резервирования

**Использование:**
```bash
# Полная инспекция установки
python inspection-system/inspect_bitrix.py

# Безопасное развертывание
python inspection-system/safe_deployment_manager.py deploy config.json
```

### 📦 [Система резервного копирования](backup-restore-system/README.md)

**Назначение:** Безопасное резервное копирование критических файлов

**Основные компоненты:**
- `backup_manager.py` - создание резервных копий
- `restore_manager.py` - восстановление файлов

**Использование:**
```bash
# Создание резервной копии
python backup-restore-system/backup_manager.py create

# Восстановление системы
python backup-restore-system/restore_manager.py full
```

### ⚙️ [Утилиты конфигурации](config-utils/README.md)

**Назначение:** Настройка и диагностика конфигурации проекта

**Основные компоненты:**
- `setup.py` - интерактивная настройка
- `check_auth.py` - проверка аутентификации
- `config.example.json` - шаблон конфигурации

**Использование:**
```bash
# Настройка проекта
python config-utils/setup.py

# Проверка настроек
python config-utils/check_auth.py
```

### 🚫 [Блокировщик завершения задач](task-completion-blocker/README.md)

**Назначение:** Кастомизация модуля задач с требованием результата

**Основные компоненты:**
- `enhanced_task_modifier.js` - JavaScript модификатор
- `task_completion_blocker.php` - PHP обработчик событий
- `deploy_task_blocker.py` - система развертывания

**Использование:**
```bash
# Развертывание блокировщика
python task-completion-blocker/deploy_and_test.py
```

## Быстрый старт

### 1. Первоначальная настройка

```bash
# Настройка конфигурации
python config-utils/setup.py

# Проверка подключения
python config-utils/check_auth.py
```

### 2. Анализ системы

```bash
# Полная инспекция Bitrix24
python inspection-system/inspect_bitrix.py

# Результат: детальный отчет о системе
```

### 3. Развертывание кастомизаций

```bash
# Безопасное развертывание с резервным копированием
python task-completion-blocker/deploy_and_test.py
```

## Рабочий процесс

### Безопасная разработка

1. **Анализ** - инспекция установки Bitrix24
2. **Планирование** - анализ отчетов и планирование изменений
3. **Резервирование** - создание резервных копий
4. **Развертывание** - безопасное внедрение изменений
5. **Тестирование** - проверка функциональности
6. **Мониторинг** - отслеживание работы системы

### Рекомендуемая последовательность

```bash
# 1. Настройка окружения
python config-utils/setup.py

# 2. Анализ системы
python inspection-system/inspect_bitrix.py

# 3. Создание резервной копии
python backup-restore-system/backup_manager.py create

# 4. Развертывание изменений
python task-completion-blocker/deploy_and_test.py

# 5. Проверка результата
python inspection-system/inspect_bitrix.py
```

## Конфигурация

### Структура `config.json`

```json
{
  "server": {
    "host": "31.129.105.41",
    "user": "root",
    "auth_method": "key",
    "key_file": "C:/Users/username/.ssh/privete-key.ppk",
    "path": "/home/bitrix/www/local/templates/bitrix24/assets/js/"
  },
  "bitrix_field_config": {
    "UF_RESULT_ANSWER": {
      "type": "list",
      "values": {
        "yes": 26,
        "no": 27
      }
    }
  },
  "deployment": {
    "files": ["global_task_modifier.js"],
    "backup_on_deploy": true
  }
}
```

## Безопасность

### Принципы безопасности

1. **Всегда создавайте резервные копии** перед изменениями
2. **Используйте SSH-ключи** вместо паролей
3. **Храните ключи в безопасном месте** (`~/.ssh/`)
4. **Тестируйте на dev-сервере** перед продакшном
5. **Не добавляйте ключи в репозиторий**

### Аутентификация

- **SSH-ключи** (рекомендуется): поддержка PPK и OpenSSH форматов
- **Пароли**: только для тестирования
- **Автоматическая конвертация** между форматами ключей

## Требования

### Системные требования

- **Python 3.6+**
- **SSH клиент** (OpenSSH или PuTTY)
- **Доступ к серверу** Bitrix24
- **Права на чтение/запись** в директории проекта

### Поддерживаемые платформы

- **Windows** (рекомендуется с PuTTY)
- **Linux** (с OpenSSH)
- **macOS** (с OpenSSH)
- **WSL** (Windows Subsystem for Linux)

## Устранение проблем

### Типичные ошибки

**Ошибка:** `❌ Файл ключа не найден`
```bash
# Проверьте путь к ключу
python config-utils/check_auth.py
```

**Ошибка:** `❌ SSH клиент не найден`
```bash
# Установите SSH клиент
choco install putty  # Windows
sudo apt-get install openssh-client  # Linux
```

**Ошибка:** `❌ Bitrix24 не найден`
```bash
# Проверьте пути установки
python inspection-system/bitrix_inspector.py
```

### Диагностика

```bash
# Полная диагностика системы
python config-utils/check_auth.py

# Проверка инспекции
python inspection-system/inspect_bitrix.py

# Проверка резервного копирования
python backup-restore-system/backup_manager.py list
```

## Мониторинг и логирование

### Логи системы

- **Резервное копирование**: `backup-restore-system/logs/`
- **Инспекция**: `inspection-system/reports/`
- **Развертывание**: `task-completion-blocker/logs/`

### Мониторинг работы

```bash
# Просмотр резервных копий
python backup-restore-system/backup_manager.py list

# Проверка отчетов инспекции
ls -la inspection-system/reports/

# Мониторинг развертывания
python task-completion-blocker/deployment/deploy_task_blocker.py --check
```

## Примеры использования

### Новый проект

```bash
# 1. Настройка с нуля
python config-utils/setup.py

# 2. Анализ системы
python inspection-system/inspect_bitrix.py

# 3. Развертывание
python task-completion-blocker/deploy_and_test.py
```

### Обновление существующего проекта

```bash
# 1. Создание резервной копии
python backup-restore-system/backup_manager.py create

# 2. Обновление конфигурации
python config-utils/setup.py

# 3. Безопасное развертывание
python inspection-system/safe_deployment_manager.py deploy config.json
```

### Восстановление после ошибок

```bash
# Полное восстановление системы
python backup-restore-system/restore_manager.py full

# Восстановление из конкретной копии
python backup-restore-system/restore_manager.py restore backup_20250115_120000
```

## Поддержка и разработка

### Структура проекта

- **Модульная архитектура** - каждая подсистема независима
- **Единая конфигурация** - общий config.json для всех компонентов
- **Общие утилиты** - переиспользуемые компоненты
- **Безопасность по умолчанию** - автоматическое резервное копирование

### Расширение функциональности

1. **Добавление новых инспекторов** в `inspection-system/`
2. **Создание новых кастомизаций** по образцу `task-completion-blocker/`
3. **Интеграция с другими системами** через общий config.json

## Лицензия и поддержка

**Версия:** 2.0  
**Совместимость:** Bitrix24 коробочная версия  
**Поддержка:** Python 3.6+, SSH клиенты  
**Платформы:** Windows, Linux, macOS

---

**Разработано для безопасной работы с Bitrix24**  
**Все изменения сопровождаются резервным копированием**  
**Протестировано в продакшн-среде** 