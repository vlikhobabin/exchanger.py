# Управление сервисами Exchanger.py

Документация по установке и управлению сервисами `exchanger-camunda-worker` и `exchanger-task-creator` с поддержкой разделения сред **Production** и **Development**.

## Архитектура сред

```
┌─────────────────────────────────────────────────────────────────┐
│                        ЕДИНАЯ КОДОВАЯ БАЗА                      │
│                     /opt/exchanger.py/                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────┐      ┌─────────────────────┐          │
│  │   EXCHANGER_ENV=prod │      │   EXCHANGER_ENV=dev  │          │
│  ├─────────────────────┤      ├─────────────────────┤          │
│  │ .env.prod            │      │ .env.dev             │          │
│  │ logs/prod/           │      │ logs/dev/            │          │
│  │ LOG_LEVEL=INFO       │      │ LOG_LEVEL=DEBUG      │          │
│  │ Bitrix: bx.eg-...    │      │ Bitrix: bx-dev.eg-.. │          │
│  └─────────────────────┘      └─────────────────────┘          │
│           │                            │                        │
│  ┌────────┴────────┐          ┌────────┴────────┐              │
│  │ systemd services│          │ systemd services│              │
│  │   *-prod.service│          │   *-dev.service │              │
│  └─────────────────┘          └─────────────────┘              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Структура файлов

```
/opt/exchanger.py/
├── .env.prod                         # Production конфигурация
├── .env.dev                          # Development конфигурация
├── env_loader.py                     # Модуль загрузки среды
├── logs/
│   ├── prod/                         # Логи production
│   │   ├── camunda-worker.log
│   │   ├── camunda-worker-errors.log
│   │   ├── task-creator.log
│   │   └── task-creator-errors.log
│   └── dev/                          # Логи development
│       ├── camunda-worker.log
│       ├── camunda-worker-errors.log
│       ├── task-creator.log
│       └── task-creator-errors.log
└── servieces-management/
    ├── install_services.sh           # Установка 4 systemd сервисов
    ├── uninstall_services.sh         # Удаление сервисов
    ├── start_services.sh [prod|dev|all]
    ├── stop_services.sh [prod|dev|all]
    ├── restart_services.sh [prod|dev|all]
    └── status_services.sh [prod|dev|all|summary]
```

## Установка сервисов

```bash
# Сделать скрипты исполняемыми
chmod +x servieces-management/*.sh

# Запустить установщик
./servieces-management/install_services.sh
```

Установщик выполнит:
1. Создание 4 systemd unit-файлов (prod и dev версии)
2. Создание директорий для логов
3. Включение PROD сервисов в автозапуск
4. Запуск PROD сервисов
5. Удаление старых сервисов (без суффикса -prod/-dev)

## Созданные сервисы

| Сервис | Среда | Автозапуск |
|--------|-------|------------|
| `exchanger-camunda-worker-prod` | Production | ✅ Да |
| `exchanger-task-creator-prod` | Production | ✅ Да |
| `exchanger-camunda-worker-dev` | Development | ❌ Нет |
| `exchanger-task-creator-dev` | Development | ❌ Нет |

## Управление сервисами

### Запуск сервисов

```bash
# Запуск production (по умолчанию)
./servieces-management/start_services.sh
./servieces-management/start_services.sh prod

# Запуск development
./servieces-management/start_services.sh dev

# Запуск обеих сред
./servieces-management/start_services.sh all
```

### Остановка сервисов

```bash
# Остановка production
./servieces-management/stop_services.sh prod

# Остановка development
./servieces-management/stop_services.sh dev

# Остановка всех
./servieces-management/stop_services.sh all
```

### Перезапуск сервисов

```bash
# Перезапуск production (после git pull или изменения кода)
./servieces-management/restart_services.sh prod

# Перезапуск development
./servieces-management/restart_services.sh dev

# Перезапуск всех
./servieces-management/restart_services.sh all
```

### Проверка статуса

```bash
# Статус всех сервисов (подробный)
./servieces-management/status_services.sh

# Статус только production
./servieces-management/status_services.sh prod

# Статус только development
./servieces-management/status_services.sh dev

# Компактная сводка
./servieces-management/status_services.sh summary
```

## Файлы конфигурации

### .env.prod (Production)

```bash
LOG_LEVEL=INFO
BITRIX_WEBHOOK_URL=https://bx.eg-holding.ru/rest/1/xxxxx/
DEBUG_SAVE_RESPONSE_MESSAGES=false
CAMUNDA_DEBUG=false
# ... остальные prod настройки
```

### .env.dev (Development)

```bash
LOG_LEVEL=DEBUG
BITRIX_WEBHOOK_URL=https://bx-dev.eg-holding.ru/rest/1/xxxxx/
DEBUG_SAVE_RESPONSE_MESSAGES=true
CAMUNDA_DEBUG=true
# ... остальные dev настройки
```

## Просмотр логов

### Production логи

```bash
# Camunda Worker
tail -f /opt/exchanger.py/logs/prod/camunda-worker.log
tail -100 /opt/exchanger.py/logs/prod/camunda-worker-errors.log

# Task Creator
tail -f /opt/exchanger.py/logs/prod/task-creator.log
tail -100 /opt/exchanger.py/logs/prod/task-creator-errors.log
```

### Development логи

```bash
# Camunda Worker
tail -f /opt/exchanger.py/logs/dev/camunda-worker.log

# Task Creator
tail -f /opt/exchanger.py/logs/dev/task-creator.log
```

### Systemd журнал

```bash
# Production
journalctl -u exchanger-camunda-worker-prod -f
journalctl -u exchanger-task-creator-prod -f

# Development
journalctl -u exchanger-camunda-worker-dev -f
journalctl -u exchanger-task-creator-dev -f
```

## Ручной запуск (для отладки)

Для отладки можно запустить сервисы вручную с указанием среды:

```bash
cd /opt/exchanger.py
source venv/bin/activate

# Production
EXCHANGER_ENV=prod python camunda-worker/main.py
EXCHANGER_ENV=prod python task-creator/main.py

# Development
EXCHANGER_ENV=dev python camunda-worker/main.py
EXCHANGER_ENV=dev python task-creator/main.py
```

## Удаление сервисов

```bash
./servieces-management/uninstall_services.sh
```

Скрипт остановит и удалит все сервисы. Логи НЕ удаляются.

## Переменная окружения EXCHANGER_ENV

Среда определяется переменной `EXCHANGER_ENV`:
- `prod` - Production (по умолчанию)
- `dev` - Development

Переменная влияет на:
1. Какой файл конфигурации загружается (`.env.prod` или `.env.dev`)
2. В какую директорию пишутся логи (`logs/prod/` или `logs/dev/`)
3. Имя lock-файла для предотвращения дублирования инстансов
4. Метку среды в логах (`[PROD]` или `[DEV]`)

## Типичные сценарии

### Разработка нового функционала

```bash
# Остановить dev если запущен
./servieces-management/stop_services.sh dev

# Запустить вручную для отладки
cd /opt/exchanger.py
source venv/bin/activate
EXCHANGER_ENV=dev python task-creator/main.py

# Или запустить как сервис
./servieces-management/start_services.sh dev
```

### Обновление production

```bash
# Обновить код
git pull

# Перезапустить prod сервисы
./servieces-management/restart_services.sh prod
```

### Проверка что всё работает

```bash
# Краткая сводка
./servieces-management/status_services.sh summary

# Последние логи
tail -20 /opt/exchanger.py/logs/prod/camunda-worker.log
tail -20 /opt/exchanger.py/logs/prod/task-creator.log
```
