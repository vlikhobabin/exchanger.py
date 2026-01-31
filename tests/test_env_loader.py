"""
Тесты для модуля определения среды выполнения
Файл: env_loader.py
"""
from pathlib import Path

import pytest

from env_loader import (
    BASE_DIR,
    EXCHANGER_ENV,
    VALID_ENVIRONMENTS,
    get_base_dir,
    get_env_info,
    get_log_path,
)


class TestGetLogPath:
    def test_contains_logs_dir(self):
        result = get_log_path("worker.log")
        assert "logs/" in result

    def test_contains_filename(self):
        result = get_log_path("worker.log")
        assert result.endswith("worker.log")

    def test_contains_env_segment(self):
        result = get_log_path("x.log")
        assert EXCHANGER_ENV in result


class TestGetEnvInfo:
    def test_returns_dict(self):
        info = get_env_info()
        assert isinstance(info, dict)

    def test_has_required_keys(self):
        info = get_env_info()
        expected_keys = {"environment", "env_file", "logs_dir", "is_production", "is_development"}
        assert expected_keys == set(info.keys())

    def test_environment_value(self):
        info = get_env_info()
        assert info["environment"] in VALID_ENVIRONMENTS

    def test_bool_fields_are_bool(self):
        info = get_env_info()
        assert isinstance(info["is_production"], bool)
        assert isinstance(info["is_development"], bool)


class TestGetBaseDir:
    def test_returns_path(self):
        assert isinstance(get_base_dir(), Path)

    def test_path_exists(self):
        assert get_base_dir().exists()

    def test_matches_constant(self):
        assert get_base_dir() == BASE_DIR


class TestExchangerEnv:
    def test_valid_environment(self):
        assert EXCHANGER_ENV in VALID_ENVIRONMENTS
