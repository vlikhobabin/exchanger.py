#!/usr/bin/env python3
"""
Tracker для отслеживания задач в Bitrix24 и перемещения завершенных в camunda.responses.queue
"""
import json
import requests
import time
from typing import Dict, Any, Optional, List
from loguru import logger
from .config import bitrix_config, worker_config
from rabbitmq_consumer import RabbitMQConsumer
from rabbitmq_publisher import RabbitMQPublisher


class BitrixTaskTracker:
    """Tracker для отслеживания статуса задач в Bitrix24"""
    
    def __init__(self):
        self.config = bitrix_config
        self.worker_config = worker_config
        self.task_get_url = f"{self.config.webhook_url}/tasks.task.get.json"
        
        # RabbitMQ компоненты
        self.consumer = RabbitMQConsumer()
        self.publisher = RabbitMQPublisher()
        
        # Очереди для работы
        self.source_queue = "bitrix24.sent.queue"
        self.target_queue = "camunda.responses.queue"
        
        # Статусы задач Bitrix24, которые считаются завершенными
        self.completed_statuses = ["4", "5"]  # 4 - Ожидает контроля, 5 - Завершена
        
        # Статистика
        self.stats = {
            "start_time": time.time(),
            "total_checked": 0,
            "completed_tasks": 0,
            "moved_to_responses": 0,
            "failed_moves": 0,
            "failed_checks": 0,
            "last_check_time": None,
            "errors": []
        }
        
        logger.info("BitrixTaskTracker инициализирован")
    
    def _check_tasks_in_queue(self):
        """Проверка задач в очереди bitrix24.sent.queue"""
        try:
            self.stats["last_check_time"] = time.time()
            
            # Подключаемся если нет соединения
            if not self.consumer.is_connected():
                if not self.consumer.connect():
                    logger.error("Не удалось подключиться к RabbitMQ")
                    return
            
            # Получение сообщений из очереди (без удаления)
            messages = self._get_messages_from_queue(self.source_queue)
            
            if not messages:
                logger.debug("Нет сообщений в очереди bitrix24.sent.queue")
                return
            
            logger.info(f"Проверка {len(messages)} сообщений в очереди {self.source_queue}")
            
            for message_info in messages:
                try:
                    self._process_message(message_info)
                except Exception as e:
                    logger.error(f"Ошибка обработки сообщения {message_info.get('delivery_tag', 'unknown')}: {e}")
                    self.stats["failed_checks"] += 1
                    
        except Exception as e:
            logger.error(f"Ошибка при проверке задач в очереди: {e}")
            self.stats["errors"].append(str(e))
    
    def _get_messages_from_queue(self, queue_name: str) -> List[Dict[str, Any]]:
        """Получение сообщений из очереди без удаления"""
        messages = []
        
        try:
            # Проверяем соединение и подключаемся если нужно
            if not self.consumer.is_connected():
                if not self.consumer.connect():
                    logger.error("Не удалось подключиться к RabbitMQ для чтения сообщений")
                    return messages
            
            # Проверяем существование очереди
            method = self.consumer.channel.queue_declare(queue=queue_name, passive=True)
            msg_count = method.method.message_count
            
            if msg_count == 0:
                return messages
            
            # Получаем сообщения без автоподтверждения
            for _ in range(min(msg_count, 50)):  # Ограничиваем количество за раз
                method_frame, header_frame, body = self.consumer.channel.basic_get(
                    queue=queue_name, 
                    auto_ack=False
                )
                
                if method_frame is None:
                    break
                
                try:
                    message_data = json.loads(body.decode('utf-8'))
                    messages.append({
                        "delivery_tag": method_frame.delivery_tag,
                        "message_data": message_data,
                        "properties": header_frame
                    })
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка декодирования сообщения: {e}")
                    # Возвращаем сообщение в очередь при ошибке
                    self.consumer.channel.basic_nack(
                        delivery_tag=method_frame.delivery_tag,
                        requeue=True
                    )
            
            return messages
            
        except Exception as e:
            logger.error(f"Ошибка получения сообщений из очереди {queue_name}: {e}")
            return []
    
    def _process_message(self, message_info: Dict[str, Any]):
        """Обработка отдельного сообщения"""
        delivery_tag = message_info["delivery_tag"]
        message_data = message_info["message_data"]
        
        try:
            # Проверяем соединение
            if not self.consumer.is_connected():
                if not self.consumer.connect():
                    logger.error("Не удалось подключиться к RabbitMQ для обработки сообщения")
                    return
            
            self.stats["total_checked"] += 1
            
            # Извлечение ID задачи из response_data
            task_id = self._extract_task_id(message_data)
            
            if not task_id:
                logger.warning(f"Не удалось извлечь ID задачи из сообщения {delivery_tag}")
                # Возвращаем сообщение в очередь
                self.consumer.channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
                return
            
            # Получение актуальной информации о задаче из Bitrix24
            task_info = self._get_task_info_from_bitrix(task_id)
            
            if not task_info:
                logger.warning(f"Не удалось получить информацию о задаче {task_id} из Bitrix24")
                # Возвращаем сообщение в очередь
                self.consumer.channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
                return
            
            # Проверка статуса задачи
            task_status = str(task_info.get('status', ''))  # Поле status в нижнем регистре
            
            if task_status in self.completed_statuses:
                logger.info(f"Задача {task_id} завершена (статус: {task_status}), перемещаем в responses.queue")
                
                # Обновление response_data с актуальными данными
                updated_message = self._update_response_data(message_data, task_info)
                
                # Отправка в camunda.responses.queue
                success = self._move_to_responses_queue(updated_message)
                
                if success:
                    # Удаление сообщения из исходной очереди
                    self.consumer.channel.basic_ack(delivery_tag=delivery_tag)
                    self.stats["completed_tasks"] += 1
                    self.stats["moved_to_responses"] += 1
                    logger.info(f"Задача {task_id} успешно перемещена в responses.queue")
                else:
                    # Возвращаем сообщение в очередь при неудаче
                    self.consumer.channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
                    self.stats["failed_moves"] += 1
                    logger.error(f"Не удалось переместить задачу {task_id} в responses.queue")
            else:
                # Задача не завершена, возвращаем в очередь
                self.consumer.channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
                logger.debug(f"Задача {task_id} не завершена (статус: {task_status})")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения {delivery_tag}: {e}")
            # Возвращаем сообщение в очередь при ошибке (если соединение есть)
            try:
                if self.consumer.is_connected():
                    self.consumer.channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
            except:
                pass
            self.stats["failed_checks"] += 1
    
    def _extract_task_id(self, message_data: Dict[str, Any]) -> Optional[str]:
        """Извлечение ID задачи из сообщения"""
        try:
            # ID задачи должен быть в response_data.result.task.id
            response_data = message_data.get('response_data', {})
            result = response_data.get('result', {})
            task = result.get('task', {})
            task_id = task.get('id')
            
            if task_id:
                return str(task_id)
            
            logger.warning("ID задачи не найден в response_data")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка извлечения ID задачи: {e}")
            return None
    
    def _get_task_info_from_bitrix(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Получение информации о задаче из Bitrix24"""
        try:
            # Подготовка параметров (правильный регистр согласно документации)
            params = {
                'taskId': task_id  # Правильный регистр параметра
            }
            
            # Выполнение GET запроса (как указано в документации)
            response = requests.get(
                self.task_get_url,
                params=params,
                timeout=self.config.request_timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get('error'):
                logger.error(f"Ошибка API Bitrix24 при получении задачи {task_id}: {result['error']}")
                logger.error(f"Описание ошибки: {result.get('error_description', 'Не указано')}")
                return None
            
            # В Bitrix24 API результат находится в result.task
            task_info = result.get('result', {}).get('task', {})
            
            if not task_info:
                logger.warning(f"Задача {task_id} не найдена в Bitrix24 (пустой result.task)")
                return None
            
            # Проверяем, что это действительно задача (есть ID)
            if not task_info.get('id'):  # Поле называется "id" в нижнем регистре
                logger.warning(f"Получен неполный ответ для задачи {task_id} - отсутствует поле id")
                return None
            
            logger.debug(f"Получена информация о задаче {task_id}: статус={task_info.get('status', 'unknown')}")
            return task_info
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса к Bitrix24 для задачи {task_id}: {e}")
            logger.debug(f"Возможные причины: недостаточно прав webhook'а, неправильный URL, проблемы с сетью")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении информации о задаче {task_id}: {e}")
            return None
    
    def _update_response_data(self, message_data: Dict[str, Any], task_info: Dict[str, Any]) -> Dict[str, Any]:
        """Обновление response_data с актуальными данными задачи"""
        try:
            # Создаем копию исходного сообщения
            updated_message = message_data.copy()
            
            # Обновляем response_data
            updated_message['response_data'] = {
                'result': {
                    'task': task_info
                },
                'time': {
                    'start': time.time(),
                    'finish': time.time(),
                    'duration': 0,
                    'processing': 0,
                    'date_start': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                    'date_finish': time.strftime('%Y-%m-%dT%H:%M:%S%z')
                }
            }
            
            # Обновляем временные метки
            updated_message['processed_at'] = time.time()
            updated_message['processing_status'] = 'completed'
            
            return updated_message
            
        except Exception as e:
            logger.error(f"Ошибка обновления response_data: {e}")
            return message_data
    
    def _move_to_responses_queue(self, message_data: Dict[str, Any]) -> bool:
        """Перемещение сообщения в очередь camunda.responses.queue"""
        try:
            # Проверяем соединение publisher'а
            if not self.publisher.is_connected():
                if not self.publisher.connect():
                    logger.error("Не удалось подключиться к RabbitMQ для отправки сообщения")
                    return False
            
            return self.publisher.publish_message(
                queue_name=self.target_queue,
                message_data=message_data,
                persistent=True
            )
            
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в {self.target_queue}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики работы tracker'а"""
        uptime = time.time() - self.stats["start_time"]
        
        return {
            "uptime_seconds": uptime,
            "total_checked": self.stats["total_checked"],
            "completed_tasks": self.stats["completed_tasks"],
            "moved_to_responses": self.stats["moved_to_responses"],
            "failed_moves": self.stats["failed_moves"],
            "failed_checks": self.stats["failed_checks"],
            "completion_rate": (
                self.stats["completed_tasks"] / self.stats["total_checked"] * 100
                if self.stats["total_checked"] > 0 else 0
            ),
            "success_move_rate": (
                self.stats["moved_to_responses"] / self.stats["completed_tasks"] * 100
                if self.stats["completed_tasks"] > 0 else 0
            ),
            "last_check_time": self.stats["last_check_time"],
            "errors_count": len(self.stats["errors"]),
            "recent_errors": self.stats["errors"][-5:] if self.stats["errors"] else []
        }
    
    def cleanup(self):
        """Очистка ресурсов"""
        try:
            if hasattr(self, 'consumer') and self.consumer:
                self.consumer.disconnect()
            if hasattr(self, 'publisher') and self.publisher:
                self.publisher.disconnect()
            logger.info("Ресурсы BitrixTaskTracker очищены")
        except Exception as e:
            logger.error(f"Ошибка при очистке ресурсов BitrixTaskTracker: {e}") 