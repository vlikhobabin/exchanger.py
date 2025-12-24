"""
Утилиты для работы с переменными Camunda BPM

Модуль содержит функции для безопасного извлечения и форматирования
значений переменных процессов Camunda.
"""
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger


def format_process_variable_value(property_type: Optional[str], value_entry: Any) -> str:
    """
    Форматирование значения переменной процесса в человекочитаемый вид.

    Args:
        property_type: Тип переменной ('boolean', 'date', 'datetime', etc.)
        value_entry: Значение переменной (может быть dict с ключом 'value' или прямое значение)

    Returns:
        Отформатированная строка значения
    """
    value = value_entry
    if isinstance(value_entry, dict):
        if 'value' in value_entry:
            value = value_entry.get('value')
        elif 'VALUE' in value_entry:
            value = value_entry.get('VALUE')

    if isinstance(value, dict) and 'value' in value:
        value = value.get('value')

    if value is None:
        return ""

    normalized_type = (property_type or '').lower()

    if normalized_type == 'boolean':
        bool_value: Optional[bool] = None
        if isinstance(value, bool):
            bool_value = value
        elif isinstance(value, (int, float)):
            bool_value = value != 0
        elif isinstance(value, str):
            bool_value = value.strip().lower() in {'true', '1', 'y', 'yes', 'да', 'истина'}

        if bool_value is None:
            return ""
        return "Да" if bool_value else "Нет"

    if normalized_type in {'date', 'datetime'}:
        if isinstance(value, datetime):
            return value.strftime("%d.%m.%Y")
        if isinstance(value, str):
            iso_value = value.strip()
            if not iso_value:
                return ""
            try:
                normalized = iso_value.replace('Z', '+00:00')
                dt = datetime.fromisoformat(normalized)
                return dt.strftime("%d.%m.%Y")
            except ValueError:
                try:
                    date_part = iso_value.split('T')[0]
                    dt = datetime.strptime(date_part, "%Y-%m-%d")
                    return dt.strftime("%d.%m.%Y")
                except ValueError:
                    return iso_value
        return str(value)

    if isinstance(value, list):
        return ", ".join(str(item) for item in value)

    return str(value)


def get_camunda_int(variables: Optional[Dict[str, Any]], key: str) -> Optional[int]:
    """
    Безопасно извлекает целочисленное значение переменной Camunda.

    Поддерживает как прямые значения, так и Camunda object format {"value": ...}.

    Args:
        variables: Словарь переменных процесса
        key: Имя переменной

    Returns:
        Целочисленное значение или None если значение отсутствует или некорректно
    """
    if not variables or not isinstance(variables, dict):
        return None

    raw_value = variables.get(key)
    if raw_value is None:
        return None

    if isinstance(raw_value, dict):
        raw_value = raw_value.get('value', raw_value.get('VALUE'))

    if isinstance(raw_value, str):
        raw_value = raw_value.strip()
        if raw_value == "":
            return None

    try:
        return int(raw_value)
    except (TypeError, ValueError):
        logger.warning(f"Некорректное значение переменной {key}: {raw_value}")
        return None


def get_camunda_datetime(variables: Optional[Dict[str, Any]], key: str) -> Optional[datetime]:
    """
    Безопасно извлекает datetime из переменной Camunda (ISO 8601 формат).

    Поддерживаемые форматы:
    - "2024-12-31T00:00:00" (ISO 8601 без timezone)
    - "2024-12-31" (только дата)
    - {"value": "2024-12-31T00:00:00"} (Camunda object format)

    Args:
        variables: Словарь переменных процесса
        key: Имя переменной

    Returns:
        datetime объект или None если значение отсутствует или некорректно
    """
    if not variables or not isinstance(variables, dict):
        return None

    raw_value = variables.get(key)
    if raw_value is None:
        return None

    # Извлечение значения из Camunda object format
    if isinstance(raw_value, dict):
        raw_value = raw_value.get('value', raw_value.get('VALUE'))

    if not isinstance(raw_value, str):
        logger.warning(f"Некорректный тип переменной {key}: ожидается строка, получено {type(raw_value)}")
        return None

    raw_value = raw_value.strip()
    if not raw_value:
        return None

    # Попытка парсинга различных форматов ISO 8601
    formats = [
        '%Y-%m-%dT%H:%M:%S',      # 2024-12-31T00:00:00
        '%Y-%m-%d %H:%M:%S',      # 2024-12-31 00:00:00
        '%Y-%m-%d',               # 2024-12-31
    ]

    for fmt in formats:
        try:
            return datetime.strptime(raw_value, fmt)
        except ValueError:
            continue

    logger.warning(f"Некорректный формат даты переменной {key}: {raw_value}")
    return None
