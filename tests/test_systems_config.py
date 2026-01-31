"""
Тесты для конфигурации систем, очередей и трекеров
Файл: task-creator/config.py
"""
import pytest

# Импорт конфигурационных классов (не экземпляров, чтобы избежать побочных эффектов pydantic)
from task_creator_config import SentQueuesConfig, SystemsConfig, TrackerConfig


# =========================================================================
# SystemsConfig
# =========================================================================


class TestSystemsConfig:
    def test_get_handler_info_existing(self):
        info = SystemsConfig.get_handler_info("bitrix24.queue")
        assert info is not None
        assert "module" in info
        assert "handler_class" in info
        assert "description" in info

    def test_get_handler_info_unknown(self):
        assert SystemsConfig.get_handler_info("nonexistent.queue") is None

    def test_get_all_queues_count(self):
        queues = SystemsConfig.get_all_queues()
        assert len(queues) == 5

    def test_get_all_queues_contains_bitrix(self):
        assert "bitrix24.queue" in SystemsConfig.get_all_queues()

    def test_get_handler_class_name_bitrix(self):
        assert SystemsConfig.get_handler_class_name("bitrix24.queue") == "BitrixTaskHandler"

    def test_get_handler_class_name_openproject(self):
        assert SystemsConfig.get_handler_class_name("openproject.queue") == "OpenProjectTaskHandler"

    def test_get_handler_class_name_unknown(self):
        assert SystemsConfig.get_handler_class_name("unknown.queue") is None

    def test_get_handler_module_path(self):
        assert SystemsConfig.get_handler_module_path("bitrix24.queue") == "consumers.bitrix"


# =========================================================================
# SentQueuesConfig
# =========================================================================


class TestSentQueuesConfig:
    def test_mapping_bitrix(self):
        assert SentQueuesConfig.get_sent_queue_name("bitrix24.queue") == "bitrix24.sent.queue"

    def test_mapping_openproject(self):
        assert SentQueuesConfig.get_sent_queue_name("openproject.queue") == "openproject.sent.queue"

    def test_mapping_unknown(self):
        assert SentQueuesConfig.get_sent_queue_name("nonexistent.queue") is None

    def test_get_all_sent_queues_count(self):
        queues = SentQueuesConfig.get_all_sent_queues()
        assert len(queues) == 5

    def test_all_sent_queues_have_sent_suffix(self):
        for queue in SentQueuesConfig.get_all_sent_queues():
            assert queue.endswith(".sent.queue")


# =========================================================================
# TrackerConfig
# =========================================================================


class TestTrackerConfig:
    def test_get_tracker_info_existing(self):
        info = TrackerConfig.get_tracker_info("bitrix24.sent.queue")
        assert info is not None
        assert "module" in info
        assert "tracker_class" in info
        assert "target_queue" in info

    def test_get_tracker_info_unknown(self):
        assert TrackerConfig.get_tracker_info("unknown.sent.queue") is None

    def test_target_queue_always_camunda_responses(self):
        for sent_queue in TrackerConfig.get_all_sent_queues():
            assert TrackerConfig.get_target_queue(sent_queue) == "camunda.responses.queue"

    def test_get_all_sent_queues_count(self):
        assert len(TrackerConfig.get_all_sent_queues()) == 5

    def test_get_tracker_class_name_bitrix(self):
        assert TrackerConfig.get_tracker_class_name("bitrix24.sent.queue") == "BitrixTaskTracker"
