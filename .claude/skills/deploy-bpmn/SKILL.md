---
name: deploy-bpmn
description: Деплой BPMN диаграмм в Camunda
disable-model-invocation: true
user-invocable: true
argument: "[file-path]"
---

# /deploy-bpmn — Деплой BPMN диаграмм

## Задача

Задеплоить BPMN диаграмму в Camunda BPM через скрипт деплоя.

## Аргумент

- `[file-path]` — путь к `.bpmn` файлу для деплоя (обязательный)

## Шаги выполнения

### 1. Валидация файла

- Проверь что файл существует по указанному пути
- Проверь что расширение файла — `.bpmn`
- Если файл не найден — предложи поискать `.bpmn` файлы в проекте: `find /opt/exchanger.py -name "*.bpmn"`

### 2. Деплой

Выполни скрипт деплоя:

```bash
source /opt/exchanger.py/venv/bin/activate
python /opt/exchanger.py/camunda-sync/tools/deploy.py {file-path}
```

### 3. Результат

- Покажи вывод скрипта деплоя
- Если деплой успешен — сообщи имя процесса и версию
- Если ошибка — покажи полный текст ошибки и предложи решение

### 4. Возможные проблемы

- Ошибка подключения к Camunda — проверь `CAMUNDA_BASE_URL` в конфигурации
- Ошибка парсинга BPMN — проверь валидность XML
- Ошибка авторизации — проверь `CAMUNDA_AUTH_USERNAME`/`CAMUNDA_AUTH_PASSWORD`
