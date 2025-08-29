"""
Response Handler для обработки ответов из RabbitMQ и завершения задач в Camunda
"""
import json
import time
import signal
import sys
from typing import Dict, Any, Optional
from threading import Thread, Event
import pika
import requests
from loguru import logger

from config import camunda_config, rabbitmq_config, worker_config, response_config
from rabbitmq_client import RabbitMQClient


class TaskResponseHandler:
    """Обработчик ответов на задачи из RabbitMQ"""
    
    def __init__(self):
        self.camunda_config = camunda_config
        self.rabbitmq_config = rabbitmq_config
        self.worker_config = worker_config
        self.response_config = response_config
        
        # Компоненты
        self.rabbitmq_client = RabbitMQClient()
        
        # Базовый URL для API
        base_url = self.camunda_config.base_url.rstrip('/')
        if base_url.endswith('/engine-rest'):
            self.api_base_url = base_url
        else:
            self.api_base_url = f"{base_url}/engine-rest"
        
        # Управление работой
        self.shutdown_event = Event()
        self.is_running = False
        
        # Статистика
        self.stats = {
            "processed_responses": 0,
            "successful_completions": 0,
            "failed_completions": 0,
            "bpmn_errors": 0,
            "start_time": None
        }
        
        # Настройка обработки сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов завершения"""
        logger.info(f"Response Handler получен сигнал {signum}, завершение работы...")
        self.shutdown()
    
    def initialize(self) -> bool:
        """Инициализация компонентов"""
        try:
            logger.info("Инициализация Task Response Handler...")
            
            # Подключение к RabbitMQ
            if not self.rabbitmq_client.connect():
                logger.error("Не удалось подключиться к RabbitMQ")
                return False
            
            # Создание инфраструктуры (если не создана)
            if not self.rabbitmq_client.setup_infrastructure():
                logger.error("Не удалось создать инфраструктуру RabbitMQ")
                return False
            
            logger.info("Инициализация Response Handler завершена успешно")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации Response Handler: {e}")
            return False
    
    def _validate_response_message(self, message_data: Dict[str, Any]) -> bool:
        """Валидация ответного сообщения"""
        try:
            # Проверка обязательных полей
            for field in self.response_config.REQUIRED_FIELDS:
                if field not in message_data:
                    logger.error(f"Отсутствует обязательное поле: {field}")
                    return False
            
            # Проверка типа ответа
            response_type = message_data.get("response_type")
            if response_type not in self.response_config.RESPONSE_TYPES.values():
                logger.error(f"Неизвестный тип ответа: {response_type}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка валидации сообщения: {e}")
            return False
    
    def _complete_task(self, task_id: str, variables: Optional[Dict[str, Any]] = None, 
                      local_variables: Optional[Dict[str, Any]] = None) -> bool:
        """Завершение задачи в Camunda"""
        try:
            url = f"{self.api_base_url}/external-task/{task_id}/complete"
            
            payload = {
                "workerId": self.camunda_config.worker_id
            }
            
            if variables:
                payload["variables"] = self._format_variables(variables)
            
            if local_variables:
                payload["localVariables"] = self._format_variables(local_variables)
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 204:
                logger.info(f"Задача {task_id} успешно завершена")
                return True
            else:
                logger.error(f"Ошибка завершения задачи {task_id}: HTTP {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка завершения задачи {task_id}: {e}")
            return False
    
    def _fail_task(self, task_id: str, error_message: str, error_details: Optional[str] = None,
                  retries: Optional[int] = None, retry_timeout: Optional[int] = None) -> bool:
        """Пометка задачи как неуспешной в Camunda"""
        try:
            url = f"{self.api_base_url}/external-task/{task_id}/failure"
            
            payload = {
                "workerId": self.camunda_config.worker_id,
                "errorMessage": error_message
            }
            
            if error_details:
                payload["errorDetails"] = error_details
            
            if retries is not None:
                payload["retries"] = retries
            
            if retry_timeout is not None:
                payload["retryTimeout"] = retry_timeout
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 204:
                logger.info(f"Задача {task_id} помечена как неуспешная")
                return True
            else:
                logger.error(f"Ошибка пометки задачи {task_id} как неуспешной: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка пометки задачи {task_id} как неуспешной: {e}")
            return False
    
    def _bpmn_error_task(self, task_id: str, error_code: str, error_message: str,
                        variables: Optional[Dict[str, Any]] = None) -> bool:
        """Создание BPMN ошибки для задачи"""
        try:
            url = f"{self.api_base_url}/external-task/{task_id}/bpmnError"
            
            payload = {
                "workerId": self.camunda_config.worker_id,
                "errorCode": error_code,
                "errorMessage": error_message
            }
            
            if variables:
                payload["variables"] = self._format_variables(variables)
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 204:
                logger.info(f"BPMN ошибка создана для задачи {task_id}: {error_code}")
                return True
            else:
                logger.error(f"Ошибка создания BPMN ошибки для {task_id}: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка создания BPMN ошибки для {task_id}: {e}")
            return False
    

    
    def _format_variables(self, variables: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Форматирование переменных для Camunda API"""
        formatted = {}
        for key, value in variables.items():
            if isinstance(value, str):
                formatted[key] = {"value": value, "type": "String"}
            elif isinstance(value, bool):
                formatted[key] = {"value": value, "type": "Boolean"}
            elif isinstance(value, int):
                formatted[key] = {"value": value, "type": "Integer"}
            elif isinstance(value, float):
                formatted[key] = {"value": value, "type": "Double"}
            else:
                # Для сложных типов используем JSON
                formatted[key] = {"value": json.dumps(value), "type": "Json"}
        return formatted
    
    def _process_response_message(self, ch, method, properties, body):
        """Обработка ответного сообщения из RabbitMQ"""
        try:
            # Парсинг сообщения
            message_data = json.loads(body.decode('utf-8'))
            self.stats["processed_responses"] += 1
            
            logger.info(f"Получен ответ на задачу: {message_data.get('task_id')}")
            
            # Валидация сообщения
            if not self._validate_response_message(message_data):
                logger.error("Сообщение не прошло валидацию")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                return
            
            task_id = message_data["task_id"]
            response_type = message_data["response_type"]
            worker_id = message_data["worker_id"]
            
            # Проверка worker_id (опционально)
            if worker_id != self.camunda_config.worker_id:
                logger.warning(f"Worker ID не совпадает: {worker_id} != {self.camunda_config.worker_id}")
            
            # Обработка разных типов ответов
            success = False
            
            if response_type == self.response_config.RESPONSE_TYPES["COMPLETE"]:
                success = self._complete_task(
                    task_id,
                    message_data.get("variables"),
                    message_data.get("local_variables")
                )
                if success:
                    self.stats["successful_completions"] += 1
                    
            elif response_type == self.response_config.RESPONSE_TYPES["FAILURE"]:
                success = self._fail_task(
                    task_id,
                    message_data.get("error_message", "Task failed"),
                    message_data.get("error_details"),
                    message_data.get("retries"),
                    message_data.get("retry_timeout")
                )
                
            elif response_type == self.response_config.RESPONSE_TYPES["BPMN_ERROR"]:
                success = self._bpmn_error_task(
                    task_id,
                    message_data.get("error_code", "BUSINESS_ERROR"),
                    message_data.get("error_message", "Business error occurred"),
                    message_data.get("variables")
                )
                if success:
                    self.stats["bpmn_errors"] += 1
                
            else:
                logger.error(f"Неподдерживаемый тип ответа: {response_type}")
                success = False
            
            # Подтверждение или отклонение сообщения
            if success:
                ch.basic_ack(delivery_tag=method.delivery_tag)
                logger.info(f"Ответ на задачу {task_id} успешно обработан")
            else:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                self.stats["failed_completions"] += 1
                logger.error(f"Ошибка обработки ответа на задачу {task_id}")
                
        except Exception as e:
            logger.error(f"Ошибка обработки ответного сообщения: {e}")
            try:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            except:
                pass
    
    def start(self) -> bool:
        """Запуск обработчика ответов"""
        try:
            if not self.initialize():
                logger.error("Инициализация не удалась")
                return False
            
            logger.info("Запуск Task Response Handler...")
            self.stats["start_time"] = time.time()
            self.is_running = True
            
            # Настройка потребления ответов
            if not self.rabbitmq_client.consume_responses(self._process_response_message):
                logger.error("Не удалось настроить потребление ответов")
                return False
            
            # Запуск потребления (блокирующий вызов)
            logger.info("Response Handler запущен и ожидает ответы...")
            self.rabbitmq_client.start_consuming()
            
        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания")
            self.shutdown()
        except Exception as e:
            logger.error(f"Ошибка запуска Response Handler: {e}")
            self.shutdown()
            return False
        
        return True
    
    def shutdown(self):
        """Корректное завершение работы"""
        logger.info("Завершение работы Task Response Handler...")
        self.is_running = False
        
        # Остановка потребления
        self.rabbitmq_client.stop_consuming()
        
        # Закрытие RabbitMQ соединения
        self.rabbitmq_client.disconnect()
        
        # Финальная статистика
        if self.stats["start_time"]:
            uptime = time.time() - self.stats["start_time"]
            logger.info(
                f"Response Handler статистика - Uptime: {uptime:.0f}s | "
                f"Обработано ответов: {self.stats['processed_responses']} | "
                f"Успешные завершения: {self.stats['successful_completions']} | "
                f"Неуспешные: {self.stats['failed_completions']} | "
                f"BPMN ошибки: {self.stats['bpmn_errors']}"
            )
        
        logger.info("Response Handler завершен")
    
    def get_status(self) -> Dict[str, Any]:
        """Получение текущего статуса обработчика"""
        uptime = time.time() - self.stats["start_time"] if self.stats["start_time"] else 0
        
        return {
            "is_running": self.is_running,
            "uptime_seconds": uptime,
            "stats": self.stats.copy(),
            "rabbitmq_connected": self.rabbitmq_client.is_connected(),
            "response_queue_info": self.rabbitmq_client.get_queue_info(
                self.rabbitmq_config.responses_queue_name
            )
        } 