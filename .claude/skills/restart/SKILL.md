---
name: restart
description: Перезапуск сервисов Exchanger.py
disable-model-invocation: true
user-invocable: true
argument: "[prod|dev|all] [worker|creator|all]"
---

# /restart — Перезапуск сервисов

## Задача

Перезапустить сервисы Exchanger.py с проверкой статуса до и после.

## Аргументы

- Первый аргумент (среда): `prod`, `dev`, `all` (default: спросить у пользователя)
- Второй аргумент (компонент): `worker`, `creator`, `all` (default: `all`)

## Имена systemd-сервисов

| Среда | Компонент | Имя сервиса |
|-------|-----------|-------------|
| prod  | worker    | `exchanger-camunda-worker-prod` |
| prod  | creator   | `exchanger-task-creator-prod` |
| dev   | worker    | `exchanger-camunda-worker-dev` |
| dev   | creator   | `exchanger-task-creator-dev` |

## Шаги выполнения

### 1. Подтверждение

**ОБЯЗАТЕЛЬНО** спроси у пользователя подтверждение перед перезапуском production сервисов. Для dev — можно без подтверждения.

### 2. Проверка текущего статуса

```bash
systemctl status {service-name}
```

Покажи текущий статус каждого сервиса, который будет перезапущен.

### 3. Перезапуск

Если нужно перезапустить все сервисы среды, используй скрипт:

```bash
/opt/exchanger.py/servieces-management/restart_services.sh {env}
```

Для точечного перезапуска отдельного компонента:

```bash
sudo systemctl restart {service-name}
```

### 4. Проверка после перезапуска

Подожди 3 секунды и проверь статус:

```bash
sleep 3 && systemctl status {service-name}
```

Покажи результат: active/failed, PID, время запуска.

### 5. Проверка логов

Покажи последние 10 строк лога после перезапуска для проверки успешной инициализации:

```bash
journalctl -u {service-name} --no-pager -n 10
```
