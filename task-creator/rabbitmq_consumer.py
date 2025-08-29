#!/usr/bin/env python3
"""
RabbitMQ Consumer для чтения сообщений из очередей
"""
import json
import pika
import time
from typing import Dict, Any, Optional, Callable
from loguru import logger
from config import rabbitmq_config, systems_config


class RabbitMQConsumer:
    """Consumer для чтения сообщений из RabbitMQ очередей"""
    
    def __init__(self):
        self.config = rabbitmq_config
        self.systems_config = systems_config
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        self.consuming = False
        
        # Обработчики для разных очередей
        self.queue_handlers: Dict[str, Callable] = {}
        
        # Статистика
        self.stats = {
            "total_messages": 0,
            "processed_messages": 0,
            "failed_messages": 0,
            "start_time": None,
            "queue_stats": {}
        }
    
    def connect(self) -> bool:
        """Подключение к RabbitMQ"""
        try:
            # Настройка подключения
            credentials = pika.PlainCredentials(
                username=self.config.username,
                password=self.config.password
            )
            
            parameters = pika.ConnectionParameters(
                host=self.config.host,
                port=self.config.port,
                virtual_host=self.config.virtual_host,
                credentials=credentials,
                heartbeat=self.config.heartbeat,
                blocked_connection_timeout=self.config.blocked_connection_timeout,
            )
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            logger.info(f"Подключение к RabbitMQ успешно: {self.config.host}:{self.config.port}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка подключения к RabbitMQ: {e}")
            return False
    
    def register_queue_handler(self, queue_name: str, handler_callback: Callable):
        """Регистрация обработчика для очереди"""
        self.queue_handlers[queue_name] = handler_callback
        logger.info(f"Зарегистрирован обработчик для очереди: {queue_name}")
    
    def setup_queue_consumption(self, queue_name: str) -> bool:
        """Настройка потребления для очереди"""
        try:
            if not self.channel:
                logger.error("Нет активного соединения с RabbitMQ")
                return False
            
            if queue_name not in self.queue_handlers:
                logger.error(f"Нет обработчика для очереди: {queue_name}")
                return False
            
            # Проверяем, что очередь существует
            try:
                self.channel.queue_declare(queue=queue_name, passive=True)
            except Exception as e:
                logger.error(f"Очередь {queue_name} не существует: {e}")
                return False
            
            # Создаем wrapper для обработчика с логированием и статистикой
            def message_wrapper(ch, method, properties, body):
                return self._process_message_wrapper(
                    queue_name, ch, method, properties, body
                )
            
            # Настройка потребления
            self.channel.basic_qos(prefetch_count=1)  # По одному сообщению за раз
            self.channel.basic_consume(
                queue=queue_name,
                on_message_callback=message_wrapper,
                auto_ack=False  # Ручное подтверждение
            )
            
            logger.info(f"Настроено потребление для очереди: {queue_name}")
            
            # Инициализация статистики для очереди
            if queue_name not in self.stats["queue_stats"]:
                self.stats["queue_stats"][queue_name] = {
                    "total": 0,
                    "processed": 0,
                    "failed": 0,
                    "last_message_time": None
                }
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка настройки потребления для очереди {queue_name}: {e}")
            return False
    
    def _process_message_wrapper(self, queue_name: str, ch, method, properties, body):
        """Wrapper для обработки сообщений с логированием и статистикой"""
        message_id = None
        start_time = time.time()
        
        try:
            # Парсинг сообщения
            try:
                message_data = json.loads(body.decode('utf-8'))
                message_id = message_data.get('task_id', 'unknown')
            except Exception as e:
                logger.error(f"Ошибка парсинга сообщения из {queue_name}: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                self._update_stats(queue_name, False)
                return
            
            # Обновление статистики
            self.stats["total_messages"] += 1
            self.stats["queue_stats"][queue_name]["total"] += 1
            self.stats["queue_stats"][queue_name]["last_message_time"] = time.time()
            
            logger.info(f"Получено сообщение из {queue_name}: {message_id}")
            logger.debug(f"Содержимое сообщения: {json.dumps(message_data, ensure_ascii=False, indent=2)}")
            
            # Вызов обработчика
            handler = self.queue_handlers[queue_name]
            success = handler(message_data, properties)
            
            # Подтверждение или отклонение сообщения
            if success:
                ch.basic_ack(delivery_tag=method.delivery_tag)
                self._update_stats(queue_name, True)
                
                processing_time = time.time() - start_time
                logger.info(f"Сообщение {message_id} из {queue_name} успешно обработано за {processing_time:.2f}s")
            else:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                self._update_stats(queue_name, False)
                logger.error(f"Ошибка обработки сообщения {message_id} из {queue_name}")
                
        except Exception as e:
            logger.error(f"Критическая ошибка при обработке сообщения {message_id} из {queue_name}: {e}")
            try:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            except:
                pass
            self._update_stats(queue_name, False)
    
    def _update_stats(self, queue_name: str, success: bool):
        """Обновление статистики"""
        if success:
            self.stats["processed_messages"] += 1
            self.stats["queue_stats"][queue_name]["processed"] += 1
        else:
            self.stats["failed_messages"] += 1
            self.stats["queue_stats"][queue_name]["failed"] += 1
    
    def start_consuming(self) -> bool:
        """Запуск потребления сообщений из всех зарегистрированных очередей"""
        try:
            if not self.channel:
                logger.error("Нет активного соединения с RabbitMQ")
                return False
            
            # Настройка потребления для всех зарегистрированных очередей
            setup_count = 0
            for queue_name in self.queue_handlers.keys():
                if self.setup_queue_consumption(queue_name):
                    setup_count += 1
                else:
                    logger.error(f"Не удалось настроить потребление для {queue_name}")
            
            if setup_count == 0:
                logger.error("Не удалось настроить потребление ни для одной очереди")
                return False
            
            logger.info(f"Настроено потребление для {setup_count} очередей")
            self.stats["start_time"] = time.time()
            self.consuming = True
            
            # Запуск блокирующего потребления
            logger.info("Запуск потребления сообщений...")
            self.channel.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания")
            self.stop_consuming()
        except Exception as e:
            logger.error(f"Ошибка потребления сообщений: {e}")
            return False
        
        return True
    
    def stop_consuming(self):
        """Остановка потребления сообщений"""
        try:
            self.consuming = False
            if self.channel:
                self.channel.stop_consuming()
                logger.info("Потребление сообщений остановлено")
                
        except Exception as e:
            logger.error(f"Ошибка остановки потребления: {e}")
    
    def is_connected(self) -> bool:
        """Проверка активности соединения"""
        try:
            return (
                self.connection is not None and 
                not self.connection.is_closed and
                self.channel is not None and
                not self.channel.is_closed
            )
        except:
            return False
    
    def reconnect(self) -> bool:
        """Переподключение к RabbitMQ"""
        logger.info("Попытка переподключения к RabbitMQ...")
        self.disconnect()
        time.sleep(5)  # Задержка перед переподключением
        return self.connect()
    
    def disconnect(self):
        """Закрытие соединения"""
        try:
            self.consuming = False
            
            if self.channel and not self.channel.is_closed:
                self.channel.close()
                
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                
            logger.info("Соединение с RabbitMQ закрыто")
            
        except Exception as e:
            logger.error(f"Ошибка при закрытии соединения RabbitMQ: {e}")
        finally:
            self.connection = None
            self.channel = None
    
    def get_queue_info(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """Получение информации об очереди"""
        try:
            if not self.channel:
                return None
                
            method = self.channel.queue_declare(queue=queue_name, passive=True)
            return {
                "queue": queue_name,
                "message_count": method.method.message_count,
                "consumer_count": method.method.consumer_count
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации об очереди {queue_name}: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики работы"""
        uptime = time.time() - self.stats["start_time"] if self.stats["start_time"] else 0
        
        return {
            "uptime_seconds": uptime,
            "is_consuming": self.consuming,
            "is_connected": self.is_connected(),
            "registered_queues": list(self.queue_handlers.keys()),
            "total_messages": self.stats["total_messages"],
            "processed_messages": self.stats["processed_messages"],
            "failed_messages": self.stats["failed_messages"],
            "success_rate": (
                self.stats["processed_messages"] / self.stats["total_messages"] * 100
                if self.stats["total_messages"] > 0 else 0
            ),
            "queue_stats": self.stats["queue_stats"]
        } 