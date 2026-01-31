"""
Тесты для конфигурации маршрутизации задач
Файл: camunda-worker/config.py, класс RoutingConfig
"""
import pytest

from camunda_worker_config import RoutingConfig


class TestGetSystemForTopic:
    """Тесты маппинга топиков на системы"""

    def test_bitrix_create_task(self):
        assert RoutingConfig.get_system_for_topic("bitrix_create_task") == "bitrix24"

    def test_op_create_task(self):
        assert RoutingConfig.get_system_for_topic("op_create_task") == "openproject"

    def test_1c_create_document(self):
        assert RoutingConfig.get_system_for_topic("1c_create_document") == "1c"

    def test_send_email(self):
        assert RoutingConfig.get_system_for_topic("send_email") == "python-services"

    def test_prefix_fallback_bitrix24(self):
        """Топик с префиксом bitrix24 → bitrix24 (через startswith)"""
        assert RoutingConfig.get_system_for_topic("bitrix24_new_action") == "bitrix24"

    def test_no_prefix_match_returns_default(self):
        """bitrix_unknown не совпадает с ключом bitrix24 по startswith → default"""
        assert RoutingConfig.get_system_for_topic("bitrix_unknown_action") == "default"

    def test_prefix_fallback_1c(self):
        assert RoutingConfig.get_system_for_topic("1c_new_thing") == "1c"

    def test_unknown_topic_returns_default(self):
        assert RoutingConfig.get_system_for_topic("completely_unknown") == "default"

    def test_empty_topic_returns_default(self):
        assert RoutingConfig.get_system_for_topic("") == "default"


class TestGetRoutingKey:
    def test_bitrix_routing_key(self):
        assert RoutingConfig.get_routing_key("bitrix_create_task") == "bitrix24.bitrix_create_task"

    def test_openproject_routing_key(self):
        assert RoutingConfig.get_routing_key("op_create_task") == "openproject.op_create_task"

    def test_unknown_routing_key(self):
        assert RoutingConfig.get_routing_key("xyz") == "default.xyz"


class TestGetQueueForSystem:
    def test_bitrix24_queue(self):
        assert RoutingConfig.get_queue_for_system("bitrix24") == "bitrix24.queue"

    def test_openproject_queue(self):
        assert RoutingConfig.get_queue_for_system("openproject") == "openproject.queue"

    def test_default_queue(self):
        assert RoutingConfig.get_queue_for_system("default") == "default.queue"

    def test_unknown_system_returns_default(self):
        assert RoutingConfig.get_queue_for_system("nonexistent") == "default.queue"


class TestSystemQueues:
    def test_contains_all_systems(self):
        expected = {"bitrix24", "openproject", "1c", "python-services", "default"}
        assert set(RoutingConfig.SYSTEM_QUEUES.keys()) == expected
