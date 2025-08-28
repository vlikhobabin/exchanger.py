"""
Конфигурационный файл для Camunda Worker
"""
import os
from typing import Dict, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class CamundaConfig(BaseSettings):
    """Настройки Camunda"""
    base_url: str = Field(default="https://camunda.eg-holding.ru/engine-rest", env="CAMUNDA_BASE_URL")
    worker_id: str = Field(default="universal-worker", env="CAMUNDA_WORKER_ID")
    max_tasks: int = Field(default=10, env="CAMUNDA_MAX_TASKS")
    lock_duration: int = Field(default=31536000000, env="CAMUNDA_LOCK_DURATION")  # 1 год (365 дней)
    async_response_timeout: int = Field(default=30000, env="CAMUNDA_ASYNC_TIMEOUT")
    fetch_interval: int = Field(default=5000, env="CAMUNDA_FETCH_INTERVAL")  # 5 секунд
    
    # HTTP настройки
    http_timeout_millis: int = Field(default=30000, env="CAMUNDA_HTTP_TIMEOUT")
    timeout_delta_millis: int = Field(default=5000, env="CAMUNDA_TIMEOUT_DELTA")
    
    # Переменные и свойства  
    include_extension_properties: bool = Field(default=True, env="CAMUNDA_INCLUDE_EXT_PROPS")
    deserialize_values: bool = Field(default=True, env="CAMUNDA_DESERIALIZE_VALUES")
    
    # Сортировка
    sorting: Optional[str] = Field(default=None, env="CAMUNDA_SORTING")  # None или "created"
    
    # Отладка
    is_debug: bool = Field(default=False, env="CAMUNDA_DEBUG")
    
    # Сохранять отладочные сообщения ответов в JSON файл
    debug_save_response_messages: bool = Field(default=False, env="DEBUG_SAVE_RESPONSE_MESSAGES")
    
    # Sleep при ошибках
    sleep_seconds: int = Field(default=30, env="CAMUNDA_SLEEP_SECONDS")
    
    # Аутентификация
    auth_enabled: bool = Field(default=True, env="CAMUNDA_AUTH_ENABLED")
    auth_username: str = Field(default="demo", env="CAMUNDA_AUTH_USERNAME")
    auth_password: str = Field(default="BwS-YqM-AFd-Cru", env="CAMUNDA_AUTH_PASSWORD")
    
    class Config:
        env_prefix = "CAMUNDA_"


class RabbitMQConfig(BaseSettings):
    """Настройки RabbitMQ"""
    host: str = Field(default="rmq.eg-holding.ru", env="RABBITMQ_HOST")
    port: int = Field(default=5672, env="RABBITMQ_PORT")
    username: str = Field(default="guest", env="RABBITMQ_USERNAME")
    password: str = Field(default="guest", env="RABBITMQ_PASSWORD")
    virtual_host: str = Field(default="/", env="RABBITMQ_VIRTUAL_HOST")
    
    # Exchange для исходящих задач
    tasks_exchange_name: str = Field(default="camunda.external.tasks", env="RABBITMQ_TASKS_EXCHANGE")
    tasks_exchange_type: str = Field(default="topic", env="RABBITMQ_TASKS_EXCHANGE_TYPE")
    
    # Alternate Exchange для неопознанных сообщений
    alternate_exchange_name: str = Field(default="camunda.unrouted.tasks", env="RABBITMQ_ALTERNATE_EXCHANGE")
    alternate_exchange_type: str = Field(default="fanout", env="RABBITMQ_ALTERNATE_EXCHANGE_TYPE")
    
    # Exchange для ответов
    responses_exchange_name: str = Field(default="camunda.task.responses", env="RABBITMQ_RESPONSES_EXCHANGE")
    responses_exchange_type: str = Field(default="direct", env="RABBITMQ_RESPONSES_EXCHANGE_TYPE")
    responses_queue_name: str = Field(default="camunda.responses.queue", env="RABBITMQ_RESPONSES_QUEUE")
    
    class Config:
        env_prefix = "RABBITMQ_"


class WorkerConfig(BaseSettings):
    """Общие настройки Worker"""
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    retry_attempts: int = Field(default=3, env="RETRY_ATTEMPTS")
    retry_delay: int = Field(default=5, env="RETRY_DELAY")  # секунды
    heartbeat_interval: int = Field(default=60, env="HEARTBEAT_INTERVAL")  # секунды
    
    # Настройки для обработчика ответов
    response_handler_enabled: bool = Field(default=True, env="RESPONSE_HANDLER_ENABLED")
    response_processing_interval: int = Field(default=5, env="RESPONSE_PROCESSING_INTERVAL")  # секунды
    
    class Config:
        # Убираем env_prefix чтобы использовать переменные без префикса
        pass


class RoutingConfig:
    """Конфигурация маршрутизации задач по системам"""
    
    # Маппинг топиков на системы
    TOPIC_TO_SYSTEM_MAPPING: Dict[str, str] = {
        # Bitrix24
        "bitrix24": "bitrix24",
        "bitrix_create_task": "bitrix24",
        "bitrix_update_task": "bitrix24",
        "bitrix_create_deal": "bitrix24",
        "bitrix_update_deal": "bitrix24",
        "bitrix_create_contact": "bitrix24",
        
        # OpenProject
        "openproject": "openproject", 
        "op_create_project": "openproject",
        "op_create_task": "openproject",
        "op_update_task": "openproject",
        "op_create_milestone": "openproject",
        
        # 1C
        "1c": "1c",
        "1c_create_document": "1c",
        "1c_update_document": "1c",
        "1c_create_counterparty": "1c",
        "1c_sync_data": "1c",
        
        # Python services
        "python": "python-services",
        "send_email": "python-services",
        "send_telegram": "python-services",
        "telegram_notify": "python-services",
        "email_notify": "python-services",
        "create_yandex_file": "python-services",
        "yandex_disk": "python-services",
        "create_user": "python-services",
        "user_management": "python-services",
        "file_processing": "python-services",
        "data_processing": "python-services",
    }
    
    # Очереди для каждой системы
    SYSTEM_QUEUES: Dict[str, str] = {
        "bitrix24": "bitrix24.queue",
        "openproject": "openproject.queue", 
        "1c": "1c.queue",
        "python-services": "python-services.queue",
        "default": "default.queue"
    }
    
    # Routing keys для привязки очередей
    ROUTING_BINDINGS: Dict[str, List[str]] = {
        "bitrix24.queue": ["bitrix24.*"],
        "openproject.queue": ["openproject.*"],
        "1c.queue": ["1c.*"],
        "python-services.queue": ["python.*", "email.*", "telegram.*", "yandex.*", "user.*", "file.*", "data.*"],
        # default.queue теперь НЕ имеет привязок к основному exchange
        # неопознанные сообщения будут автоматически направляться через Alternate Exchange
    }
    
    @classmethod
    def get_system_for_topic(cls, topic: str) -> str:
        """Определить систему по топику"""
        # Прямое соответствие
        if topic in cls.TOPIC_TO_SYSTEM_MAPPING:
            return cls.TOPIC_TO_SYSTEM_MAPPING[topic]
        
        # Поиск по префиксам
        topic_lower = topic.lower()
        for key, system in cls.TOPIC_TO_SYSTEM_MAPPING.items():
            if topic_lower.startswith(key.lower()):
                return system
        
        return "default"
    
    @classmethod
    def get_routing_key(cls, topic: str) -> str:
        """Получить routing key для топика"""
        system = cls.get_system_for_topic(topic)
        return f"{system}.{topic}"
    
    @classmethod
    def get_queue_for_system(cls, system: str) -> str:
        """Получить очередь для системы"""
        return cls.SYSTEM_QUEUES.get(system, cls.SYSTEM_QUEUES["default"])


class TaskResponseConfig:
    """Конфигурация для ответных сообщений - Stateless режим"""
    
    # Типы ответов (без продления блокировок в Stateless режиме)
    RESPONSE_TYPES = {
        "COMPLETE": "complete",           # Успешное завершение
        "FAILURE": "failure",             # Ошибка с возможностью повтора
        "BPMN_ERROR": "bpmn_error"        # BPMN ошибка
    }
    
    # Обязательные поля в ответном сообщении
    REQUIRED_FIELDS = [
        "task_id",           # ID задачи в Camunda
        "response_type",     # Тип ответа
        "worker_id"          # ID worker'а для проверки
    ]
    
    # Опциональные поля для разных типов ответов
    OPTIONAL_FIELDS = {
        "complete": ["variables", "local_variables"],
        "failure": ["error_message", "error_details", "retries", "retry_timeout"],
        "bpmn_error": ["error_code", "error_message", "variables"]
    }


# Создание экземпляров конфигурации
camunda_config = CamundaConfig()
rabbitmq_config = RabbitMQConfig()
worker_config = WorkerConfig()
routing_config = RoutingConfig()
response_config = TaskResponseConfig() 