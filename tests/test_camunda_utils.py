"""
Тесты для утилит работы с переменными Camunda BPM
Файл: task-creator/consumers/bitrix/utils/camunda_utils.py
"""
from datetime import datetime

import pytest

from camunda_utils import (
    format_process_variable_value,
    get_camunda_datetime,
    get_camunda_int,
)


# =========================================================================
# format_process_variable_value — boolean
# =========================================================================


class TestFormatBoolean:
    def test_true_bool(self):
        assert format_process_variable_value("boolean", True) == "Да"

    def test_false_bool(self):
        assert format_process_variable_value("boolean", False) == "Нет"

    def test_string_true(self):
        assert format_process_variable_value("boolean", "true") == "Да"

    def test_string_1(self):
        assert format_process_variable_value("boolean", "1") == "Да"

    def test_string_da(self):
        assert format_process_variable_value("boolean", "да") == "Да"

    def test_string_false(self):
        assert format_process_variable_value("boolean", "false") == "Нет"

    def test_string_0(self):
        assert format_process_variable_value("boolean", "0") == "Нет"

    def test_int_1(self):
        assert format_process_variable_value("boolean", 1) == "Да"

    def test_int_0(self):
        assert format_process_variable_value("boolean", 0) == "Нет"

    def test_none_value(self):
        assert format_process_variable_value("boolean", None) == ""


# =========================================================================
# format_process_variable_value — date / datetime
# =========================================================================


class TestFormatDate:
    def test_iso_datetime(self):
        assert format_process_variable_value("date", "2024-12-31T10:30:00") == "31.12.2024"

    def test_iso_date_only(self):
        assert format_process_variable_value("date", "2024-01-15") == "15.01.2024"

    def test_iso_with_z_suffix(self):
        assert format_process_variable_value("date", "2024-06-01T00:00:00Z") == "01.06.2024"

    def test_datetime_type(self):
        assert format_process_variable_value("datetime", "2024-03-20T12:00:00") == "20.03.2024"

    def test_datetime_object(self):
        dt = datetime(2024, 7, 4, 15, 30)
        assert format_process_variable_value("date", dt) == "04.07.2024"

    def test_empty_string(self):
        assert format_process_variable_value("date", "") == ""

    def test_none_value(self):
        assert format_process_variable_value("date", None) == ""


# =========================================================================
# format_process_variable_value — dict unwrap, list, misc
# =========================================================================


class TestFormatMisc:
    def test_dict_unwrap_value_key(self):
        assert format_process_variable_value("boolean", {"value": True}) == "Да"

    def test_dict_unwrap_VALUE_key(self):
        assert format_process_variable_value("boolean", {"VALUE": "true"}) == "Да"

    def test_list_values(self):
        assert format_process_variable_value(None, ["a", "b", "c"]) == "a, b, c"

    def test_unknown_type_str(self):
        assert format_process_variable_value("string", 42) == "42"

    def test_none_type_passthrough(self):
        assert format_process_variable_value(None, "hello") == "hello"

    def test_none_value_returns_empty(self):
        assert format_process_variable_value("string", None) == ""


# =========================================================================
# get_camunda_int
# =========================================================================


class TestGetCamundaInt:
    def test_direct_int(self):
        assert get_camunda_int({"x": 5}, "x") == 5

    def test_dict_value(self):
        assert get_camunda_int({"x": {"value": "123"}}, "x") == 123

    def test_string_value(self):
        assert get_camunda_int({"x": "77"}, "x") == 77

    def test_missing_key(self):
        assert get_camunda_int({"x": 1}, "y") is None

    def test_none_variables(self):
        assert get_camunda_int(None, "x") is None

    def test_empty_dict(self):
        assert get_camunda_int({}, "x") is None

    def test_empty_string(self):
        assert get_camunda_int({"x": ""}, "x") is None

    def test_invalid_string(self):
        assert get_camunda_int({"x": "abc"}, "x") is None

    def test_none_value(self):
        assert get_camunda_int({"x": None}, "x") is None


# =========================================================================
# get_camunda_datetime
# =========================================================================


class TestGetCamundaDatetime:
    def test_iso_with_t(self):
        result = get_camunda_datetime({"d": "2024-12-31T00:00:00"}, "d")
        assert result == datetime(2024, 12, 31, 0, 0, 0)

    def test_iso_with_space(self):
        result = get_camunda_datetime({"d": "2024-12-31 10:30:00"}, "d")
        assert result == datetime(2024, 12, 31, 10, 30, 0)

    def test_date_only(self):
        result = get_camunda_datetime({"d": "2024-12-31"}, "d")
        assert result == datetime(2024, 12, 31, 0, 0, 0)

    def test_dict_unwrap(self):
        result = get_camunda_datetime({"d": {"value": "2024-01-15T08:00:00"}}, "d")
        assert result == datetime(2024, 1, 15, 8, 0, 0)

    def test_none_variables(self):
        assert get_camunda_datetime(None, "d") is None

    def test_missing_key(self):
        assert get_camunda_datetime({"a": "2024-01-01"}, "d") is None

    def test_empty_string(self):
        assert get_camunda_datetime({"d": "  "}, "d") is None

    def test_invalid_format(self):
        assert get_camunda_datetime({"d": "not-a-date"}, "d") is None

    def test_non_string_value(self):
        assert get_camunda_datetime({"d": 12345}, "d") is None
