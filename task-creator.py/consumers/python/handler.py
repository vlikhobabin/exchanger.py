#!/usr/bin/env python3
"""
Заглушка обработчика сообщений для Python Services
"""
import time
from typing import Dict, Any
from loguru import logger
from rabbitmq_publisher import RabbitMQPublisher


class PythonServiceHandler:
    """Заглушка обработчика для вызова Python сервисов"""
    
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
        
        logger.warning("🚧 Python Services Handler: Инициализирована ЗАГЛУШКА модуля Python Services")
    
    def process_message(self, message_data: Dict[str, Any], properties: Any) -> bool:
        """
        Заглушка обработки сообщения для Python Services
        
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
            f"🚧 Python Services Handler (ЗАГЛУШКА): "
            f"Получено сообщение task_id={task_id}, topic={topic}. "
            f"Модуль Python Services не реализован - это временная заглушка!"
        )
        
        # Имитируем успешную обработку
        self.stats["successful_tasks"] += 1
        
        # Имитируем ответ от Python Service
        mock_response = {
            "result": {
                "service": {
                    "id": f"mock-py-{task_id}",
                    "status": "executed"
                }
            },
            "success": True
        }
        
        # Отправка успешного результата в очередь
        success_sent = self._send_success_message(message_data, mock_response, "python-services.queue")
        if success_sent:
            self.stats["sent_to_success_queue"] += 1
        else:
            self.stats["failed_to_send_success"] += 1
            logger.warning("🚧 Python Services Handler: Не удалось отправить результат в очередь успешных сообщений")
        
        return True
    
    def _send_success_message(self, original_message: Dict[str, Any], 
                             mock_response: Dict[str, Any], original_queue: str) -> bool:
        """
        Отправка сообщения об успешной обработке (stub)
        
        Args:
            original_message: Исходное сообщение из RabbitMQ
            mock_response: Имитированный ответ от Python Service
            original_queue: Имя исходной очереди
            
        Returns:
            True если сообщение успешно отправлено, False иначе
        """
        try:
            # Подключение к RabbitMQ если нет соединения
            if not self.publisher.is_connected():
                if not self.publisher.connect():
                    logger.error("🚧 Python Services Handler: Не удалось подключиться к RabbitMQ для отправки успешного сообщения")
                    return False
            
            # Отправка сообщения через publisher
            success = self.publisher.publish_success_message(
                original_queue=original_queue,
                original_message=original_message, 
                response_data=mock_response
            )
            
            if success:
                service_id = mock_response.get('result', {}).get('service', {}).get('id', 'unknown')
                logger.info(f"🚧 Python Services Handler: Результат выполнения сервиса {service_id} отправлен в очередь успешных сообщений")
            
            return success
            
        except Exception as e:
            logger.error(f"🚧 Python Services Handler: Ошибка при отправке успешного сообщения: {e}")
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
            "system": "Python Services",
            "publisher_stats": self.publisher.get_stats()
        }
    
    def cleanup(self):
        """Очистка ресурсов при завершении работы"""
        try:
            if hasattr(self, 'publisher') and self.publisher:
                self.publisher.disconnect()
                logger.info("🚧 Python Services Handler: Publisher отключен при очистке ресурсов")
        except Exception as e:
            logger.error(f"🚧 Python Services Handler: Ошибка при очистке ресурсов: {e}") 