"""
Bitrix24 интеграционный модуль
"""
from .handler import BitrixTaskHandler
from .config import bitrix_config, worker_config, SUPPORTED_TOPICS

__all__ = ['BitrixTaskHandler', 'bitrix_config', 'worker_config', 'SUPPORTED_TOPICS'] 