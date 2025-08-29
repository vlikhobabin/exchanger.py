#!/usr/bin/env python3
"""
Конфигурация для модуля синхронизации между StormBPMN и Camunda
"""
import os
from typing import Dict, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

# Загружаем .env из корня проекта
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


class StormBPMNConfig(BaseSettings):
    """Настройки StormBPMN API"""
    base_url: str = Field(default="https://stormbpmn.com", env="STORMBPMN_BASE_URL")
    api_version: str = Field(default="v1", env="STORMBPMN_API_VERSION")
    
    # Аутентификация
    bearer_token: str = Field(default="", env="STORMBPMN_BEARER_TOKEN")
    
    # Настройки запросов
    timeout: int = Field(default=30, env="STORMBPMN_TIMEOUT")
    retry_attempts: int = Field(default=3, env="STORMBPMN_RETRY_ATTEMPTS")
    retry_delay: int = Field(default=1, env="STORMBPMN_RETRY_DELAY")
    
    # Параметры по умолчанию для фильтрации диаграмм
    default_page_size: int = Field(default=20, env="STORMBPMN_DEFAULT_PAGE_SIZE")
    default_sort: str = Field(default="updatedOn,desc", env="STORMBPMN_DEFAULT_SORT")
    default_view: str = Field(default="TEAM", env="STORMBPMN_DEFAULT_VIEW")
    
    class Config:
        env_prefix = "STORMBPMN_"
    
    @property
    def api_base_url(self) -> str:
        """Полный URL к API"""
        return f"{self.base_url}/api/{self.api_version}"
    
    @property
    def auth_headers(self) -> Dict[str, str]:
        """Заголовки для аутентификации"""
        if not self.bearer_token:
            raise ValueError("STORMBPMN_BEARER_TOKEN не установлен")
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }


class CamundaConfig(BaseSettings):
    """Настройки Camunda"""
    base_url: str = Field(default="https://camunda.eg-holding.ru/engine-rest", env="CAMUNDA_BASE_URL")
    
    # Аутентификация
    auth_enabled: bool = Field(default=True, env="CAMUNDA_AUTH_ENABLED")
    auth_username: str = Field(default="demo", env="CAMUNDA_AUTH_USERNAME")
    auth_password: str = Field(default="", env="CAMUNDA_AUTH_PASSWORD")
    
    # HTTP настройки
    timeout: int = Field(default=30, env="CAMUNDA_TIMEOUT")
    retry_attempts: int = Field(default=3, env="CAMUNDA_RETRY_ATTEMPTS")
    retry_delay: int = Field(default=2, env="CAMUNDA_RETRY_DELAY")
    
    class Config:
        env_prefix = "CAMUNDA_"
    
    @property
    def auth_credentials(self) -> Optional[tuple]:
        """Кредендералы для аутентификации"""
        if self.auth_enabled and self.auth_username and self.auth_password:
            return (self.auth_username, self.auth_password)
        return None


class SyncConfig(BaseSettings):
    """Настройки синхронизации (упрощенная версия)"""
    # Общие настройки
    sync_enabled: bool = Field(default=True, env="SYNC_ENABLED")
    sync_interval: int = Field(default=3600, env="SYNC_INTERVAL")  # секунды
    
    # Настройки обработки
    batch_size: int = Field(default=10, env="SYNC_BATCH_SIZE")
    max_workers: int = Field(default=5, env="SYNC_MAX_WORKERS")
    
    # Базовые фильтры (без сложных списков пока)
    sync_only_team_diagrams: bool = Field(default=True, env="SYNC_ONLY_TEAM_DIAGRAMS")
    sync_only_public: bool = Field(default=True, env="SYNC_ONLY_PUBLIC")
    
    class Config:
        env_prefix = "SYNC_"


class WorkerConfig(BaseSettings):
    """Общие настройки Worker"""
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Настройки мониторинга
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=8080, env="METRICS_PORT")
    
    # Настройки обработки ошибок
    max_error_count: int = Field(default=10, env="MAX_ERROR_COUNT")
    error_cooldown: int = Field(default=300, env="ERROR_COOLDOWN")  # секунды
    
    class Config:
        env_prefix = "WORKER_"


class MappingConfig:
    """Конфигурация маппингов между StormBPMN и Camunda"""
    
    # Маппинг статусов диаграмм
    STATUS_MAPPING: Dict[str, str] = {
        "NEW": "active",
        "IN_PROGRESS": "active", 
        "DONE": "suspended",
        "ARCHIVED": "suspended"
    }
    
    # Маппинг типов процессов
    PROCESS_TYPE_MAPPING: Dict[str, str] = {
        "ASIS": "as-is",
        "TOBE": "to-be",
        "HYBRID": "hybrid"
    }
    
    # Приоритеты по качеству диаграммы
    QUALITY_PRIORITY_MAPPING: Dict[float, int] = {
        10.0: 100,  # Высокий приоритет
        9.0: 90,
        8.0: 80,
        7.0: 70,
        6.0: 60,
        5.0: 50,    # Средний приоритет
        4.0: 40,
        3.0: 30,
        2.0: 20,
        1.0: 10,
        0.0: 0      # Низкий приоритет
    }
    
    @classmethod
    def get_camunda_status(cls, stormbpmn_status: str) -> str:
        """Получить статус Camunda по статусу StormBPMN"""
        return cls.STATUS_MAPPING.get(stormbpmn_status, "active")
    
    @classmethod
    def get_process_type(cls, stormbpmn_type: str) -> str:
        """Получить тип процесса для Camunda"""
        return cls.PROCESS_TYPE_MAPPING.get(stormbpmn_type, "as-is")
    
    @classmethod
    def get_priority_by_quality(cls, quality: float) -> int:
        """Получить приоритет по качеству диаграммы"""
        # Найти ближайшее значение качества
        for q in sorted(cls.QUALITY_PRIORITY_MAPPING.keys(), reverse=True):
            if quality >= q:
                return cls.QUALITY_PRIORITY_MAPPING[q]
        return 0


# Создание экземпляров конфигурации
stormbpmn_config = StormBPMNConfig()
camunda_config = CamundaConfig()
sync_config = SyncConfig()
worker_config = WorkerConfig()
mapping_config = MappingConfig() 