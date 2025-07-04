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

from config import worker_config, systems_config, tracker_config
from rabbitmq_consumer import RabbitMQConsumer
import importlib


class MessageProcessor:
    """Главный обработчик сообщений для всех внешних систем"""
    
    def __init__(self):
        self.config = worker_config
        self.systems_config = systems_config
        self.tracker_config = tracker_config
        
        # Компоненты
        self.consumer = RabbitMQConsumer()
        
        # Обработчики для разных систем (загружаются динамически)
        self.handlers = {}
        self._load_handlers()
        
        # Tracker'ы для отслеживания задач (загружаются динамически)
        self.trackers = {}
        self._load_trackers()
        
        # Управление работой
        self.running = False
        self.shutdown_event = threading.Event()
        
        # Потоки для tracker'ов
        self.tracker_threads = {}
        
        # Статистика
        self.stats = {
            "start_time": None,
            "total_messages": 0,
            "processed_messages": 0,
            "failed_messages": 0,
            "handler_stats": {},
            "tracker_stats": {}
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
    
    def _load_trackers(self):
        """Динамическая загрузка tracker'ов из модулей"""
        active_trackers = self.tracker_config.get_active_trackers()
        
        for sent_queue in active_trackers:
            try:
                tracker_info = self.tracker_config.get_tracker_info(sent_queue)
                if not tracker_info:
                    continue
                
                module_path = tracker_info["module"]
                tracker_class_name = tracker_info["tracker_class"]
                
                # Импорт модуля
                module = importlib.import_module(module_path)
                
                # Получение класса tracker'а
                tracker_class = getattr(module, tracker_class_name)
                
                # Создание экземпляра tracker'а
                tracker_instance = tracker_class()
                
                # Определение ключа для tracker'а (название очереди без .sent.queue)
                tracker_key = sent_queue.replace('.sent.queue', '_tracker')
                self.trackers[tracker_key] = tracker_instance
                
                logger.info(f"Загружен tracker {tracker_class_name} для {sent_queue}")
                
            except Exception as e:
                logger.error(f"Ошибка загрузки tracker'а для {sent_queue}: {e}")
        
        logger.info(f"Загружено {len(self.trackers)} tracker'ов")
    
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
            
            logger.info(f"Инициализация завершена успешно ({registered_count} обработчиков, {len(self.trackers)} tracker'ов)")
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
    
    def _start_trackers(self):
        """Запуск tracker'ов в отдельных потоках"""
        for tracker_key, tracker in self.trackers.items():
            try:
                # Создаем поток для tracker'а
                thread = threading.Thread(
                    target=self._tracker_worker,
                    args=(tracker_key, tracker),
                    daemon=True,
                    name=f"Tracker-{tracker_key}"
                )
                
                # Запускаем поток
                thread.start()
                self.tracker_threads[tracker_key] = thread
                
                logger.info(f"Запущен tracker {tracker_key} в отдельном потоке")
                
            except Exception as e:
                logger.error(f"Ошибка запуска tracker'а {tracker_key}: {e}")
        
        logger.info(f"Запущено {len(self.tracker_threads)} tracker'ов")
    
    def _tracker_worker(self, tracker_key: str, tracker):
        """Рабочий метод для tracker'а в отдельном потоке"""
        try:
            logger.info(f"Поток tracker'а {tracker_key} запущен")
            
            # Инициализация статистики tracker'а
            self.stats["tracker_stats"][tracker_key] = {
                "start_time": time.time(),
                "last_check_time": None,
                "cycles_completed": 0,
                "errors": 0
            }
            
            # Основной цикл tracker'а
            while not self.shutdown_event.is_set() and self.running:
                try:
                    cycle_start = time.time()
                    
                    # Вызов метода проверки tracker'а
                    tracker._check_tasks_in_queue()
                    
                    # Обновление статистики
                    tracker_stats = self.stats["tracker_stats"][tracker_key]
                    tracker_stats["last_check_time"] = time.time()
                    tracker_stats["cycles_completed"] += 1
                    
                    # Ожидание следующего цикла
                    self.shutdown_event.wait(self.config.heartbeat_interval)
                    
                except Exception as e:
                    logger.error(f"Ошибка в цикле tracker'а {tracker_key}: {e}")
                    if tracker_key in self.stats["tracker_stats"]:
                        self.stats["tracker_stats"][tracker_key]["errors"] += 1
                    
                    # Задержка при ошибке
                    self.shutdown_event.wait(30)
            
            logger.info(f"Поток tracker'а {tracker_key} завершен")
            
        except Exception as e:
            logger.error(f"Критическая ошибка в потоке tracker'а {tracker_key}: {e}")
    
    def start(self) -> bool:
        """Запуск обработчика сообщений"""
        try:
            if not self.initialize():
                logger.error("Инициализация не удалась")
                return False
            
            logger.info("Запуск Message Processor...")
            self.stats["start_time"] = time.time()
            self.running = True
            
            # Запуск tracker'ов в отдельных потоках
            self._start_trackers()
            
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
                    
                    # Статистика по tracker'ам
                    for tracker_key, stats in self.stats["tracker_stats"].items():
                        if stats["cycles_completed"] > 0:
                            tracker_uptime = time.time() - stats["start_time"]
                            logger.info(
                                f"  {tracker_key}: {stats['cycles_completed']} циклов, "
                                f"uptime: {tracker_uptime:.0f}s, "
                                f"ошибки: {stats['errors']}"
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
        
        # Ожидание завершения tracker'ов
        for tracker_key, thread in self.tracker_threads.items():
            if thread.is_alive():
                logger.info(f"Ожидание завершения tracker'а {tracker_key}...")
                thread.join(timeout=10)
                if thread.is_alive():
                    logger.warning(f"Tracker {tracker_key} не завершился за 10 секунд")
        
        # Очистка ресурсов tracker'ов
        for tracker in self.trackers.values():
            try:
                if hasattr(tracker, 'cleanup'):
                    tracker.cleanup()
            except Exception as e:
                logger.error(f"Ошибка очистки tracker'а: {e}")
        
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
            
            # Статистика по tracker'ам
            for tracker_key, stats in self.stats["tracker_stats"].items():
                if stats["cycles_completed"] > 0:
                    tracker_uptime = time.time() - stats["start_time"]
                    logger.info(
                        f"  {tracker_key}: {stats['cycles_completed']} циклов, "
                        f"uptime: {tracker_uptime:.0f}s, "
                        f"ошибки: {stats['errors']}"
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
        
        # Получение статистики от tracker'ов
        tracker_detailed_stats = {}
        for tracker_key, tracker in self.trackers.items():
            if hasattr(tracker, 'get_stats'):
                tracker_detailed_stats[tracker_key] = tracker.get_stats()
        
        return {
            "is_running": self.running,
            "uptime_seconds": uptime,
            "stats": self.stats.copy(),
            "consumer_stats": consumer_stats,
            "handler_stats": handler_detailed_stats,
            "tracker_stats": tracker_detailed_stats,
            "registered_handlers": list(self.handlers.keys()),
            "registered_trackers": list(self.trackers.keys()),
            "registered_queues": list(self.consumer.queue_handlers.keys()) if hasattr(self.consumer, 'queue_handlers') else [],
            "active_tracker_threads": [name for name, thread in self.tracker_threads.items() if thread.is_alive()]
        } 