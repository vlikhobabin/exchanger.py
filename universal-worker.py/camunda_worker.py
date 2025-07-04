#!/usr/bin/env python3
"""
Universal Camunda Worker на базе ExternalTaskClient
Stateless архитектура для обработки External Tasks
"""
import json
import time
import signal
import sys
import threading
import traceback
import requests
from typing import Dict, Any, Optional
from loguru import logger

from camunda.client.external_task_client import ExternalTaskClient
from camunda.external_task.external_task import ExternalTask
from config import camunda_config, worker_config, routing_config, rabbitmq_config
from rabbitmq_client import RabbitMQClient
from bpmn_metadata_cache import BPMNMetadataCache


class UniversalCamundaWorker:
    """Universal Worker на базе ExternalTaskClient с Stateless архитектурой"""
    
    def __init__(self):
        self.config = camunda_config
        self.worker_config = worker_config
        self.routing_config = routing_config
        self.rabbitmq_config = rabbitmq_config
        
        # Компоненты
        self.client: Optional[ExternalTaskClient] = None
        self.rabbitmq_client = RabbitMQClient()
        self.metadata_cache: Optional[BPMNMetadataCache] = None
        
        # Управление работой
        self.running = False
        self.stop_event = threading.Event()
        self.worker_threads = []
        
        # Статистика
        self.stats = {
            "processed_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "start_time": None,
            "last_fetch": None,
            # Добавляем статистику для обработки ответов
            "processed_responses": 0,
            "successful_completions": 0,
            "failed_completions": 0
        }
        
        # Настройка обработки сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов завершения"""
        logger.info(f"Получен сигнал {signum}, завершение работы...")
        self.shutdown()
        sys.exit(0)
    
    def initialize(self) -> bool:
        """Инициализация компонентов"""
        try:
            logger.info("Инициализация Universal Camunda Worker...")
            
            # Подключение к RabbitMQ
            if not self.rabbitmq_client.connect():
                logger.error("Не удалось подключиться к RabbitMQ")
                return False
            
            if not self.rabbitmq_client.setup_infrastructure():
                logger.error("Не удалось создать инфраструктуру RabbitMQ")
                return False
            
            # Конфигурация ExternalTaskClient
            client_config = {
                "maxTasks": self.config.max_tasks,
                "lockDuration": self.config.lock_duration,
                "asyncResponseTimeout": self.config.async_response_timeout,
                "httpTimeoutMillis": self.config.http_timeout_millis,
                "timeoutDeltaMillis": self.config.timeout_delta_millis,
                "includeExtensionProperties": self.config.include_extension_properties,
                "deserializeValues": self.config.deserialize_values,
                "usePriority": True,
                "sorting": self.config.sorting,
                "isDebug": self.config.is_debug
            }
            
            if self.config.auth_enabled:
                client_config["auth_basic"] = {
                    "username": self.config.auth_username,
                    "password": self.config.auth_password
                }
            
            # Создание ExternalTaskClient
            self.client = ExternalTaskClient(
                worker_id=self.config.worker_id,
                engine_base_url=self.config.base_url,
                config=client_config
            )
            
            # Инициализация кэша метаданных BPMN
            self.metadata_cache = BPMNMetadataCache(
                base_url=self.config.base_url,
                auth_username=self.config.auth_username if self.config.auth_enabled else None,
                auth_password=self.config.auth_password if self.config.auth_enabled else None,
                max_cache_size=150,  # Для ~100 процессов с запасом
                ttl_hours=24         # Кэш живет 24 часа
            )
            
            logger.info("Инициализация завершена успешно")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации: {e}")
            return False
    
    def _fetch_and_process_loop(self, topic: str):
        """Основной цикл получения и обработки задач для топика"""
        logger.info(f"Запущен поток для топика: {topic}")
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while not self.stop_event.is_set():
            try:
                # Получение задач
                tasks = self.client.fetch_and_lock(topic)
                self.stats["last_fetch"] = time.time()
                
                if tasks:
                    consecutive_errors = 0  # Сброс счетчика ошибок при успешном получении
                    logger.info(f"Получено {len(tasks)} задач для топика {topic}")
                    
                    for task_data in tasks:
                        if self.stop_event.is_set():
                            break
                        self._process_task(task_data, topic)
                    
                    # Короткая пауза между обработками
                    self.stop_event.wait(1)
                else:
                    # Нет задач - ждем дольше
                    self.stop_event.wait(self.config.sleep_seconds)
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Ошибка в цикле обработки топика {topic}: {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"Слишком много ошибок подряд ({consecutive_errors}) для топика {topic}, останавливаю поток")
                    break
                
                # Увеличиваем паузу при ошибках
                error_sleep = min(30, 5 * consecutive_errors)
                logger.warning(f"Пауза {error_sleep}s после ошибки для топика {topic}")
                self.stop_event.wait(error_sleep)
        
        logger.info(f"Поток для топика {topic} завершен")
    
    def _process_task(self, task_data: Dict[str, Any], topic: str):
        """Обработка одной задачи с получением метаданных BPMN"""
        task_id = task_data.get('id', 'unknown')
        
        try:
            logger.info(f"Обработка задачи {task_id} | Топик: {topic}")
            self.stats["processed_tasks"] += 1
            
            # Создание объекта ExternalTask
            task = ExternalTask(task_data)
            
            # Получение метаданных активности из BPMN XML
            process_definition_id = task_data.get('processDefinitionId')
            activity_id = task.get_activity_id()
            
            metadata = {}
            if self.metadata_cache and process_definition_id and activity_id:
                try:
                    metadata = self.metadata_cache.get_activity_metadata(process_definition_id, activity_id)
                    if metadata:
                        logger.debug(f"Получены метаданные для задачи {task_id}: {list(metadata.keys())}")
                except Exception as e:
                    logger.warning(f"Ошибка получения метаданных для задачи {task_id}: {e}")
            
            # Подготовка расширенных данных для RabbitMQ
            task_payload = {
                "id": task_id,
                "topic": topic,
                "variables": task.get_variables(),
                "processInstanceId": task.get_process_instance_id(),
                "processDefinitionId": process_definition_id,
                "activityId": activity_id,
                "activityInstanceId": task_data.get("activityInstanceId"),
                "workerId": task.get_worker_id(),
                "retries": task_data.get("retries"),
                "createTime": task_data.get("createTime"),
                "priority": task_data.get("priority", 0),
                "tenantId": task.get_tenant_id(),
                "businessKey": task.get_business_key(),
                # Добавляем метаданные BPMN
                "metadata": metadata
            }
            
            # Определение целевой системы
            system = self.routing_config.get_system_for_topic(topic)
            logger.info(f"Задача {task_id} направляется в систему: {system}")
            
            # Отправка в RabbitMQ
            if self.rabbitmq_client.publish_task(topic, task_payload):
                self.stats["successful_tasks"] += 1
                logger.info(f"Задача {task_id} успешно отправлена в RabbitMQ")
                
                # В Stateless режиме задача остается заблокированной
                logger.info(f"Задача {task_id} остается заблокированной, ожидает ответа из {system}")
            else:
                raise Exception("Не удалось опубликовать задачу в RabbitMQ")
                
        except Exception as e:
            self._handle_task_error(task_id, topic, str(e))
    
    def _handle_task_error(self, task_id: str, topic: str, error: str):
        """Обработка ошибки задачи"""
        try:
            logger.error(f"Ошибка обработки задачи {task_id}: {error}")
            self.stats["failed_tasks"] += 1
            
            # Отправка ошибки в RabbitMQ
            self.rabbitmq_client.publish_error(topic, task_id, error)
            
            # Возврат задачи в Camunda с ошибкой
            retries = max(0, self.worker_config.retry_attempts - 1)
            
            success = self.client.failure(
                task_id=task_id,
                error_message=f"Task processing error: {error}",
                error_details=error,
                retries=retries,
                retry_timeout=self.worker_config.retry_delay * 1000
            )
            
            if success:
                logger.warning(f"Задача {task_id} возвращена с ошибкой (retries: {retries})")
            else:
                logger.error(f"Не удалось вернуть задачу {task_id} с ошибкой")
                
        except Exception as handle_error:
            logger.error(f"Ошибка обработки ошибки задачи {task_id}: {handle_error}")
    
    def _check_response_queue(self):
        """Проверка и обработка сообщений из очереди ответов"""
        try:
            if not self.rabbitmq_client.is_connected():
                logger.warning("RabbitMQ соединение потеряно при проверке очереди ответов")
                return
            
            # Проверяем количество сообщений в очереди ответов
            queue_info = self.rabbitmq_client.get_queue_info(self.rabbitmq_config.responses_queue_name)
            if not queue_info:
                return
            
            message_count = queue_info.get("message_count", 0)
            if message_count == 0:
                return
            
            logger.info(f"Найдено {message_count} сообщений в очереди ответов, обрабатываем...")
            
            # Обрабатываем сообщения (по одному за раз)
            processed_count = 0
            max_messages_per_check = min(10, message_count)  # Не более 10 за раз
            
            for _ in range(max_messages_per_check):
                if self._process_single_response_message():
                    processed_count += 1
                else:
                    break  # Нет больше сообщений или ошибка
            
            if processed_count > 0:
                logger.info(f"Обработано {processed_count} ответов из очереди")
                
        except Exception as e:
            logger.error(f"Ошибка при проверке очереди ответов: {e}")
    
    def _process_single_response_message(self) -> bool:
        """Обработка одного сообщения из очереди ответов"""
        try:
            # Получаем сообщение без автоподтверждения
            method_frame, header_frame, body = self.rabbitmq_client.channel.basic_get(
                queue=self.rabbitmq_config.responses_queue_name,
                auto_ack=False
            )
            
            if method_frame is None:
                return False  # Нет сообщений
            
            # Парсим сообщение
            try:
                message_data = json.loads(body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.error(f"Ошибка парсинга сообщения из очереди ответов: {e}")
                self.rabbitmq_client.channel.basic_nack(
                    delivery_tag=method_frame.delivery_tag, 
                    requeue=False
                )
                return True
            
            self.stats["processed_responses"] += 1
            
            # Обрабатываем ответное сообщение
            success = self._process_response_message(message_data)
            
            # Подтверждаем или отклоняем сообщение
            if success:
                self.rabbitmq_client.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                logger.debug("Сообщение из очереди ответов успешно обработано и удалено")
            else:
                self.rabbitmq_client.channel.basic_nack(
                    delivery_tag=method_frame.delivery_tag, 
                    requeue=True
                )
                logger.error("Ошибка обработки сообщения, возвращаем в очередь")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения из очереди ответов: {e}")
            return False
    
    def _process_response_message(self, message_data: Dict[str, Any]) -> bool:
        """Обработка ответного сообщения и завершение задачи в Camunda"""
        try:
            # Извлекаем данные из сообщения
            original_message = message_data.get("original_message", {})
            response_data = message_data.get("response_data", {})
            processing_status = message_data.get("processing_status")
            
            task_id = original_message.get("task_id")
            if not task_id:
                logger.error("Отсутствует task_id в ответном сообщении")
                return False
            
            logger.info(f"Обрабатываем ответ для задачи {task_id} (статус: {processing_status})")
            
            # Проверяем статус обработки
            if processing_status != "completed":
                logger.warning(f"Задача {task_id} имеет статус '{processing_status}', пропускаем")
                return True  # Считаем успешным, удаляем сообщение
            
            # Извлекаем данные результата для передачи в Camunda
            task_result = response_data.get("result", {}).get("task", {})
            if not task_result:
                logger.warning(f"Отсутствуют данные результата для задачи {task_id}")
                # Завершаем задачу без переменных
                return self._complete_task_in_camunda(task_id, {})
            
            # Подготавливаем переменные для Camunda
            variables = {
                "task_result": task_result,
                "processing_status": processing_status,
                "processed_at": message_data.get("processed_at"),
                "original_topic": original_message.get("topic"),
                "external_system": original_message.get("system")
            }
            
            # Завершаем задачу в Camunda
            return self._complete_task_in_camunda(task_id, variables)
            
        except Exception as e:
            logger.error(f"Ошибка обработки ответного сообщения: {e}")
            return False
    
    def _complete_task_in_camunda(self, task_id: str, variables: Dict[str, Any]) -> bool:
        """Завершение задачи в Camunda через REST API"""
        try:
            # Формируем URL для завершения задачи
            base_url = self.config.base_url.rstrip('/')
            if base_url.endswith('/engine-rest'):
                api_base_url = base_url
            else:
                api_base_url = f"{base_url}/engine-rest"
            
            url = f"{api_base_url}/external-task/{task_id}/complete"
            
            # Подготавливаем payload
            payload = {
                "workerId": self.config.worker_id,
                "variables": self._format_variables(variables)
            }
            
            # Настраиваем аутентификацию
            auth = None
            if self.config.auth_enabled:
                auth = (self.config.auth_username, self.config.auth_password)
            
            # Отправляем запрос
            response = requests.post(url, json=payload, auth=auth, timeout=30)
            
            if response.status_code == 204:
                logger.info(f"Задача {task_id} успешно завершена в Camunda")
                self.stats["successful_completions"] += 1
                return True
            else:
                logger.error(f"Ошибка завершения задачи {task_id} в Camunda: HTTP {response.status_code} - {response.text}")
                self.stats["failed_completions"] += 1
                return False
                
        except Exception as e:
            logger.error(f"Ошибка завершения задачи {task_id} в Camunda: {e}")
            self.stats["failed_completions"] += 1
            return False
    
    def _format_variables(self, variables: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Форматирование переменных для Camunda API"""
        formatted = {}
        for key, value in variables.items():
            if value is None:
                formatted[key] = {"value": None, "type": "Null"}
            elif isinstance(value, str):
                formatted[key] = {"value": value, "type": "String"}
            elif isinstance(value, bool):
                formatted[key] = {"value": value, "type": "Boolean"}
            elif isinstance(value, int):
                formatted[key] = {"value": value, "type": "Long"}
            elif isinstance(value, float):
                formatted[key] = {"value": value, "type": "Double"}
            else:
                # Для сложных типов используем JSON
                formatted[key] = {"value": json.dumps(value, ensure_ascii=False), "type": "Json"}
        return formatted
    
    def start(self):
        """Запуск Worker"""
        try:
            if not self.initialize():
                logger.error("Инициализация не удалась")
                return False
            
            logger.info("Запуск Universal Camunda Worker...")
            self.stats["start_time"] = time.time()
            self.running = True
            
            # Получение списка топиков
            topics = list(self.routing_config.TOPIC_TO_SYSTEM_MAPPING.keys())
            logger.info(f"Запуск обработки {len(topics)} топиков: {topics}")
            
            # Создание потоков для каждого топика
            for topic in topics:
                thread = threading.Thread(
                    target=self._fetch_and_process_loop,
                    args=(topic,),
                    daemon=True,
                    name=f"Worker-{topic}"
                )
                thread.start()
                self.worker_threads.append(thread)
                logger.info(f"Запущен поток для топика: {topic}")
            
            # Поток мониторинга
            monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
                name="Monitor"
            )
            monitor_thread.start()
            self.worker_threads.append(monitor_thread)
            
            logger.info("Worker запущен и ожидает задачи...")
            
            # Ожидание завершения
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Получен сигнал прерывания")
                self.shutdown()
                
        except Exception as e:
            logger.error(f"Ошибка запуска Worker: {e}")
            traceback.print_exc()
            self.shutdown()
            return False
        
        return True
    
    def _monitor_loop(self):
        """Поток мониторинга статистики и обработки ответов"""
        last_response_check = 0
        
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                
                if self.running and self.stats["start_time"]:
                    uptime = current_time - self.stats["start_time"]
                    logger.info(
                        f"Monitor - Uptime: {uptime:.0f}s | "
                        f"Обработано: {self.stats['processed_tasks']} | "
                        f"Успешно: {self.stats['successful_tasks']} | "
                        f"Ошибки: {self.stats['failed_tasks']} | "
                        f"Ответов: {self.stats['processed_responses']} | "
                        f"Завершено: {self.stats['successful_completions']}"
                    )
                    
                    # Проверка соединения с RabbitMQ
                    if not self.rabbitmq_client.is_connected():
                        logger.warning("RabbitMQ соединение потеряно, попытка переподключения...")
                        self.rabbitmq_client.reconnect()
                    
                    # Проверка очереди ответов с интервалом heartbeat_interval
                    if current_time - last_response_check >= self.worker_config.heartbeat_interval:
                        logger.debug("Проверка очереди ответов...")
                        self._check_response_queue()
                        last_response_check = current_time
                
                # Мониторинг каждые 30 секунд
                self.stop_event.wait(30)
                
            except Exception as e:
                logger.error(f"Ошибка в мониторинге: {e}")
                self.stop_event.wait(10)
    
    def shutdown(self):
        """Корректное завершение работы"""
        logger.info("Завершение работы Universal Camunda Worker...")
        self.running = False
        self.stop_event.set()
        
        # Ожидание завершения потоков
        for thread in self.worker_threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        # Закрытие RabbitMQ соединения
        self.rabbitmq_client.disconnect()
        
        # Финальная статистика
        if self.stats["start_time"]:
            uptime = time.time() - self.stats["start_time"]
            logger.info(
                f"Финальная статистика - Uptime: {uptime:.0f}s | "
                f"Обработано: {self.stats['processed_tasks']} | "
                f"Успешно: {self.stats['successful_tasks']} | "
                f"Ошибки: {self.stats['failed_tasks']}"
            )
        
        logger.info("Universal Worker завершен")
    
    def get_status(self) -> Dict[str, Any]:
        """Получение текущего статуса Worker с информацией о кэше метаданных и обработке ответов"""
        uptime = time.time() - self.stats["start_time"] if self.stats["start_time"] else 0
        
        status = {
            "is_running": self.running,
            "uptime_seconds": uptime,
            "stats": self.stats.copy(),
            "architecture": "stateless",
            "active_threads": len([t for t in self.worker_threads if t.is_alive()]),
            "topics": list(self.routing_config.TOPIC_TO_SYSTEM_MAPPING.keys()),
            "lock_duration_minutes": self.config.lock_duration / (1000 * 60),
            "heartbeat_interval_seconds": self.worker_config.heartbeat_interval,
            "camunda_config": {
                "base_url": self.config.base_url,
                "worker_id": self.config.worker_id,
                "max_tasks": self.config.max_tasks,
                "lock_duration": self.config.lock_duration
            },
            "rabbitmq_connected": self.rabbitmq_client.is_connected(),
            "queues_info": self.rabbitmq_client.get_all_queues_info(),
            "response_processing": {
                "enabled": True,
                "queue_name": self.rabbitmq_config.responses_queue_name,
                "check_interval_seconds": self.worker_config.heartbeat_interval,
                "processed_responses": self.stats["processed_responses"],
                "successful_completions": self.stats["successful_completions"],
                "failed_completions": self.stats["failed_completions"]
            }
        }
        
        # Добавление статистики кэша метаданных BPMN
        if self.metadata_cache:
            status["metadata_cache"] = self.metadata_cache.get_cache_stats()
        
        return status


def main():
    """Главная функция для тестирования"""
    logger.info("Запуск Universal Camunda Worker")
    
    worker = UniversalCamundaWorker()
    
    try:
        worker.start()
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания")
    finally:
        worker.shutdown()


if __name__ == "__main__":
    main() 