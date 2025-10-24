#!/usr/bin/env python3
"""
RabbitMQ Publisher для отправки сообщений в очереди
"""
import json
import time
import pika
from typing import Dict, Any, Optional
from loguru import logger
from config import rabbitmq_config, sent_queues_config


class RabbitMQPublisher:
    """Publisher для отправки сообщений в RabbitMQ очереди"""
    
    def __init__(self):
        self.config = rabbitmq_config
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        
        # Статистика
        self.stats = {
            "sent_messages": 0,
            "failed_messages": 0,
            "last_message_time": None
        }
    
    def _handle_connection_error(self, error) -> bool:
        """Обработка ошибок соединения с автоматическим переподключением"""
        error_str = str(error)
        connection_errors = [
            "Connection reset by peer",
            "IndexError", 
            "pop from an empty deque",
            "Stream connection lost",
            "ConnectionResetError",
            "Broken pipe",
            "Connection refused"
        ]
        
        if any(err in error_str for err in connection_errors):
            logger.warning(f"Обнаружена ошибка соединения: {error_str}, переподключаемся...")
            # Закрываем существующие соединения перед переподключением
            try:
                if self.channel and not self.channel.is_closed:
                    self.channel.close()
                if self.connection and not self.connection.is_closed:
                    self.connection.close()
            except:
                pass
            
            # Сбрасываем состояние
            self.connection = None
            self.channel = None
            
            return self.connect()
        return False

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
            
            logger.info(f"Publisher подключен к RabbitMQ: {self.config.host}:{self.config.port}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка подключения Publisher к RabbitMQ: {e}")
            return False
    
    def publish_message(self, queue_name: str, message_data: Dict[str, Any], 
                       exchange: str = "", persistent: bool = True) -> bool:
        """
        Отправка сообщения в очередь
        
        Args:
            queue_name: Имя очереди
            message_data: Данные сообщения
            exchange: Имя exchange (по умолчанию direct)
            persistent: Сделать сообщение persistent
            
        Returns:
            True если сообщение успешно отправлено, False иначе
        """
        # Подготовка сообщения заранее, чтобы избежать проблем с областью видимости
        message_json = json.dumps(message_data, ensure_ascii=False, default=str)
        properties = pika.BasicProperties(
            delivery_mode=2 if persistent else 1,  # 2 = persistent
            content_type='application/json',
            content_encoding='utf-8'
        )
        
        try:
            if not self.is_connected():
                logger.warning("Нет соединения с RabbitMQ, пытаемся переподключиться...")
                if not self.connect():
                    logger.error("Не удалось переподключиться к RabbitMQ")
                    return False
            
            # Проверяем/создаем очередь
            self.channel.queue_declare(queue=queue_name, durable=True)
            
            # Отправка сообщения
            self.channel.basic_publish(
                exchange=exchange,
                routing_key=queue_name,
                body=message_json.encode('utf-8'),
                properties=properties
            )
            
            # Обновление статистики
            self.stats["sent_messages"] += 1
            self.stats["last_message_time"] = message_data.get('timestamp') or 'unknown'
            
            logger.info(f"Сообщение успешно отправлено в очередь {queue_name}")
            logger.debug(f"Содержимое отправленного сообщения: {message_json[:200]}...")
            
            return True
            
        except Exception as e:
            self.stats["failed_messages"] += 1
            logger.error(f"Ошибка отправки сообщения в очередь {queue_name}: {e}")
            # Попытка автоматического переподключения при ошибках соединения
            if self._handle_connection_error(e):
                # Повторная попытка отправки после переподключения
                try:
                    self.channel.queue_declare(queue=queue_name, durable=True)
                    self.channel.basic_publish(
                        exchange=exchange,
                        routing_key=queue_name,
                        body=message_json.encode('utf-8'),
                        properties=properties
                    )
                    self.stats["sent_messages"] += 1
                    self.stats["failed_messages"] -= 1  # Отменяем предыдущий счетчик ошибок
                    logger.info(f"Сообщение успешно отправлено в очередь {queue_name} после переподключения")
                    return True
                except Exception as retry_error:
                    logger.error(f"Ошибка повторной отправки сообщения в очередь {queue_name}: {retry_error}")
            return False
    
    def publish_success_message(self, original_queue: str, original_message: Dict[str, Any], 
                               response_data: Dict[str, Any]) -> bool:
        """
        Отправка сообщения об успешной обработке в соответствующую очередь
        
        Args:
            original_queue: Исходная очередь (например, bitrix24.queue)
            original_message: Исходное сообщение
            response_data: Данные ответа от системы
            
        Returns:
            True если сообщение успешно отправлено, False иначе
        """
        try:
            # Определяем целевую очередь
            target_queue = self._get_success_queue_name(original_queue)
            
            if not target_queue:
                logger.error(f"Не удалось определить очередь успешных сообщений для {original_queue}")
                return False
            
            # Формирование объединенного сообщения
            success_message = {
                "timestamp": original_message.get('timestamp'),
                "original_queue": original_queue,
                "original_message": original_message,
                "response_data": response_data,
                "processing_status": "success",
                "processed_at": time.time()
            }
            
            # Добавляем timestamp если его нет
            if not success_message["timestamp"]:
                success_message["timestamp"] = time.time()
            
            return self.publish_message(target_queue, success_message)
            
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения об успешной обработке: {e}")
            return False
    
    def _get_success_queue_name(self, original_queue: str) -> Optional[str]:
        """
        Получение имени очереди для успешно обработанных сообщений
        
        Args:
            original_queue: Имя исходной очереди
            
        Returns:
            Имя целевой очереди или None
        """
        return sent_queues_config.get_sent_queue_name(original_queue)
    
    def is_connected(self) -> bool:
        """Проверка активного соединения"""
        try:
            return (self.connection is not None and 
                   not self.connection.is_closed and 
                   self.channel is not None and 
                   not self.channel.is_closed)
        except:
            return False
    
    def disconnect(self):
        """Закрытие соединения"""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("Publisher отключен от RabbitMQ")
        except Exception as e:
            logger.error(f"Ошибка при отключении Publisher: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики Publisher"""
        return {
            "sent_messages": self.stats["sent_messages"],
            "failed_messages": self.stats["failed_messages"],
            "last_message_time": self.stats["last_message_time"],
            "success_rate": (
                self.stats["sent_messages"] / 
                (self.stats["sent_messages"] + self.stats["failed_messages"])
            ) if (self.stats["sent_messages"] + self.stats["failed_messages"]) > 0 else 0.0,
            "is_connected": self.is_connected()
        } 