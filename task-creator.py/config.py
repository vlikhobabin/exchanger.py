#!/usr/bin/env python3
"""
Универсальная конфигурация для системы обработки сообщений RabbitMQ
"""
import os
from typing import Dict, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class RabbitMQConfig(BaseSettings):
    """Настройки RabbitMQ"""
    host: str = Field(default="rmq.eg-holding.ru", env="RABBITMQ_HOST")
    port: int = Field(default=5672, env="RABBITMQ_PORT")
    username: str = Field(default="admin", env="RABBITMQ_USERNAME")
    password: str = Field(default="admin", env="RABBITMQ_PASSWORD")
    virtual_host: str = Field(default="/", env="RABBITMQ_VIRTUAL_HOST")
    
    # Exchange и очереди
    tasks_exchange_name: str = Field(default="camunda.external.tasks", env="RABBITMQ_TASKS_EXCHANGE")
    tasks_exchange_type: str = Field(default="topic", env="RABBITMQ_TASKS_EXCHANGE_TYPE")
    
    # Таймауты и настройки соединения
    heartbeat: int = Field(default=600, env="RABBITMQ_HEARTBEAT")
    blocked_connection_timeout: int = Field(default=300, env="RABBITMQ_BLOCKED_TIMEOUT")
    
    class Config:
        env_prefix = "RABBITMQ_"


class WorkerConfig(BaseSettings):
    """Общие настройки Worker"""
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    retry_attempts: int = Field(default=3, env="RETRY_ATTEMPTS")
    retry_delay: int = Field(default=5, env="RETRY_DELAY")  # секунды
    heartbeat_interval: int = Field(default=60, env="HEARTBEAT_INTERVAL")  # секунды
    
    # Настройки обработки сообщений
    max_messages_per_batch: int = Field(default=10, env="MAX_MESSAGES_PER_BATCH")
    message_processing_timeout: int = Field(default=120, env="MESSAGE_PROCESSING_TIMEOUT")  # секунды
    
    class Config:
        env_prefix = "WORKER_"


class SentQueuesConfig:
    """
    Конфигурация очередей для отправленных сообщений
    """
    
    # Маппинг исходных очередей на очереди успешно отправленных сообщений
    SENT_QUEUES_MAPPING: Dict[str, str] = {
        "bitrix24.queue": "bitrix24.sent.queue",
        "openproject.queue": "openproject.sent.queue",
        "1c.queue": "1c.sent.queue", 
        "python-services.queue": "python-services.sent.queue",
        "default.queue": "default.sent.queue"
    }
    
    # Exchange для отправленных сообщений  
    SENT_MESSAGES_EXCHANGE: str = "sent.messages"
    SENT_MESSAGES_EXCHANGE_TYPE: str = "direct"
    
    @classmethod
    def get_sent_queue_name(cls, source_queue: str) -> Optional[str]:
        """
        Получить имя очереди для отправленных сообщений
        
        Args:
            source_queue: Исходная очередь
            
        Returns:
            Имя очереди для отправленных сообщений или None
        """
        return cls.SENT_QUEUES_MAPPING.get(source_queue)
    
    @classmethod
    def get_all_sent_queues(cls) -> List[str]:
        """Получить список всех очередей для отправленных сообщений"""
        return list(cls.SENT_QUEUES_MAPPING.values())
    
    @classmethod
    def add_sent_queue_mapping(cls, source_queue: str, sent_queue: str):
        """
        Добавить новый маппинг очереди
        
        Args:
            source_queue: Исходная очередь
            sent_queue: Очередь для отправленных сообщений
        """
        cls.SENT_QUEUES_MAPPING[source_queue] = sent_queue


class SystemsConfig:
    """
    Конфигурация систем и маппинг очередей на обработчики
    """
    
    # Маппинг очередей на модули обработчики
    QUEUE_HANDLERS: Dict[str, Dict[str, str]] = {
        "bitrix24.queue": {
            "module": "consumers.bitrix",
            "handler_class": "BitrixTaskHandler",
            "description": "Создание задач в Bitrix24"
        },
        "openproject.queue": {
            "module": "consumers.openproject", 
            "handler_class": "OpenProjectTaskHandler",
            "description": "Создание задач в OpenProject"
        },
        "1c.queue": {
            "module": "consumers.1c",
            "handler_class": "OneСTaskHandler", 
            "description": "Интеграция с 1C"
        },
        "python-services.queue": {
            "module": "consumers.python",
            "handler_class": "PythonServiceHandler",
            "description": "Вызов Python сервисов"
        },
        "default.queue": {
            "module": "consumers.default",
            "handler_class": "DefaultHandler",
            "description": "Обработчик по умолчанию"
        }
    }
    
    @classmethod
    def get_handler_info(cls, queue_name: str) -> Optional[Dict[str, str]]:
        """
        Получить информацию об обработчике для очереди
        
        Args:
            queue_name: Имя очереди
            
        Returns:
            Словарь с информацией о модуле и классе обработчика
        """
        return cls.QUEUE_HANDLERS.get(queue_name)
    
    @classmethod
    def get_all_queues(cls) -> List[str]:
        """Получить список всех очередей для обработки"""
        return list(cls.QUEUE_HANDLERS.keys())
    
    @classmethod
    def get_active_queues(cls) -> List[str]:
        """
        Получить список активных очередей (тех, для которых реализованы обработчики)
        
        Returns:
            Список имен очередей
        """
        active_queues = []
        for queue_name, handler_info in cls.QUEUE_HANDLERS.items():
            try:
                # Попытка импорта модуля для проверки что он существует
                module_name = handler_info["module"]
                __import__(module_name)
                active_queues.append(queue_name)
            except ImportError:
                # Модуль не найден - пропускаем эту очередь
                continue
        return active_queues
    
    @classmethod
    def get_handler_module_path(cls, queue_name: str) -> Optional[str]:
        """Получить путь к модулю обработчика"""
        handler_info = cls.get_handler_info(queue_name)
        return handler_info["module"] if handler_info else None
    
    @classmethod
    def get_handler_class_name(cls, queue_name: str) -> Optional[str]:
        """Получить имя класса обработчика"""
        handler_info = cls.get_handler_info(queue_name)
        return handler_info["handler_class"] if handler_info else None
    
    @classmethod
    def add_queue_handler(cls, queue_name: str, module: str, handler_class: str, description: str = ""):
        """
        Добавить новый обработчик очереди (для динамического расширения)
        
        Args:
            queue_name: Имя очереди
            module: Путь к модулю
            handler_class: Имя класса обработчика
            description: Описание обработчика
        """
        cls.QUEUE_HANDLERS[queue_name] = {
            "module": module,
            "handler_class": handler_class,
            "description": description
        }
    
    @classmethod
    def get_systems_status(cls) -> Dict[str, Dict[str, any]]:
        """
        Получить статус всех систем
        
        Returns:
            Словарь со статусом каждой системы
        """
        systems_status = {}
        
        for queue_name, handler_info in cls.QUEUE_HANDLERS.items():
            module_name = handler_info["module"]
            try:
                __import__(module_name)
                status = "active"
                error = None
            except ImportError as e:
                status = "inactive"
                error = str(e)
            
            systems_status[queue_name] = {
                "module": module_name,
                "handler_class": handler_info["handler_class"], 
                "description": handler_info["description"],
                "status": status,
                "error": error
            }
        
        return systems_status


# Создание экземпляров конфигурации
rabbitmq_config = RabbitMQConfig()
worker_config = WorkerConfig()
systems_config = SystemsConfig()
sent_queues_config = SentQueuesConfig() 