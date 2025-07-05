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
    default_priority: int = Field(default=1, env="BITRIX_DEFAULT_PRIORITY")  # 1-низкий, 2-обычный, 3-высокий
    request_timeout: int = Field(default=30, env="BITRIX_REQUEST_TIMEOUT")
    max_description_length: int = Field(default=10000, env="BITRIX_MAX_DESCRIPTION_LENGTH")
    
    class Config:
        env_prefix = "BITRIX_"


class WorkerConfig(BaseSettings):
    """Общие настройки Worker (только для Bitrix модуля)"""
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    retry_attempts: int = Field(default=3, env="RETRY_ATTEMPTS")
    retry_delay: int = Field(default=5, env="RETRY_DELAY")  # секунды
    heartbeat_interval: int = Field(default=60, env="HEARTBEAT_INTERVAL")  # секунды
    
    # Настройки обработки сообщений
    max_messages_per_batch: int = Field(default=10, env="MAX_MESSAGES_PER_BATCH")
    message_processing_timeout: int = Field(default=120, env="MESSAGE_PROCESSING_TIMEOUT")  # секунды
    
    class Config:
        env_prefix = "WORKER_"


# Поддерживаемые топики для Bitrix24
SUPPORTED_TOPICS: List[str] = [
    "bitrix_create_task",
    "bitrix_update_task", 
    "bitrix_create_deal",
    "bitrix_update_deal",
    "bitrix_create_contact",
    "bitrix_create_lead",
    "bitrix_update_lead",
    "bitrix_create_company",
    "bitrix_update_company",
]

# Создание экземпляров конфигурации
bitrix_config = BitrixConfig()
worker_config = WorkerConfig() 