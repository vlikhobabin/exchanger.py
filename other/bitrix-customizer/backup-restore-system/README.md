# Система резервного копирования и восстановления Bitrix24

## Описание

Универсальная система для создания резервных копий и восстановления файлов Bitrix24 коробочной версии. Обеспечивает безопасное резервное копирование критически важных файлов перед внесением изменений и возможность их восстановления.

## Возможности

- ✅ **Автоматическое создание резервных копий** оригинальных файлов
- ✅ **Умная система восстановления** с проверкой целостности  
- ✅ **Поддержка SSH-ключей и паролей** для подключения к серверу
- ✅ **Проверка целостности** резервных копий через MD5 checksums
- ✅ **Детальное логирование** всех операций
- ✅ **Интеграция с системой инспекции** для автоматического определения файлов

## Структура компонентов

```
backup-restore-system/
├── 📄 backup_manager.py          # Основной модуль создания резервных копий
├── 📄 restore_manager.py         # Модуль восстановления
├── 📁 backups/                   # Директория для хранения резервных копий
│   ├── backup_YYYYMMDD_HHMMSS/   # Сессии резервного копирования
│   │   ├── backup_info.json      # Метаданные резервной копии
│   │   └── [файлы_копий]         # Резервные копии файлов
└── 📄 README.md                  # Документация
```

## Использование

### Создание резервной копии

```bash
# Базовое создание резервной копии
python backup_manager.py create

# Просмотр всех резервных копий
python backup_manager.py list

# Создание резервной копии с отчетом инспекции
python backup_manager.py create --inspection-report ../inspection-system/reports/latest.json
```

### Восстановление файлов

```bash
# Восстановление из конкретной резервной копии
python restore_manager.py restore backup_20250712_123456

# Просмотр доступных резервных копий
python restore_manager.py list

# Полное восстановление системы (удаляет все кастомизации)
python restore_manager.py full
```

## Типы резервируемых файлов

### Критически важные файлы
- `local/php_interface/init.php` - файл локальной инициализации
- `local/templates/bitrix24/header.php` - заголовок шаблона
- `local/templates/bitrix24/footer.php` - подвал шаблона
- `bitrix/php_interface/dbconn.php` - настройки базы данных

### Конфигурационные файлы
- `bitrix/.settings.php` - основные настройки системы
- `local/.settings.php` - локальные настройки

## Конфигурация

Использует общий файл конфигурации `../config.json`:

```json
{
  "server": {
    "host": "your-server.com",
    "user": "root",
    "auth_method": "key",
    "key_file": "C:/Users/username/.ssh/privete-key.ppk"
  }
}
```

## Интеграция с другими системами

### Автоматическое использование системы инспекции

```python
# Создание резервной копии на основе отчета инспекции
python backup_manager.py create --inspection-report ../inspection-system/reports/latest.json
```

### Использование из других модулей

```python
from backup_restore_system.backup_manager import BitrixBackupManager

backup_manager = BitrixBackupManager()
success = backup_manager.create_backup()
```

## Метаданные резервных копий

Каждая резервная копия содержит файл `backup_info.json`:

```json
{
  "timestamp": "2025-01-15T12:00:00",
  "files": [
    {
      "remote_path": "/home/bitrix/www/local/php_interface/init.php",
      "local_path": "local_php_interface_init.php",
      "description": "Файл инициализации локальных модификаций",
      "file_type": "init_file",
      "size": 1024,
      "status": "success",
      "checksum": "abc123..."
    }
  ],
  "server_info": {
    "host": "your-server.com",
    "user": "root",
    "auth_method": "key"
  }
}
```

## Безопасность

- Инспекторы НЕ читают конфиденциальные данные
- Пароли и ключи НЕ передаются в отчетах
- Используется только чтение системной информации
- Нет изменений в конфигурации Bitrix24

## Устранение проблем

### Типичные ошибки

**Ошибка:** `❌ Файл ключа не найден`
**Решение:** Проверьте путь к ключу в `config.json`

**Ошибка:** `❌ SSH клиент не найден`
**Решение:** Установите PuTTY или OpenSSH

**Ошибка:** `❌ Таймаут выполнения`
**Решение:** Увеличьте timeout в скриптах или проверьте нагрузку сервера

### Диагностика

```bash
# Проверка подключения
python ../config-utils/check_auth.py

# Проверка SSH подключения вручную
ssh -i ~/.ssh/privete-key.ppk root@your-server.com
```

## Примеры использования

### Резервное копирование перед развертыванием

```bash
# 1. Создаем резервную копию
python backup_manager.py create

# 2. Вносим изменения
python ../task-completion-blocker/deploy_and_test.py

# 3. В случае проблем восстанавливаем
python restore_manager.py restore backup_20250115_120000
```

### Аварийное восстановление

```bash
# Полное восстановление системы к исходному состоянию
python restore_manager.py full
```

---

**Версия:** 2.0  
**Совместимость:** Bitrix24 коробочная версия, Python 3.6+  
**Зависимости:** SSH клиент (OpenSSH или PuTTY) 