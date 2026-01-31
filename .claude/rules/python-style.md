---
paths:
  - "**/*.py"
---

# Python Code Style

- Python 3.12, используй современный синтаксис (match/case, type unions `X | Y`)
- Логирование ТОЛЬКО через `loguru` — НЕ использовать стандартный `logging` или `print()`
- Метки среды в логах: `[PROD]` / `[DEV]` в зависимости от `EXCHANGER_ENV`
- Конфигурация через `pydantic-settings` (`BaseSettings` + `SettingsConfigDict`)
- Type hints обязательны для параметров и возвращаемых значений публичных методов
- Документация и комментарии на русском языке
- Graceful shutdown: обработка `SIGINT`/`SIGTERM` через `signal.signal()`
- Импорты: stdlib → third-party → local, разделённые пустой строкой
- Автоформат: `ruff format` (запускается автоматически хуком после каждого изменения .py файла)
