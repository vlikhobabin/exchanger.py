#!/usr/bin/env python3
"""
Универсальная конфигурация для системы обработки сообщений RabbitMQ
"""
import os
import sys
from typing import Dict, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings

# Импорт env_loader ДО любых других импортов, зависящих от переменных окружения
# Он загружает правильный .env файл на основе EXCHANGER_ENV
sys.path.insert(0, "/opt/exchanger.py")
from env_loader import EXCHANGER_ENV, get_log_path, get_env_info


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
    
    # Настройки логирования монитора
    monitor_log_interval: int = Field(default=300, env="MONITOR_LOG_INTERVAL")  # секунды
    
    # Настройки обработки сообщений
    max_messages_per_batch: int = Field(default=10, env="MAX_MESSAGES_PER_BATCH")
    message_processing_timeout: int = Field(default=120, env="MESSAGE_PROCESSING_TIMEOUT")  # секунды
    
    class Config:
        # Убираем env_prefix чтобы использовать переменные без префикса
        pass


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


class TrackerConfig:
    """
    Конфигурация tracker'ов для отслеживания задач в системах-получателях
    """
    
    # Маппинг sent очередей на модули tracker'ов
    TRACKER_HANDLERS: Dict[str, Dict[str, str]] = {
        "bitrix24.sent.queue": {
            "module": "consumers.bitrix",
            "tracker_class": "BitrixTaskTracker",
            "description": "Отслеживание задач в Bitrix24",
            "target_queue": "camunda.responses.queue"
        },
        "openproject.sent.queue": {
            "module": "consumers.openproject", 
            "tracker_class": "OpenProjectTaskTracker",
            "description": "Отслеживание задач в OpenProject",
            "target_queue": "camunda.responses.queue"
        },
        "1c.sent.queue": {
            "module": "consumers.1c",
            "tracker_class": "OneСTaskTracker", 
            "description": "Отслеживание задач в 1C",
            "target_queue": "camunda.responses.queue"
        },
        "python-services.sent.queue": {
            "module": "consumers.python",
            "tracker_class": "PythonServiceTracker",
            "description": "Отслеживание Python сервисов",
            "target_queue": "camunda.responses.queue"
        },
        "default.sent.queue": {
            "module": "consumers.default",
            "tracker_class": "DefaultTaskTracker",
            "description": "Отслеживание задач по умолчанию",
            "target_queue": "camunda.responses.queue"
        }
    }
    
    @classmethod
    def get_tracker_info(cls, sent_queue: str) -> Optional[Dict[str, str]]:
        """
        Получить информацию о tracker'е для очереди отправленных сообщений
        
        Args:
            sent_queue: Имя очереди отправленных сообщений
            
        Returns:
            Словарь с информацией о модуле и классе tracker'а
        """
        return cls.TRACKER_HANDLERS.get(sent_queue)
    
    @classmethod
    def get_all_sent_queues(cls) -> List[str]:
        """Получить список всех sent очередей для отслеживания"""
        return list(cls.TRACKER_HANDLERS.keys())
    
    @classmethod
    def get_active_trackers(cls) -> List[str]:
        """
        Получить список активных tracker'ов (тех, для которых реализованы классы)
        
        Returns:
            Список имен sent очередей
        """
        active_trackers = []
        for sent_queue, tracker_info in cls.TRACKER_HANDLERS.items():
            try:
                # Попытка импорта модуля для проверки что он существует
                module_name = tracker_info["module"]
                module = __import__(module_name, fromlist=[tracker_info["tracker_class"]])
                # Проверяем, что класс tracker'а существует
                if hasattr(module, tracker_info["tracker_class"]):
                    active_trackers.append(sent_queue)
            except (ImportError, AttributeError):
                # Модуль не найден или класс не существует - пропускаем этот tracker
                continue
        return active_trackers
    
    @classmethod
    def get_tracker_module_path(cls, sent_queue: str) -> Optional[str]:
        """Получить путь к модулю tracker'а"""
        tracker_info = cls.get_tracker_info(sent_queue)
        return tracker_info["module"] if tracker_info else None
    
    @classmethod
    def get_tracker_class_name(cls, sent_queue: str) -> Optional[str]:
        """Получить имя класса tracker'а"""
        tracker_info = cls.get_tracker_info(sent_queue)
        return tracker_info["tracker_class"] if tracker_info else None
    
    @classmethod
    def get_target_queue(cls, sent_queue: str) -> Optional[str]:
        """Получить целевую очередь для перемещения сообщений"""
        tracker_info = cls.get_tracker_info(sent_queue)
        return tracker_info["target_queue"] if tracker_info else None
    
    @classmethod
    def add_tracker_handler(cls, sent_queue: str, module: str, tracker_class: str, 
                           description: str = "", target_queue: str = "camunda.responses.queue"):
        """
        Добавить новый tracker обработчик (для динамического расширения)
        
        Args:
            sent_queue: Имя sent очереди
            module: Путь к модулю
            tracker_class: Имя класса tracker'а
            description: Описание tracker'а
            target_queue: Целевая очередь для перемещения сообщений
        """
        cls.TRACKER_HANDLERS[sent_queue] = {
            "module": module,
            "tracker_class": tracker_class,
            "description": description,
            "target_queue": target_queue
        }
    
    @classmethod
    def get_trackers_status(cls) -> Dict[str, Dict[str, any]]:
        """
        Получить статус всех tracker'ов
        
        Returns:
            Словарь со статусом каждого tracker'а
        """
        trackers_status = {}
        
        for sent_queue, tracker_info in cls.TRACKER_HANDLERS.items():
            module_name = tracker_info["module"]
            tracker_class_name = tracker_info["tracker_class"]
            try:
                module = __import__(module_name, fromlist=[tracker_class_name])
                if hasattr(module, tracker_class_name):
                    status = "active"
                    error = None
                else:
                    status = "inactive"
                    error = f"Класс {tracker_class_name} не найден в модуле {module_name}"
            except ImportError as e:
                status = "inactive"
                error = str(e)
            
            trackers_status[sent_queue] = {
                "module": module_name,
                "tracker_class": tracker_class_name,
                "description": tracker_info["description"],
                "target_queue": tracker_info["target_queue"],
                "status": status,
                "error": error
            }
        
        return trackers_status


# Создание экземпляров конфигурации
rabbitmq_config = RabbitMQConfig()
worker_config = WorkerConfig()
systems_config = SystemsConfig()
sent_queues_config = SentQueuesConfig() 
tracker_config = TrackerConfig() 