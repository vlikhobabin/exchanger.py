#!/usr/bin/env python3
"""
Заглушка обработчика сообщений для 1C
"""
import time
from typing import Dict, Any
from loguru import logger
from rabbitmq_publisher import RabbitMQPublisher


class OneСTaskHandler:
    """Заглушка обработчика для интеграции с 1C"""
    
    def __init__(self):
        # RabbitMQ Publisher для отправки успешных сообщений
        self.publisher = RabbitMQPublisher()
        
        # Статистика
        self.stats = {
            "total_messages": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "start_time": time.time(),
            "last_message_time": None,
            "sent_to_success_queue": 0,
            "failed_to_send_success": 0
        }
        
        logger.warning("🚧 1C Handler: Инициализирована ЗАГЛУШКА модуля 1C")
    
    def process_message(self, message_data: Dict[str, Any], properties: Any) -> bool:
        """
        Заглушка обработки сообщения для 1C
        
        Args:
            message_data: Данные сообщения из RabbitMQ
            properties: Свойства сообщения RabbitMQ
            
        Returns:
            True (заглушка всегда возвращает успех)
        """
        self.stats["total_messages"] += 1
        self.stats["last_message_time"] = time.time()
        
        task_id = message_data.get('task_id', 'unknown')
        topic = message_data.get('topic', 'unknown')
        
        logger.warning(
            f"🚧 1C Handler (ЗАГЛУШКА): "
            f"Получено сообщение task_id={task_id}, topic={topic}. "
            f"Модуль 1C не реализован - это временная заглушка!"
        )
        
        # Имитируем успешную обработку
        self.stats["successful_tasks"] += 1
        
        # Имитируем ответ от 1C
        mock_response = {
            "result": {
                "document": {
                    "id": f"mock-1c-{task_id}",
                    "status": "processed"
                }
            },
            "success": True
        }
        
        # Отправка успешного результата в очередь
        success_sent = self._send_success_message(message_data, mock_response, "1c.queue")
        if success_sent:
            self.stats["sent_to_success_queue"] += 1
        else:
            self.stats["failed_to_send_success"] += 1
            logger.warning("🚧 1C Handler: Не удалось отправить результат в очередь успешных сообщений")
        
        return True
    
    def _send_success_message(self, original_message: Dict[str, Any], 
                             mock_response: Dict[str, Any], original_queue: str) -> bool:
        """
        Отправка сообщения об успешной обработке (stub)
        
        Args:
            original_message: Исходное сообщение из RabbitMQ
            mock_response: Имитированный ответ от 1C
            original_queue: Имя исходной очереди
            
        Returns:
            True если сообщение успешно отправлено, False иначе
        """
        try:
            # Подключение к RabbitMQ если нет соединения
            if not self.publisher.is_connected():
                if not self.publisher.connect():
                    logger.error("🚧 1C Handler: Не удалось подключиться к RabbitMQ для отправки успешного сообщения")
                    return False
            
            # Отправка сообщения через publisher
            success = self.publisher.publish_success_message(
                original_queue=original_queue,
                original_message=original_message, 
                response_data=mock_response
            )
            
            if success:
                doc_id = mock_response.get('result', {}).get('document', {}).get('id', 'unknown')
                logger.info(f"🚧 1C Handler: Результат обработки документа {doc_id} отправлен в очередь успешных сообщений")
            
            return success
            
        except Exception as e:
            logger.error(f"🚧 1C Handler: Ошибка при отправке успешного сообщения: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики обработки"""
        current_time = time.time()
        uptime = current_time - self.stats["start_time"]
        
        return {
            **self.stats,
            "uptime_seconds": uptime,
            "success_rate": (
                self.stats["successful_tasks"] / self.stats["total_messages"] 
                if self.stats["total_messages"] > 0 else 0
            ),
            "success_queue_rate": (
                self.stats["sent_to_success_queue"] / self.stats["successful_tasks"] * 100
                if self.stats["successful_tasks"] > 0 else 0
            ),
            "messages_per_minute": (
                self.stats["total_messages"] / (uptime / 60) 
                if uptime > 0 else 0
            ),
            "handler_type": "stub",
            "system": "1C",
            "publisher_stats": self.publisher.get_stats()
        }
    
    def cleanup(self):
        """Очистка ресурсов при завершении работы"""
        try:
            if hasattr(self, 'publisher') and self.publisher:
                self.publisher.disconnect()
                logger.info("🚧 1C Handler: Publisher отключен при очистке ресурсов")
        except Exception as e:
            logger.error(f"🚧 1C Handler: Ошибка при очистке ресурсов: {e}") 