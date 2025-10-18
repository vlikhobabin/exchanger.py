#!/usr/bin/env python3
"""
Конфигурация для Bitrix24 модуля
"""
import os
from typing import Dict, List
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class BitrixConfig(BaseSettings):
    """Настройки Bitrix24"""
    webhook_url: str = Field(default="https://bx.eg-holding.ru/rest/1/123123123123", env="BITRIX_WEBHOOK_URL")
    default_responsible_id: int = Field(default=1, env="BITRIX_DEFAULT_RESPONSIBLE_ID")
    default_priority: int = Field(default=1, env="BITRIX_DEFAULT_PRIORITY")
    request_timeout: int = Field(default=30, env="BITRIX_REQUEST_TIMEOUT")
    max_description_length: int = Field(default=10000, env="BITRIX_MAX_DESCRIPTION_LENGTH")
    
    roles_cache_ttl: int = Field(default=3600, env="BITRIX_ROLES_CACHE_TTL")
    
    # Маппинг для значений списка "Ответ по результату" (заполняется динамически)
    # Формат: "ID значения в Битрикс24": "Текстовое представление"
    uf_result_answer_mapping: Dict[str, str] = Field(default={})
    
    # Путь к кеш-файлу для пользовательских полей
    uf_cache_file: str = Field(default=".uf_result_answer_cache.json")
    
    class Config:
        env_prefix = "BITRIX_"


class WorkerConfig(BaseSettings):
    # ... (остальная часть файла без изменений)
    """Общие настройки Worker (только для Bitrix модуля)"""
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    retry_attempts: int = Field(default=3, env="RETRY_ATTEMPTS")
    retry_delay: int = Field(default=5, env="RETRY_DELAY")  # секунды
    heartbeat_interval: int = Field(default=60, env="HEARTBEAT_INTERVAL")  # секунды
    
    # Настройки обработки сообщений
    max_messages_per_batch: int = Field(default=10, env="MAX_MESSAGES_PER_BATCH")
    message_processing_timeout: int = Field(default=120, env="MESSAGE_PROCESSING_TIMEOUT")  # секунды
    
    class Config:
        # Убираем env_prefix чтобы использовать переменные без префикса
        pass

SUPPORTED_TOPICS: List[str] = [
    "bitrix_create_task", "bitrix_update_task", "bitrix_create_deal",
    "bitrix_update_deal", "bitrix_create_contact", "bitrix_create_lead",
    "bitrix_update_lead", "bitrix_create_company", "bitrix_update_company",
]

bitrix_config = BitrixConfig()
worker_config = WorkerConfig()
roles_cache_ttl = bitrix_config.roles_cache_ttl
roles_mapping_file = os.getenv('BITRIX_ROLES_MAPPING_FILE', 'roles_mapping.json')