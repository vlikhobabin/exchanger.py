"""
Общие фикстуры и настройки для тестов Exchanger.py
"""
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# Добавляем корень проекта в sys.path
sys.path.insert(0, "/opt/exchanger.py")


def _import_module_from_path(module_name: str, file_path: str):
    """Импортирует модуль напрямую по пути к файлу, минуя __init__.py"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Предзагружаем модули с конфликтующими именами, чтобы тесты получали правильные версии.
# camunda_utils — грузим напрямую, чтобы не тянуть consumers.bitrix.__init__
_import_module_from_path(
    "camunda_utils",
    "/opt/exchanger.py/task-creator/consumers/bitrix/utils/camunda_utils.py",
)

# task-creator/config.py — грузим как отдельный модуль, чтобы не конфликтовал с camunda-worker/config.py
_import_module_from_path(
    "task_creator_config",
    "/opt/exchanger.py/task-creator/config.py",
)

# camunda-worker/config.py
_import_module_from_path(
    "camunda_worker_config",
    "/opt/exchanger.py/camunda-worker/config.py",
)


@pytest.fixture
def sample_variables() -> Dict[str, Any]:
    """Словарь переменных в Camunda-формате {"key": {"value": "..."}}"""
    return {
        "taskName": {"value": "Тестовая задача", "type": "String"},
        "responsibleId": {"value": "123", "type": "String"},
        "deadline": {"value": "2024-12-31T00:00:00", "type": "String"},
        "priority": {"value": "2", "type": "String"},
        "isUrgent": {"value": "true", "type": "String"},
        "count": {"value": "42", "type": "String"},
    }


@pytest.fixture
def empty_variables() -> Dict[str, Any]:
    """Пустой словарь переменных"""
    return {}
