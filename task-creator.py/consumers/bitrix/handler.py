#!/usr/bin/env python3
"""
Обработчик сообщений для создания задач в Bitrix24
"""
import json
import requests
import time
from typing import Dict, Any, Optional
from loguru import logger
from .config import bitrix_config, worker_config
from rabbitmq_publisher import RabbitMQPublisher


class BitrixTaskHandler:
    """Обработчик для создания задач в Bitrix24"""
    
    def __init__(self):
        self.config = bitrix_config
        self.worker_config = worker_config
        self.task_add_url = f"{self.config.webhook_url}/tasks.task.add.json"
        
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
    
    def process_message(self, message_data: Dict[str, Any], properties: Any) -> bool:
        """
        Обработка сообщения из RabbitMQ и создание задачи в Bitrix24
        
        Args:
            message_data: Данные сообщения из RabbitMQ
            properties: Свойства сообщения RabbitMQ
            
        Returns:
            True если задача успешно создана, False иначе
        """
        self.stats["total_messages"] += 1
        self.stats["last_message_time"] = time.time()
        
        try:
            # Извлечение основных данных из сообщения
            task_id = message_data.get('task_id', 'unknown')
            topic = message_data.get('topic', 'unknown')
            variables = message_data.get('variables', {})
            metadata = message_data.get('metadata', {})
            
            logger.info(f"Обработка сообщения Bitrix24: task_id={task_id}, topic={topic}")
            
            # Создание задачи в Bitrix24
            result = self._create_bitrix_task(message_data)
            
            if result and not result.get('error'):
                self.stats["successful_tasks"] += 1
                task_id_bitrix = result.get('result', {}).get('task', {}).get('id')
                logger.info(f"Задача успешно создана в Bitrix24: ID={task_id_bitrix}")
                
                # Отправка успешного результата в очередь bitrix24.sent.queue
                success_sent = self._send_success_message(message_data, result, "bitrix24.queue")
                if success_sent:
                    self.stats["sent_to_success_queue"] += 1
                else:
                    self.stats["failed_to_send_success"] += 1
                    logger.warning("Не удалось отправить результат в очередь успешных сообщений")
                
                return True
            else:
                self.stats["failed_tasks"] += 1
                error_msg = result.get('error_description', 'Unknown error') if result else 'No response'
                logger.error(f"Ошибка создания задачи в Bitrix24: {error_msg}")
                return False
                
        except Exception as e:
            self.stats["failed_tasks"] += 1
            logger.error(f"Критическая ошибка при обработке сообщения: {e}")
            return False
    
    def _create_bitrix_task(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Создание задачи в Bitrix24 на основе данных сообщения
        
        Args:
            message_data: Данные сообщения из RabbitMQ
            
        Returns:
            Ответ от API Bitrix24
        """
        try:
            # Извлечение данных из сообщения
            task_id = message_data.get('task_id', 'unknown')
            topic = message_data.get('topic', 'unknown')
            variables = message_data.get('variables', {})
            metadata = message_data.get('metadata', {})
            
            # Формирование заголовка задачи
            title = self._extract_title(variables, metadata, topic)
            
            # Формирование описания (в первой версии - все данные сообщения)
            description = self._create_description(message_data)
            
            # Извлечение дополнительных параметров
            responsible_id = self._extract_responsible_id(variables, metadata)
            priority = self._extract_priority(variables, metadata)
            deadline = self._extract_deadline(variables, metadata)
            
            # Подготовка данных задачи для Bitrix24
            task_data = {
                'TITLE': title,
                'DESCRIPTION': description,
                'RESPONSIBLE_ID': responsible_id,
                'PRIORITY': priority,
                'CREATED_BY': responsible_id,
            }
            
            # Добавление дедлайна если указан
            if deadline:
                task_data['DEADLINE'] = deadline
            
            # Добавление дополнительных полей из метаданных
            additional_fields = self._extract_additional_fields(variables, metadata)
            task_data.update(additional_fields)
            
            # Подготовка данных для отправки
            payload = {'fields': task_data}
            
            logger.debug(f"Отправка задачи в Bitrix24: {json.dumps(payload, ensure_ascii=False, indent=2)}")
            
            # Отправка POST запроса
            response = requests.post(
                self.task_add_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=self.config.request_timeout
            )
            
            # Проверка статуса ответа
            response.raise_for_status()
            
            # Возврат результата
            result = response.json()
            
            if result.get('error'):
                logger.error(f"Ошибка API Bitrix24: {result['error']}")
                logger.error(f"Описание ошибки: {result.get('error_description', 'Не указано')}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            error_result = {
                'error': 'REQUEST_ERROR',
                'error_description': f'Ошибка запроса: {str(e)}'
            }
            logger.error(f"Ошибка при отправке запроса в Bitrix24: {e}")
            return error_result
            
        except json.JSONDecodeError as e:
            error_result = {
                'error': 'JSON_DECODE_ERROR', 
                'error_description': f'Ошибка декодирования JSON: {str(e)}'
            }
            logger.error(f"Ошибка декодирования ответа от Bitrix24: {e}")
            return error_result
        
        except Exception as e:
            error_result = {
                'error': 'UNEXPECTED_ERROR',
                'error_description': f'Неожиданная ошибка: {str(e)}'
            }
            logger.error(f"Неожиданная ошибка при создании задачи в Bitrix24: {e}")
            return error_result
    
    def _extract_title(self, variables: Dict[str, Any], metadata: Dict[str, Any], topic: str) -> str:
        """Извлечение заголовка задачи из данных сообщения"""
        # Попытка найти заголовок в переменных
        title_fields = ['title', 'name', 'subject', 'task_title', 'task_name']
        
        for field in title_fields:
            if field in variables:
                value = variables[field]
                if isinstance(value, dict) and 'value' in value:
                    return str(value['value'])
                elif isinstance(value, str):
                    return value
        
        # Попытка найти заголовок в метаданных
        if metadata:
            input_params = metadata.get('inputParameters', {})
            for field in title_fields:
                if field in input_params:
                    return str(input_params[field])
        
        # Fallback - создание заголовка на основе топика
        topic_titles = {
            'bitrix_create_task': 'Новая задача из процесса Camunda',
            'bitrix_update_task': 'Обновление задачи из процесса Camunda',
            'bitrix_create_deal': 'Новая сделка из процесса Camunda',
            'bitrix_update_deal': 'Обновление сделки из процесса Camunda',
            'bitrix_create_contact': 'Новый контакт из процесса Camunda',
        }
        
        return topic_titles.get(topic, f'Задача из Camunda процесса ({topic})')
    
    def _create_description(self, message_data: Dict[str, Any]) -> str:
        """Создание описания задачи (для отладки - все данные сообщения)"""
        try:
            # Форматированное представление всех данных сообщения
            description_parts = [
                "Задача создана автоматически из процесса Camunda BPM",
                "",
                "=== ДАННЫЕ СООБЩЕНИЯ ===",
                json.dumps(message_data, ensure_ascii=False, indent=2)
            ]
            
            description = '\n'.join(description_parts)
            
            # Ограничение длины описания
            if len(description) > self.config.max_description_length:
                description = description[:self.config.max_description_length - 100] + '\n\n[Описание обрезано]'
            
            return description
            
        except Exception as e:
            logger.error(f"Ошибка создания описания: {e}")
            return f"Задача создана автоматически из процесса Camunda BPM\n\nОшибка формирования описания: {str(e)}"
    
    def _extract_responsible_id(self, variables: Dict[str, Any], metadata: Dict[str, Any]) -> int:
        """Извлечение ID ответственного"""
        # Попытка найти ID ответственного в переменных
        responsible_fields = ['responsible_id', 'assignee_id', 'user_id', 'owner_id']
        
        for field in responsible_fields:
            if field in variables:
                value = variables[field]
                if isinstance(value, dict) and 'value' in value:
                    try:
                        return int(value['value'])
                    except (ValueError, TypeError):
                        pass
                elif isinstance(value, (int, str)):
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        pass
        
        # Fallback - использование значения по умолчанию
        return self.config.default_responsible_id
    
    def _extract_priority(self, variables: Dict[str, Any], metadata: Dict[str, Any]) -> int:
        """Извлечение приоритета задачи"""
        # Попытка найти приоритет в переменных
        priority_fields = ['priority', 'task_priority', 'urgency']
        
        for field in priority_fields:
            if field in variables:
                value = variables[field]
                if isinstance(value, dict) and 'value' in value:
                    try:
                        priority = int(value['value'])
                        return max(1, min(3, priority))  # Ограничение 1-3
                    except (ValueError, TypeError):
                        pass
                elif isinstance(value, (int, str)):
                    try:
                        priority = int(value)
                        return max(1, min(3, priority))  # Ограничение 1-3
                    except (ValueError, TypeError):
                        pass
        
        # Fallback - использование значения по умолчанию
        return self.config.default_priority
    
    def _extract_deadline(self, variables: Dict[str, Any], metadata: Dict[str, Any]) -> Optional[str]:
        """Извлечение дедлайна задачи"""
        # Попытка найти дедлайн в переменных
        deadline_fields = ['deadline', 'due_date', 'end_date', 'finish_date']
        
        for field in deadline_fields:
            if field in variables:
                value = variables[field]
                if isinstance(value, dict) and 'value' in value:
                    deadline = value['value']
                elif isinstance(value, str):
                    deadline = value
                else:
                    continue
                
                # Проверка и форматирование даты
                if deadline and isinstance(deadline, str):
                    # TODO: Добавить валидацию и форматирование даты
                    return deadline
        
        return None
    
    def _extract_additional_fields(self, variables: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Извлечение дополнительных полей для задачи"""
        additional_fields = {}
        
        # Маппинг полей из переменных в поля Bitrix24
        field_mapping = {
            'group_id': 'GROUP_ID',
            'project_id': 'GROUP_ID',
            'tags': 'TAGS',
            'description_additional': 'DESCRIPTION',
        }
        
        for var_field, bitrix_field in field_mapping.items():
            if var_field in variables:
                value = variables[var_field]
                if isinstance(value, dict) and 'value' in value:
                    additional_fields[bitrix_field] = value['value']
                elif value is not None:
                    additional_fields[bitrix_field] = value
        
        return additional_fields
    
    def _send_success_message(self, original_message: Dict[str, Any], 
                             bitrix_response: Dict[str, Any], original_queue: str) -> bool:
        """
        Отправка сообщения об успешной обработке в очередь sent messages
        
        Args:
            original_message: Исходное сообщение из RabbitMQ
            bitrix_response: Ответ от Bitrix24 API
            original_queue: Имя исходной очереди
            
        Returns:
            True если сообщение успешно отправлено, False иначе
        """
        try:
            # Подключение к RabbitMQ если нет соединения
            if not self.publisher.is_connected():
                if not self.publisher.connect():
                    logger.error("Не удалось подключиться к RabbitMQ для отправки успешного сообщения")
                    return False
            
            # Отправка сообщения через publisher
            success = self.publisher.publish_success_message(
                original_queue=original_queue,
                original_message=original_message, 
                response_data=bitrix_response
            )
            
            if success:
                task_id = bitrix_response.get('result', {}).get('task', {}).get('id', 'unknown')
                logger.info(f"Результат создания задачи {task_id} отправлен в очередь успешных сообщений")
            else:
                logger.error("Не удалось отправить результат в очередь успешных сообщений")
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка при отправке успешного сообщения: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики работы обработчика"""
        uptime = time.time() - self.stats["start_time"]
        
        return {
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
                logger.info("Publisher отключен при очистке ресурсов BitrixTaskHandler")
        except Exception as e:
            logger.error(f"Ошибка при очистке ресурсов BitrixTaskHandler: {e}") 