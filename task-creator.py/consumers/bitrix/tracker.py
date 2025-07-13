#!/usr/bin/env python3
"""
Tracker для отслеживания задач в Bitrix24 и перемещения завершенных в camunda.responses.queue
"""
import json
import requests
import time
from typing import Dict, Any, Optional, List
from loguru import logger
from .config import bitrix_config
from rabbitmq_consumer import RabbitMQConsumer
from rabbitmq_publisher import RabbitMQPublisher


class BitrixTaskTracker:
    """Tracker для отслеживания статуса задач в Bitrix24"""
    
    def __init__(self):
        self.config = bitrix_config
        self.task_get_url = f"{self.config.webhook_url}/tasks.task.get.json"
        
        self.consumer = RabbitMQConsumer()
        self.publisher = RabbitMQPublisher()
        
        self.source_queue = "bitrix24.sent.queue"
        self.target_queue = "camunda.responses.queue"
        
        self.completed_statuses = ["4", "5"]

        self.stats = {
            "start_time": time.time(), "total_checked": 0, "completed_tasks": 0,
            "moved_to_responses": 0, "failed_moves": 0, "failed_checks": 0,
            "last_check_time": None, "errors": []
        }
        
        logger.info("BitrixTaskTracker инициализирован с упрощенной логикой резолвинга полей.")
    
    def _check_tasks_in_queue(self):
        try:
            self.stats["last_check_time"] = time.time()
            if not self.consumer.is_connected() and not self.consumer.connect():
                return
            
            messages = self._get_messages_from_queue(self.source_queue)
            if not messages: return
            
            logger.info(f"Проверка {len(messages)} сообщений в очереди {self.source_queue}")
            for message_info in messages:
                try:
                    self._process_message(message_info)
                except Exception as e:
                    logger.error(f"Критическая ошибка обработки сообщения {message_info.get('delivery_tag', 'unknown')}: {e}")
                    self.stats["failed_checks"] += 1
        except Exception as e:
            logger.error(f"Ошибка при проверке задач в очереди: {e}")
            self.stats["errors"].append(str(e))
    
    def _get_messages_from_queue(self, queue_name: str) -> List[Dict[str, Any]]:
        messages = []
        try:
            if not self.consumer.is_connected() and not self.consumer.connect():
                return messages
            
            method = self.consumer.channel.queue_declare(queue=queue_name, passive=True)
            if method.method.message_count == 0: return messages
            
            for _ in range(min(method.method.message_count, 50)):
                method_frame, _, body = self.consumer.channel.basic_get(queue=queue_name, auto_ack=False)
                if method_frame is None: break
                messages.append({"delivery_tag": method_frame.delivery_tag, "message_data": json.loads(body)})
            return messages
        except Exception as e:
            logger.error(f"Ошибка получения сообщений из очереди {queue_name}: {e}")
            return []
    
    def _process_message(self, message_info: Dict[str, Any]):
        delivery_tag = message_info["delivery_tag"]
        try:
            task_id = self._extract_task_id(message_info["message_data"])
            if not task_id:
                self.consumer.channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
                return

            task_info = self._get_task_info_from_bitrix(task_id)
            if not task_info:
                self.consumer.channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
                return
            
            if str(task_info.get('status')) in self.completed_statuses:
                logger.info(f"Задача {task_id} завершена (статус: {task_info['status']}), перемещаем.")
                updated_message = self._update_response_data(message_info["message_data"], task_info)
                if self._move_to_responses_queue(updated_message):
                    self.consumer.channel.basic_ack(delivery_tag=delivery_tag)
                    self.stats["completed_tasks"] += 1; self.stats["moved_to_responses"] += 1
                else:
                    self.consumer.channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
            else:
                self.consumer.channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения {delivery_tag}: {e}")
            if self.consumer.is_connected():
                self.consumer.channel.basic_nack(delivery_tag=delivery_tag, requeue=True)

    def _extract_task_id(self, message_data: Dict[str, Any]) -> Optional[str]:
        try:
            return str(message_data['response_data']['result']['task']['id'])
        except KeyError:
            logger.warning("ID задачи не найден в response_data")
            return None
    
    def _get_task_info_from_bitrix(self, task_id: str) -> Optional[Dict[str, Any]]:
        try:
            select_fields = ['*', 'UF_RESULT_EXPECTED', 'UF_RESULT_QUESTION', 'UF_RESULT_ANSWER']
            params = {'taskId': task_id, 'select[]': select_fields}
            response = requests.get(self.task_get_url, params=params, timeout=self.config.request_timeout)
            response.raise_for_status()
            task_info = response.json().get('result', {}).get('task', {})
            return task_info if task_info.get('id') else None
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса к Bitrix24 для задачи {task_id}: {e}")
            return None

    def _update_response_data(self, message_data: Dict[str, Any], task_info: Dict[str, Any]) -> Dict[str, Any]:
        """Обновление response_data с заменой ID из списка на значение из конфига."""
        # Упрощенная логика резолвинга
        answer_id = task_info.get('ufResultAnswer')
        if answer_id:
            # Используем маппинг из конфига. .get() вернет ID, если соответствие не найдено.
            task_info['ufResultAnswer_text'] = self.config.uf_result_answer_mapping.get(str(answer_id), str(answer_id))

        message_data['response_data'] = {'result': {'task': task_info}}
        message_data['processed_at'] = time.time()
        message_data['processing_status'] = 'completed_by_tracker'
        return message_data

    def _move_to_responses_queue(self, message_data: Dict[str, Any]) -> bool:
        try:
            if not self.publisher.is_connected() and not self.publisher.connect():
                return False
            return self.publisher.publish_message(self.target_queue, message_data, persistent=True)
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения в {self.target_queue}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        # (Без изменений)
        uptime = time.time() - self.stats["start_time"]
        return {
            "uptime_seconds": uptime, "total_checked": self.stats["total_checked"], 
            "completed_tasks": self.stats["completed_tasks"], "moved_to_responses": self.stats["moved_to_responses"],
            "failed_moves": self.stats["failed_moves"], "failed_checks": self.stats["failed_checks"],
            "completion_rate": (self.stats["completed_tasks"] / self.stats["total_checked"] * 100 if self.stats["total_checked"] > 0 else 0),
            "success_move_rate": (self.stats["moved_to_responses"] / self.stats["completed_tasks"] * 100 if self.stats["completed_tasks"] > 0 else 0),
            "last_check_time": self.stats["last_check_time"], "errors_count": len(self.stats["errors"]),
            "recent_errors": self.stats["errors"][-5:]
        }
    
    def cleanup(self):
        # (Без изменений)
        if hasattr(self, 'consumer') and self.consumer.is_connected(): self.consumer.disconnect()
        if hasattr(self, 'publisher') and self.publisher.is_connected(): self.publisher.disconnect()
        logger.info("Ресурсы BitrixTaskTracker очищены")