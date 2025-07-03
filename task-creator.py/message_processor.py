#!/usr/bin/env python3
"""
Главный модуль обработки сообщений из RabbitMQ для всех внешних систем
"""
import signal
import sys
import time
import threading
from typing import Dict, Any
from loguru import logger

from config import worker_config, systems_config
from rabbitmq_consumer import RabbitMQConsumer
import importlib


class MessageProcessor:
    """Главный обработчик сообщений для всех внешних систем"""
    
    def __init__(self):
        self.config = worker_config
        self.systems_config = systems_config
        
        # Компоненты
        self.consumer = RabbitMQConsumer()
        
        # Обработчики для разных систем (загружаются динамически)
        self.handlers = {}
        self._load_handlers()
        
        # Управление работой
        self.running = False
        self.shutdown_event = threading.Event()
        
        # Статистика
        self.stats = {
            "start_time": None,
            "total_messages": 0,
            "processed_messages": 0,
            "failed_messages": 0,
            "handler_stats": {}
        }
        
        # Настройка обработки сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _load_handlers(self):
        """Динамическая загрузка обработчиков из модулей"""
        active_queues = self.systems_config.get_active_queues()
        
        for queue_name in active_queues:
            try:
                handler_info = self.systems_config.get_handler_info(queue_name)
                if not handler_info:
                    continue
                
                module_path = handler_info["module"]
                handler_class_name = handler_info["handler_class"]
                
                # Импорт модуля
                module = importlib.import_module(module_path)
                
                # Получение класса обработчика
                handler_class = getattr(module, handler_class_name)
                
                # Создание экземпляра обработчика
                handler_instance = handler_class()
                
                # Определение ключа для обработчика (название очереди без .queue)
                handler_key = queue_name.replace('.queue', '')
                self.handlers[handler_key] = handler_instance
                
                logger.info(f"Загружен обработчик {handler_class_name} для {queue_name}")
                
            except Exception as e:
                logger.error(f"Ошибка загрузки обработчика для {queue_name}: {e}")
        
        logger.info(f"Загружено {len(self.handlers)} обработчиков")
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов завершения"""
        logger.info(f"Получен сигнал {signum}, завершение работы...")
        self.shutdown()
        sys.exit(0)
    
    def initialize(self) -> bool:
        """Инициализация компонентов"""
        try:
            logger.info("Инициализация Message Processor...")
            
            # Подключение к RabbitMQ
            if not self.consumer.connect():
                logger.error("Не удалось подключиться к RabbitMQ")
                return False
            
            # Регистрация обработчиков для очередей
            registered_count = 0
            active_queues = self.systems_config.get_active_queues()
            
            for queue_name in active_queues:
                handler_key = queue_name.replace('.queue', '')
                
                if handler_key in self.handlers:
                    # Создаем wrapper для обработчика
                    handler = self.handlers[handler_key]
                    
                    def create_handler_wrapper(h, hk):
                        def wrapper(message_data: Dict[str, Any], properties: Any) -> bool:
                            return self._process_message_with_stats(h, hk, message_data, properties)
                        return wrapper
                    
                    # Регистрация обработчика
                    self.consumer.register_queue_handler(
                        queue_name, 
                        create_handler_wrapper(handler, handler_key)
                    )
                    registered_count += 1
                    logger.info(f"Зарегистрирован обработчик {handler_key} для очереди {queue_name}")
                else:
                    logger.warning(f"Нет обработчика для очереди {queue_name}")
            
            if registered_count == 0:
                logger.error("Не зарегистрировано ни одного обработчика")
                return False
            
            logger.info(f"Инициализация завершена успешно ({registered_count} обработчиков)")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации: {e}")
            return False
    
    def _process_message_with_stats(self, handler: Any, handler_type: str, 
                                  message_data: Dict[str, Any], properties: Any) -> bool:
        """Обработка сообщения с ведением статистики"""
        start_time = time.time()
        
        try:
            # Обновление общей статистики
            self.stats["total_messages"] += 1
            
            # Инициализация статистики обработчика
            if handler_type not in self.stats["handler_stats"]:
                self.stats["handler_stats"][handler_type] = {
                    "total": 0,
                    "processed": 0,
                    "failed": 0,
                    "avg_processing_time": 0,
                    "last_message_time": None
                }
            
            handler_stats = self.stats["handler_stats"][handler_type]
            handler_stats["total"] += 1
            handler_stats["last_message_time"] = time.time()
            
            # Вызов обработчика
            success = handler.process_message(message_data, properties)
            
            # Обновление статистики
            processing_time = time.time() - start_time
            
            if success:
                self.stats["processed_messages"] += 1
                handler_stats["processed"] += 1
                logger.debug(f"Сообщение обработано успешно за {processing_time:.2f}s")
            else:
                self.stats["failed_messages"] += 1
                handler_stats["failed"] += 1
                logger.warning(f"Ошибка обработки сообщения за {processing_time:.2f}s")
            
            # Обновление среднего времени обработки
            total_processed = handler_stats["processed"] + handler_stats["failed"]
            if total_processed > 0:
                current_avg = handler_stats["avg_processing_time"]
                handler_stats["avg_processing_time"] = (
                    (current_avg * (total_processed - 1) + processing_time) / total_processed
                )
            
            return success
            
        except Exception as e:
            self.stats["failed_messages"] += 1
            if handler_type in self.stats["handler_stats"]:
                self.stats["handler_stats"][handler_type]["failed"] += 1
            
            logger.error(f"Критическая ошибка при обработке сообщения через {handler_type}: {e}")
            return False
    
    def start(self) -> bool:
        """Запуск обработчика сообщений"""
        try:
            if not self.initialize():
                logger.error("Инициализация не удалась")
                return False
            
            logger.info("Запуск Message Processor...")
            self.stats["start_time"] = time.time()
            self.running = True
            
            # Запуск мониторинга в отдельном потоке
            monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
                name="Monitor"
            )
            monitor_thread.start()
            
            # Запуск основного цикла потребления (блокирующий)
            logger.info("Message Processor запущен и ожидает сообщения...")
            success = self.consumer.start_consuming()
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка запуска Message Processor: {e}")
            self.shutdown()
            return False
    
    def _monitor_loop(self):
        """Поток мониторинга статистики"""
        while not self.shutdown_event.is_set() and self.running:
            try:
                if self.stats["start_time"]:
                    uptime = time.time() - self.stats["start_time"]
                    
                    # Общая статистика
                    logger.info(
                        f"Monitor - Uptime: {uptime:.0f}s | "
                        f"Всего: {self.stats['total_messages']} | "
                        f"Обработано: {self.stats['processed_messages']} | "
                        f"Ошибки: {self.stats['failed_messages']}"
                    )
                    
                    # Статистика по обработчикам
                    for handler_type, stats in self.stats["handler_stats"].items():
                        if stats["total"] > 0:
                            success_rate = (stats["processed"] / stats["total"]) * 100
                            logger.info(
                                f"  {handler_type}: {stats['total']} сообщений, "
                                f"успех: {success_rate:.1f}%, "
                                f"время: {stats['avg_processing_time']:.2f}s"
                            )
                    
                    # Проверка соединения с RabbitMQ
                    if not self.consumer.is_connected():
                        logger.warning("RabbitMQ соединение потеряно, попытка переподключения...")
                        if self.consumer.reconnect():
                            logger.info("Переподключение к RabbitMQ успешно")
                        else:
                            logger.error("Не удалось переподключиться к RabbitMQ")
                
                # Мониторинг каждые HEARTBEAT_INTERVAL секунд
                self.shutdown_event.wait(self.config.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"Ошибка в мониторинге: {e}")
                self.shutdown_event.wait(10)
    
    def shutdown(self):
        """Корректное завершение работы"""
        logger.info("Завершение работы Message Processor...")
        self.running = False
        self.shutdown_event.set()
        
        # Остановка потребления сообщений
        self.consumer.stop_consuming()
        
        # Закрытие соединения с RabbitMQ
        self.consumer.disconnect()
        
        # Финальная статистика
        if self.stats["start_time"]:
            uptime = time.time() - self.stats["start_time"]
            logger.info(
                f"Финальная статистика - Uptime: {uptime:.0f}s | "
                f"Всего: {self.stats['total_messages']} | "
                f"Обработано: {self.stats['processed_messages']} | "
                f"Ошибки: {self.stats['failed_messages']}"
            )
            
            # Статистика по обработчикам
            for handler_type, stats in self.stats["handler_stats"].items():
                if stats["total"] > 0:
                    success_rate = (stats["processed"] / stats["total"]) * 100
                    logger.info(
                        f"  {handler_type}: {stats['total']} сообщений, "
                        f"успех: {success_rate:.1f}%, "
                        f"среднее время: {stats['avg_processing_time']:.2f}s"
                    )
        
        logger.info("Message Processor завершен")
    
    def get_status(self) -> Dict[str, Any]:
        """Получение текущего статуса обработчика"""
        uptime = time.time() - self.stats["start_time"] if self.stats["start_time"] else 0
        
        # Получение статистики от RabbitMQ consumer
        consumer_stats = self.consumer.get_stats()
        
        # Получение статистики от обработчиков
        handler_detailed_stats = {}
        for handler_type, handler in self.handlers.items():
            if hasattr(handler, 'get_stats'):
                handler_detailed_stats[handler_type] = handler.get_stats()
        
        return {
            "is_running": self.running,
            "uptime_seconds": uptime,
            "stats": self.stats.copy(),
            "consumer_stats": consumer_stats,
            "handler_stats": handler_detailed_stats,
            "registered_handlers": list(self.handlers.keys()),
            "registered_queues": list(self.consumer.queue_handlers.keys())
        } 