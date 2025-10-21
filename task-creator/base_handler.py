#!/usr/bin/env python3
"""
Базовый класс для обработчиков сообщений
"""
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from loguru import logger
from rabbitmq_publisher import RabbitMQPublisher


class BaseMessageHandler(ABC):
    """Базовый класс для всех обработчиков сообщений"""
    
    def __init__(self, system_name: str):
        """
        Инициализация базового обработчика
        
        Args:
            system_name: Название системы (например, "Bitrix24", "OpenProject")
        """
        self.system_name = system_name
        
        # RabbitMQ Publisher для отправки успешных сообщений
        self.publisher = RabbitMQPublisher()
        
        # Базовая статистика
        self.stats = {
            "total_messages": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "start_time": time.time(),
            "last_message_time": None,
            "sent_to_success_queue": 0,
            "failed_to_send_success": 0
        }
        
        logger.info(f"{self.system_name} Handler: Инициализирован обработчик")
    
    def process_message(self, message_data: Dict[str, Any], properties: Any) -> bool:
        """
        Публичный метод обработки сообщения
        
        Args:
            message_data: Данные сообщения из RabbitMQ
            properties: Свойства сообщения RabbitMQ
            
        Returns:
            True если сообщение успешно обработано, False иначе
        """
        # Обновление базовой статистики
        self.stats["total_messages"] += 1
        self.stats["last_message_time"] = time.time()
        
        task_id = message_data.get('task_id', 'unknown')
        topic = message_data.get('topic', 'unknown')
        
        logger.info(f"{self.system_name} Handler: Обработка сообщения task_id={task_id}, topic={topic}")
        
        try:
            # Вызов конкретной реализации обработки
            result = self._process_message_impl(message_data, properties)
            
            if result:
                self.stats["successful_tasks"] += 1
                
                # Получение данных ответа от системы
                response_data = self._get_response_data(result, message_data)
                
                if response_data:
                    # Отправка успешного результата в очередь
                    original_queue = self._get_original_queue_name()
                    success_sent = self._send_success_message(message_data, response_data, original_queue)
                    
                    if success_sent:
                        self.stats["sent_to_success_queue"] += 1
                    else:
                        self.stats["failed_to_send_success"] += 1
                        logger.warning(f"{self.system_name} Handler: Не удалось отправить результат в очередь успешных сообщений")
                
                return True
            else:
                self.stats["failed_tasks"] += 1
                return False
                
        except Exception as e:
            self.stats["failed_tasks"] += 1
            logger.error(f"{self.system_name} Handler: Критическая ошибка при обработке сообщения: {e}")
            return False
    
    @abstractmethod
    def _process_message_impl(self, message_data: Dict[str, Any], properties: Any) -> Optional[Dict[str, Any]]:
        """
        Конкретная реализация обработки сообщения (должна быть реализована в наследниках)
        
        Args:
            message_data: Данные сообщения из RabbitMQ
            properties: Свойства сообщения RabbitMQ
            
        Returns:
            Результат обработки (например, ответ от API) или None в случае ошибки
        """
        pass
    
    @abstractmethod
    def _get_original_queue_name(self) -> str:
        """
        Получение имени исходной очереди для данного обработчика
        
        Returns:
            Имя очереди (например, "bitrix24.queue")
        """
        pass
    
    def _get_response_data(self, result: Dict[str, Any], original_message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Извлечение данных ответа от системы
        
        Args:
            result: Результат обработки из _process_message_impl
            original_message: Исходное сообщение
            
        Returns:
            Данные ответа или None
        """
        # Базовая реализация - возвращает результат как есть
        return result
    
    def _send_success_message(self, original_message: Dict[str, Any], 
                             response_data: Dict[str, Any], original_queue: str) -> bool:
        """
        Отправка сообщения об успешной обработке в очередь sent messages
        
        Args:
            original_message: Исходное сообщение из RabbitMQ
            response_data: Данные ответа от системы
            original_queue: Имя исходной очереди
            
        Returns:
            True если сообщение успешно отправлено, False иначе
        """
        try:
            # Подключение к RabbitMQ если нет соединения
            if not self.publisher.is_connected():
                if not self.publisher.connect():
                    logger.error(f"{self.system_name} Handler: Не удалось подключиться к RabbitMQ для отправки успешного сообщения")
                    return False
            
            # Отправка сообщения через publisher
            success = self.publisher.publish_success_message(
                original_queue=original_queue,
                original_message=original_message, 
                response_data=response_data
            )
            
            if success:
                task_id = original_message.get('task_id', 'unknown')
                logger.info(f"{self.system_name} Handler: Результат обработки задачи {task_id} отправлен в очередь успешных сообщений")
            
            return success
            
        except Exception as e:
            logger.error(f"{self.system_name} Handler: Ошибка при отправке успешного сообщения: {e}")
            return False
    
    def _send_success_message_with_retry(self, original_message: Dict[str, Any], 
                                       response_data: Dict[str, Any], original_queue: str, 
                                       max_attempts: int = 5) -> bool:
        """
        Отправка сообщения об успешной обработке в очередь sent messages с retry
        
        Args:
            original_message: Исходное сообщение из RabbitMQ
            response_data: Данные ответа от системы
            original_queue: Имя исходной очереди
            max_attempts: Максимальное количество попыток
            
        Returns:
            True если сообщение успешно отправлено, False иначе
        """
        task_id = original_message.get('task_id', 'unknown')
        
        for attempt in range(max_attempts):
            try:
                logger.debug(f"{self.system_name} Handler: Попытка {attempt + 1}/{max_attempts} отправки результата задачи {task_id}")
                
                if self._send_success_message(original_message, response_data, original_queue):
                    logger.info(f"{self.system_name} Handler: Результат задачи {task_id} успешно отправлен в очередь успешных сообщений (попытка {attempt + 1})")
                    return True
                
                # Если не последняя попытка - ждем перед повтором
                if attempt < max_attempts - 1:
                    wait_time = 2 ** attempt  # 1, 2, 4, 8, 16 секунд
                    logger.warning(f"{self.system_name} Handler: Попытка {attempt + 1} не удалась, повтор через {wait_time}s")
                    time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"{self.system_name} Handler: Ошибка попытки {attempt + 1} отправки результата задачи {task_id}: {e}")
                
                # Если не последняя попытка - ждем перед повтором
                if attempt < max_attempts - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"{self.system_name} Handler: Ошибка попытки {attempt + 1}, повтор через {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"{self.system_name} Handler: Все {max_attempts} попыток отправки результата задачи {task_id} провалились")
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики работы обработчика"""
        uptime = time.time() - self.stats["start_time"]
        
        return {
            "system": self.system_name,
            "uptime_seconds": uptime,
            "total_messages": self.stats["total_messages"],
            "successful_tasks": self.stats["successful_tasks"],
            "failed_tasks": self.stats["failed_tasks"],
            "sent_to_success_queue": self.stats["sent_to_success_queue"],
            "failed_to_send_success": self.stats["failed_to_send_success"],
            "success_rate": (
                self.stats["successful_tasks"] / self.stats["total_messages"] * 100
                if self.stats["total_messages"] > 0 else 0
            ),
            "success_queue_rate": (
                self.stats["sent_to_success_queue"] / self.stats["successful_tasks"] * 100
                if self.stats["successful_tasks"] > 0 else 0
            ),
            "last_message_time": self.stats["last_message_time"],
            "publisher_stats": self.publisher.get_stats()
        }
    
    def cleanup(self):
        """Очистка ресурсов при завершении работы"""
        try:
            if hasattr(self, 'publisher') and self.publisher:
                self.publisher.disconnect()
                logger.info(f"{self.system_name} Handler: Publisher отключен при очистке ресурсов")
        except Exception as e:
            logger.error(f"{self.system_name} Handler: Ошибка при очистке ресурсов: {e}")


class StubHandler(BaseMessageHandler):
    """Базовый класс для заглушек обработчиков"""
    
    def __init__(self, system_name: str, queue_name: str):
        """
        Инициализация заглушки
        
        Args:
            system_name: Название системы
            queue_name: Имя очереди
        """
        super().__init__(system_name)
        self.queue_name = queue_name
        logger.warning(f"🚧 {self.system_name} Handler: Инициализирована ЗАГЛУШКА модуля {self.system_name}")
    
    def _process_message_impl(self, message_data: Dict[str, Any], properties: Any) -> Optional[Dict[str, Any]]:
        """Имитация обработки сообщения"""
        task_id = message_data.get('task_id', 'unknown')
        topic = message_data.get('topic', 'unknown')
        
        logger.warning(
            f"🚧 {self.system_name} Handler (ЗАГЛУШКА): "
            f"Получено сообщение task_id={task_id}, topic={topic}. "
            f"Модуль {self.system_name} не реализован - это временная заглушка!"
        )
        
        # Имитируем ответ от системы
        mock_response = {
            "result": {
                "id": f"mock-{self.system_name.lower()}-{task_id}",
                "status": "processed"
            },
            "success": True
        }
        
        return mock_response
    
    def _get_original_queue_name(self) -> str:
        """Возвращает имя очереди для заглушки"""
        return self.queue_name
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики заглушки"""
        stats = super().get_stats()
        stats["handler_type"] = "stub"
        return stats 