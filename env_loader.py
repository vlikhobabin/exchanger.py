#!/usr/bin/env python3
"""
Модуль определения среды выполнения и загрузки конфигурации
============================================================

Этот модуль должен импортироваться ПЕРВЫМ во всех сервисах проекта.
Он определяет среду выполнения (prod/dev) на основе переменной окружения
EXCHANGER_ENV и загружает соответствующий файл конфигурации.

Использование:
    import sys
    sys.path.insert(0, "/opt/exchanger.py")
    from env_loader import EXCHANGER_ENV, get_log_path, get_env_info

Переменные окружения:
    EXCHANGER_ENV - среда выполнения: "prod" (по умолчанию) или "dev"
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Определение базовой директории проекта
BASE_DIR = Path("/opt/exchanger.py")

# Определение среды из переменной окружения (по умолчанию: prod)
EXCHANGER_ENV = os.environ.get("EXCHANGER_ENV", "prod").lower()

# Валидация среды
VALID_ENVIRONMENTS = ("prod", "dev")
if EXCHANGER_ENV not in VALID_ENVIRONMENTS:
    raise ValueError(
        f"Invalid EXCHANGER_ENV: '{EXCHANGER_ENV}'. "
        f"Must be one of: {', '.join(VALID_ENVIRONMENTS)}"
    )

# Пути к файлам конфигурации
ENV_FILE = BASE_DIR / f".env.{EXCHANGER_ENV}"

# Директория для логов (разделена по средам)
LOGS_DIR = BASE_DIR / "logs" / EXCHANGER_ENV

# Проверка существования файла конфигурации
if not ENV_FILE.exists():
    raise FileNotFoundError(
        f"Configuration file not found: {ENV_FILE}\n"
        f"Please create {ENV_FILE} based on config.env.example"
    )

# Загрузка конфигурации для текущей среды
# override=True перезаписывает уже установленные переменные
load_dotenv(ENV_FILE, override=True)

# Создание директории логов если не существует
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def get_log_path(filename: str) -> str:
    """
    Получить полный путь к файлу логов для текущей среды.
    
    Args:
        filename: Имя файла лога (например, "camunda-worker.log")
        
    Returns:
        Полный путь к файлу в директории логов текущей среды
        
    Example:
        >>> get_log_path("worker.log")
        '/opt/exchanger.py/logs/prod/worker.log'
    """
    return str(LOGS_DIR / filename)


def get_env_info() -> dict:
    """
    Получить информацию о текущей среде выполнения.
    
    Returns:
        Словарь с информацией о среде:
        - environment: имя среды (prod/dev)
        - env_file: путь к файлу конфигурации
        - logs_dir: путь к директории логов
        - is_production: True если production среда
        - is_development: True если development среда
    """
    return {
        "environment": EXCHANGER_ENV,
        "env_file": str(ENV_FILE),
        "logs_dir": str(LOGS_DIR),
        "is_production": EXCHANGER_ENV == "prod",
        "is_development": EXCHANGER_ENV == "dev"
    }


def get_base_dir() -> Path:
    """
    Получить базовую директорию проекта.
    
    Returns:
        Path объект базовой директории
    """
    return BASE_DIR


# Информация для отладки при импорте
if __name__ == "__main__":
    info = get_env_info()
    print("=" * 60)
    print("EXCHANGER.PY ENVIRONMENT LOADER")
    print("=" * 60)
    print(f"Environment: {info['environment'].upper()}")
    print(f"Config file: {info['env_file']}")
    print(f"Logs directory: {info['logs_dir']}")
    print(f"Is Production: {info['is_production']}")
    print(f"Is Development: {info['is_development']}")
    print("=" * 60)

