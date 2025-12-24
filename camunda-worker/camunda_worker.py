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
import os
from typing import Dict, Any, Optional, Tuple
from loguru import logger

# SSL Patch - ДОЛЖЕН быть импортирован ДО ExternalTaskClient
import ssl_patch
from tenant_external_task_client import TenantAwareExternalTaskClient
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
        self.client: Optional[TenantAwareExternalTaskClient] = None
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
    
    def _save_response_message_debug(self, message_data: Dict[str, Any]) -> None:
        """
        ОТЛАДОЧНАЯ ФУНКЦИЯ: Сохранение сообщения из camunda.responses.queue в JSON файл
        TODO: Удалить после завершения отладки
        """
        try:
            # Создаем директорию для отладочных файлов
            debug_dir = "logs/debug"
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            
            # Путь к файлу для сохранения всех сообщений
            debug_file = os.path.join(debug_dir, "response_messages_debug.json")
            
            # Подготавливаем данные для сохранения
            debug_entry = {
                "timestamp": time.time(),
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "message_data": message_data
            }
            
            # Дописываем в конец файла
            with open(debug_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(debug_entry, ensure_ascii=False) + "\n")
            
            logger.debug(f"DEBUG: Сообщение сохранено в {debug_file}")
            
        except Exception as e:
            # Не прерываем основной процесс при ошибке отладки
            logger.error(f"Ошибка сохранения отладочного сообщения: {e}")
    
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
            
            # Создание TenantAwareExternalTaskClient с поддержкой multi-tenancy
            self.client = TenantAwareExternalTaskClient(
                worker_id=self.config.worker_id,
                engine_base_url=self.config.base_url,
                config=client_config,
                tenant_id=self.config.tenant_id  # Фильтрация по tenant
            )
            
            # Логирование информации о tenant
            if self.config.tenant_id:
                logger.info(f"🏢 Tenant ID: {self.config.tenant_id}")
            else:
                logger.warning("⚠️ Tenant ID не указан - будут получаться задачи всех тенантов")
            
            # Инициализация кэша метаданных BPMN
            self.metadata_cache = BPMNMetadataCache(
                base_url=self.config.base_url,
                auth_username=self.config.auth_username if self.config.auth_enabled else None,
                auth_password=self.config.auth_password if self.config.auth_enabled else None,
                max_cache_size=150,  # Для ~100 процессов с запасом
                ttl_hours=24         # Кэш живет 24 часа
            )
            
            # DEBUG: Создаем директорию для отладочных файлов
            # TODO: Удалить после завершения отладки
            debug_dir = "logs/debug"
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
                logger.debug(f"DEBUG: Создана директория для отладочных файлов: {debug_dir}")
            
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
                    if len(tasks) > 1:  # Логируем только если получено несколько задач
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
            self.stats["processed_tasks"] += 1
            
            # Создание объекта ExternalTask
            task = ExternalTask(task_data)
            
            # Получение метаданных активности из BPMN XML
            process_definition_id = task_data.get('processDefinitionId')
            activity_id = task.get_activity_id()
            process_instance_id = task.get_process_instance_id()
            
            logger.debug(f"Получение метаданных для задачи {task_id}: process_definition_id={process_definition_id}, activity_id={activity_id}")
            
            metadata = {}
            if self.metadata_cache and process_definition_id and activity_id:
                try:
                    logger.debug(f"Вызов get_activity_metadata для {process_definition_id}/{activity_id}")
                    metadata = self.metadata_cache.get_activity_metadata(process_definition_id, activity_id)
                    logger.debug(f"Получены метаданные: {metadata}")
                except Exception as e:
                    logger.warning(f"Ошибка получения метаданных для задачи {task_id}: {e}")
            else:
                logger.debug(f"Пропуск получения метаданных: metadata_cache={self.metadata_cache is not None}, process_definition_id={process_definition_id}, activity_id={activity_id}")
            
            # Получение переменных процесса из Camunda
            process_variables = self._get_process_variables(process_instance_id, task_id)
            if isinstance(metadata, dict):
                metadata.setdefault("processVariables", process_variables)
            
            # Логирование исходных данных для отладки
            logger.debug(f"Исходные данные задачи {task_id}: {json.dumps(task_data, ensure_ascii=False, indent=2)}")
            
            # Подготовка расширенных данных для RabbitMQ
            task_payload = {
                "id": task_id,
                "topic": topic,
                "variables": task.get_variables(),
                "processInstanceId": process_instance_id,
                "processDefinitionId": process_definition_id,
                "processDefinitionKey": task_data.get("processDefinitionKey"),  # Из исходных данных задачи
                "activityId": activity_id,
                "activityInstanceId": task_data.get("activityInstanceId"),
                "workerId": task.get_worker_id(),
                "retries": task_data.get("retries"),
                "createTime": task_data.get("createTime"),
                "priority": task_data.get("priority", 0),
                "tenantId": task.get_tenant_id(),
                "businessKey": task.get_business_key(),
                # Добавляем метаданные BPMN
                "metadata": metadata,
                # Добавляем переменные процесса уровня процесса
                "processVariables": process_variables
            }
            
            # Логирование processDefinitionKey для отладки
            process_def_key = task_data.get("processDefinitionKey")
            if process_def_key:
                logger.info(f"processDefinitionKey найден для задачи {task_id}: {process_def_key}")
            else:
                logger.error(f"processDefinitionKey НЕ найден для задачи {task_id}. Доступные поля: {list(task_data.keys())}")
                # Попытка извлечь ключ из processDefinitionId
                if process_definition_id:
                    try:
                        # processDefinitionId обычно имеет формат "key:version:id"
                        extracted_key = process_definition_id.split(':')[0]
                        logger.info(f"Извлечен ключ процесса из processDefinitionId: {extracted_key}")
                        # Обновляем processDefinitionKey в task_payload
                        task_payload["processDefinitionKey"] = extracted_key
                    except Exception as e:
                        logger.error(f"Ошибка извлечения ключа из processDefinitionId {process_definition_id}: {e}")
            
            # Определение целевой системы
            system = self.routing_config.get_system_for_topic(topic)
            
            # ТРАНЗАКЦИОННАЯ БЕЗОПАСНОСТЬ: Сначала отправляем в RabbitMQ, только потом считаем задачу обработанной
            logger.info(f"Подготовка к отправке задачи {task_id} в {system}...")
            
            # Отправка в RabbitMQ с повторными попытками
            publish_success = False
            max_publish_attempts = 3
            
            for attempt in range(max_publish_attempts):
                try:
                    if self.rabbitmq_client.publish_task(topic, task_payload):
                        publish_success = True
                        break
                    else:
                        logger.warning(f"Попытка {attempt + 1}/{max_publish_attempts} отправки задачи {task_id} не удалась")
                        if attempt < max_publish_attempts - 1:
                            time.sleep(2)  # Пауза перед повторной попыткой
                except Exception as publish_error:
                    logger.warning(f"Ошибка попытки {attempt + 1}/{max_publish_attempts} отправки задачи {task_id}: {publish_error}")
                    if attempt < max_publish_attempts - 1:
                        time.sleep(2)
            
            if publish_success:
                self.stats["successful_tasks"] += 1
                logger.info(f"✅ Задача {task_id} успешно отправлена в {system}, ожидает ответа")
            else:
                # КРИТИЧЕСКАЯ ОШИБКА: Задача заблокирована, но не отправлена в RabbitMQ
                logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Задача {task_id} заблокирована, но не удалось отправить в RabbitMQ после {max_publish_attempts} попыток")
                raise Exception(f"Не удалось опубликовать задачу {task_id} в RabbitMQ после {max_publish_attempts} попыток")
                
        except Exception as e:
            self._handle_task_error(task_id, topic, str(e))
    
    def _handle_task_error(self, task_id: str, topic: str, error: str):
        """Обработка ошибки задачи"""
        try:
            logger.error(f"Ошибка обработки задачи {task_id}: {error}")
            self.stats["failed_tasks"] += 1
            
            # Проверяем, является ли это критической ошибкой (задача заблокирована, но не отправлена)
            is_critical_error = "заблокирована, но не удалось отправить" in error or "КРИТИЧЕСКАЯ ОШИБКА" in error
            
            if is_critical_error:
                logger.critical(f"🚨 КРИТИЧЕСКАЯ ОШИБКА: Задача {task_id} заблокирована в Camunda, но не отправлена в RabbitMQ!")
                logger.critical(f"🚨 Это может привести к зависанию процесса! Требуется ручное вмешательство.")
            
            # Попытка отправки ошибки в RabbitMQ (может не удаться при проблемах с соединением)
            try:
                self.rabbitmq_client.publish_error(topic, task_id, error)
            except Exception as publish_error:
                logger.error(f"Не удалось отправить ошибку в RabbitMQ для задачи {task_id}: {publish_error}")
            
            # Возврат задачи в Camunda с ошибкой
            retries = max(0, self.worker_config.retry_attempts - 1)
            
            # Для критических ошибок уменьшаем количество попыток
            if is_critical_error:
                retries = 0  # Не повторяем критические ошибки
                logger.warning(f"Критическая ошибка для задачи {task_id}, retries установлен в 0")
            
            success = self.client.failure(
                task_id=task_id,
                error_message=f"Task processing error: {error}",
                error_details=error,
                retries=retries,
                retry_timeout=self.worker_config.retry_delay * 1000
            )
            
            if success:
                if is_critical_error:
                    logger.critical(f"🚨 Задача {task_id} возвращена с критической ошибкой (retries: {retries})")
                else:
                    logger.warning(f"Задача {task_id} возвращена с ошибкой (retries: {retries})")
            else:
                logger.error(f"Не удалось вернуть задачу {task_id} с ошибкой")
                
        except Exception as handle_error:
            logger.error(f"Ошибка обработки ошибки задачи {task_id}: {handle_error}")
    
    def _get_process_variables(self, process_instance_id: Optional[str], task_id: str) -> Dict[str, Any]:
        """Получение переменных процесса из Camunda по ID экземпляра процесса"""
        if not process_instance_id:
            logger.debug(f"Пропуск получения переменных процесса для задачи {task_id}: отсутствует processInstanceId")
            return {}
        
        base_url = self.config.base_url.rstrip('/')
        url = f"{base_url}/process-instance/{process_instance_id}/variables"
        timeout_seconds = max(1, int(self.config.http_timeout_millis)) / 1000
        auth = None
        if self.config.auth_enabled:
            auth = (self.config.auth_username, self.config.auth_password)
        
        try:
            logger.debug(f"Запрос переменных процесса для задачи {task_id}: {url}")
            response = requests.get(url, auth=auth, timeout=timeout_seconds)
            response.raise_for_status()
            variables = response.json()
            if not isinstance(variables, dict):
                logger.warning(f"Неверный формат переменных процесса для {process_instance_id}: ожидается dict, получено {type(variables)}")
                return {}
            logger.debug(f"Получены переменные процесса для задачи {task_id}: {list(variables.keys())}")
            return variables
        except requests.exceptions.RequestException as request_error:
            logger.warning(f"Ошибка получения переменных процесса {process_instance_id} для задачи {task_id}: {request_error}")
        except ValueError as parse_error:
            logger.warning(f"Ошибка разбора переменных процесса {process_instance_id} для задачи {task_id}: {parse_error}")
        
        return {}
    
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
        """
        Обработка одного сообщения из очереди ответов.
        
        При ошибке обработки сообщение перемещается в очередь ошибок
        (errors.camunda_tasks.queue) для последующего анализа.
        """
        method_frame = None
        message_data = None
        
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
                # Перемещаем в очередь ошибок даже при ошибке парсинга
                self.rabbitmq_client.publish_response_processing_error(
                    original_message={"raw_body": body.decode('utf-8', errors='replace')},
                    error_info={
                        "type": "json_parse_error",
                        "message": f"Ошибка парсинга JSON: {e}"
                    },
                    task_id="unknown",
                    activity_id=None
                )
                self.rabbitmq_client.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                return True
            
            # DEBUG: Сохраняем сообщение в отладочный файл перед обработкой (если включено)
            if self.config.debug_save_response_messages:
                self._save_response_message_debug(message_data)
            
            self.stats["processed_responses"] += 1
            
            # Извлекаем task_id и activity_id для использования в ошибках
            original_message = message_data.get("original_message", {})
            task_id = original_message.get("task_id", "unknown")
            activity_id = original_message.get("activity_id")
            
            # Обрабатываем ответное сообщение
            success, error_info = self._process_response_message(message_data)
            
            if success:
                # Успешная обработка - просто ACK
                self.rabbitmq_client.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
            else:
                # Ошибка обработки - перемещаем в очередь ошибок
                logger.warning(f"Ошибка обработки задачи {task_id}, перемещаем в очередь ошибок...")
                
                # Публикуем в очередь ошибок
                error_published = self.rabbitmq_client.publish_response_processing_error(
                    original_message=message_data,
                    error_info=error_info or {"type": "unknown_error", "message": "Unknown error"},
                    task_id=task_id,
                    activity_id=activity_id
                )
                
                if error_published:
                    # Успешно переместили в очередь ошибок - ACK оригинал
                    self.rabbitmq_client.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                    logger.info(f"Сообщение для задачи {task_id} перемещено в очередь ошибок")
                else:
                    # Не удалось переместить в очередь ошибок - NACK для повторной попытки
                    logger.error(f"Не удалось переместить задачу {task_id} в очередь ошибок, возвращаем в очередь")
                    self.rabbitmq_client.channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)
            
            return True
            
        except Exception as e:
            logger.error(f"Критическая ошибка при обработке сообщения из очереди ответов: {e}")
            
            # Пытаемся переместить в очередь ошибок даже при критической ошибке
            if method_frame:
                try:
                    task_id = "unknown"
                    activity_id = None
                    if message_data:
                        task_id = message_data.get("original_message", {}).get("task_id", "unknown")
                        activity_id = message_data.get("original_message", {}).get("activity_id")
                    
                    error_published = self.rabbitmq_client.publish_response_processing_error(
                        original_message=message_data or {"error": "message_data not available"},
                        error_info={
                            "type": "critical_exception",
                            "message": f"Критическая ошибка: {e}"
                        },
                        task_id=task_id,
                        activity_id=activity_id
                    )
                    
                    if error_published:
                        self.rabbitmq_client.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                        logger.info(f"Критическая ошибка для задачи {task_id} перемещена в очередь ошибок")
                    else:
                        # Если не удалось переместить в очередь ошибок - ACK чтобы не блокировать
                        # (лучше потерять сообщение, чем заблокировать всю очередь)
                        self.rabbitmq_client.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                        logger.critical(f"ПОТЕРЯ ДАННЫХ: Не удалось сохранить ошибку для задачи {task_id}")
                except Exception as ack_error:
                    logger.critical(f"Не удалось обработать ошибку: {ack_error}")
            
            return False
    
    def _convert_uf_result_answer(self, uf_result_answer_text: str) -> str:
        """
        Конвертирует значения ufResultAnswer_text для использования в conditionExpression
        
        Args:
            uf_result_answer_text: Текстовое значение ответа из Bitrix24
            
        Returns:
            Конвертированное значение для использования в Camunda:
            - "НЕТ" -> "no"
            - "ДА" -> "ok"  
            - другие значения -> "no" (по умолчанию)
        """
        try:
            if not uf_result_answer_text:
                return "no"
            
            # Приводим к верхнему регистру для унификации
            answer_upper = str(uf_result_answer_text).strip().upper()
            
            # Конвертируем значения
            if answer_upper == "ДА":
                return "ok"
            elif answer_upper == "НЕТ":
                return "no"
            else:
                # По умолчанию для неизвестных значений
                logger.warning(f"Неизвестное значение ufResultAnswer_text: '{uf_result_answer_text}', используем 'no'")
                return "no"
                
        except Exception as e:
            logger.error(f"Ошибка конвертации ufResultAnswer_text '{uf_result_answer_text}': {e}")
            return "no"

    def _is_truthy_uf_result_expected(self, value: Any) -> bool:
        """
        UF_RESULT_EXPECTED в Bitrix24 может приходить в разных форматах:
        - "1"/"0"
        - "Y"/"N"
        - True/False
        - "true"/"false"
        """
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        v = str(value).strip().lower()
        return v in {"1", "y", "yes", "true", "да"}

    def _convert_question_answer_for_camunda(self, q_type: Any, answer: Any) -> Any:
        """
        Преобразование answer из Bitrix questionnaires под типы переменных Camunda.
        Требования:
        - boolean/integer/string/date -> конвертируем в соответствующий тип
        - user/enum/universal_list/прочее -> оставляем строкой
        - answer == None -> вернуть None (Camunda Null), кроме boolean
        """
        q_type_str = (str(q_type).strip().lower() if q_type is not None else "")

        # Bitrix v2.0: boolean answers are strings "true"/"false"
        # ВАЖНО: Для boolean, если answer=None (чек-бокс не установлен), возвращаем False
        # Это критично для работы Gateway условий (null != false)
        if q_type_str == "boolean":
            if answer is None:
                return False
            v = str(answer).strip().lower()
            return v in {"true", "1", "y", "yes", "да"}

        if answer is None:
            return None
        if q_type_str == "integer":
            try:
                return int(str(answer).strip())
            except Exception:
                # По контракту: если тип указан явно, пытаемся привести.
                # При неудаче — сохраняем как строку, но логируем.
                logger.debug(f"Не удалось привести integer answer='{answer}' к int; сохраняем строкой")
                return str(answer)
        if q_type_str in {"string", "date"}:
            return str(answer)

        # Неявные типы: user/enum/universal_list и любые другие оставляем строкой
        return str(answer)

    def _apply_questionnaires_to_variables(self, message_data: Dict[str, Any], variables: Dict[str, Any]):
        """
        Разворачивает анкеты из response_data.result.questionnaires в плоские process variables:
        {ELEMENT_ID}_{QUESTIONNAIRE_CODE}_{QUESTION_CODE} = answer

        - ELEMENT_ID = original_message.activity_id
        - answer == null -> переменная создаётся со значением None (Camunda Null)
        """
        try:
            original_message = message_data.get("original_message", {}) or {}
            element_id = original_message.get("activity_id")
            if not element_id:
                return

            questionnaires = (
                message_data.get("response_data", {})
                .get("result", {})
                .get("questionnaires")
            )
            if not isinstance(questionnaires, dict):
                return

            items = questionnaires.get("items")
            if not isinstance(items, list) or not items:
                return

            # DEBUG: краткая сводка, сырой JSON не пишем в процесс
            logger.debug(f"Questionnaires: taskId={questionnaires.get('taskId')} items={len(items)}")

            for qn in items:
                if not isinstance(qn, dict):
                    continue
                qn_code = qn.get("CODE")
                if not qn_code:
                    continue
                questions = qn.get("questions")
                if not isinstance(questions, list):
                    continue

                for q in questions:
                    if not isinstance(q, dict):
                        continue
                    q_code = q.get("CODE")
                    if not q_code:
                        continue
                    var_name = f"{element_id}_{qn_code}_{q_code}"

                    q_type = q.get("TYPE")
                    answer = q.get("answer")
                    variables[var_name] = self._convert_question_answer_for_camunda(q_type, answer)

        except Exception as e:
            logger.error(f"Ошибка преобразования анкет в переменные Camunda: {e}")

    def _process_response_message(self, message_data: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Обработка ответного сообщения и завершение задачи в Camunda
        
        ИСПРАВЛЕНИЯ (2025-01-13):
        - Убрано загрязнение переменных процесса битрикс-специфичными полями
        - Удалена переменная result из переменных процесса  
        - Логика проверки ответа использует ufResultExpected вместо checkListCanAdd
        - Данные извлекаются только из строго определенных полей API ответа
        
        Returns:
            Tuple[bool, Optional[Dict]]:
                - (True, None) при успехе
                - (False, error_info) при ошибке, где error_info содержит детали
        """
        try:
            # Извлекаем данные из сообщения
            original_message = message_data.get("original_message", {})
            response_data = message_data.get("response_data", {})
            processing_status = message_data.get("processing_status")
            
            task_id = original_message.get("task_id")
            if not task_id:
                logger.error("Отсутствует task_id в ответном сообщении")
                return False, {
                    "type": "missing_task_id",
                    "message": "Отсутствует task_id в ответном сообщении"
                }
            
            logger.info(f"Обрабатываем ответ для задачи {task_id} (статус: {processing_status})")
            
            # Проверяем статус обработки
            # Поддерживаем оба статуса: completed (прямой ответ) и completed_by_tracker (через tracker)
            if processing_status not in ["completed", "completed_by_tracker"]:
                logger.warning(f"Задача {task_id} имеет неподдерживаемый статус '{processing_status}', пропускаем")
                return True, None  # Считаем успешным, удаляем сообщение
            
            # Дополнительная информация о типе обработки
            if processing_status == "completed_by_tracker":
                logger.info(f"Задача {task_id} завершена через tracker (автоматическое отслеживание)")
            else:
                logger.info(f"Задача {task_id} завершена через прямой ответ системы")
            
            # Подготавливаем переменные для Camunda
            original_variables = message_data.get("original_message", {}).get("variables", {})
            variables = original_variables.copy() if original_variables else {}
            
            # НЕ определяем и НЕ добавляем переменную result в переменные процесса,
            # так как она больше не используется в логике conditionExpression
            # Удаляем строки:
            # result_status = self._determine_result_status(response_data)
            # variables["result"] = result_status
            
            # Извлекаем данные из ответа системы (например, Bitrix24)
            self._extract_response_data(response_data, variables)

            # Анкеты: раскладываем ответы по вопросам в плоские переменные процесса
            # Формат: {ELEMENT_ID}_{QUESTIONNAIRE_CODE}_{QUESTION_CODE}
            self._apply_questionnaires_to_variables(message_data, variables)
            
            # Новая логика для conditionExpression с activity_id
            activity_id = original_message.get("activity_id")
            if activity_id:
                # Извлекаем данные задачи из response_data
                task_data = response_data.get("result", {}).get("task", {})
                
                # Проверяем, требуется ли ответ от пользователя по полю ufResultExpected
                # Это поле устанавливается при создании задачи на основе UF_RESULT_EXPECTED из metadata
                # Поддерживаем оба формата: camelCase (ufResultExpected) и UPPER_CASE (UF_RESULT_EXPECTED)
                uf_result_expected = task_data.get("ufResultExpected") or task_data.get("UF_RESULT_EXPECTED")
                
                # Создаем переменную activity_id ТОЛЬКО если задача требует ответа.
                # Если ответ не требуется — переменная activity_id НЕ нужна Camunda и не должна появляться.
                if self._is_truthy_uf_result_expected(uf_result_expected):
                    # Задача требует ответа от пользователя
                    uf_result_answer_text = task_data.get("ufResultAnswer_text")
                    
                    if uf_result_answer_text:
                        # Конвертируем значение для использования в Camunda
                        converted_value = self._convert_uf_result_answer(uf_result_answer_text)
                        
                        # Создаем переменную с именем activity_id
                        variables.setdefault(activity_id, converted_value)
                        
                        logger.debug(f"Создана переменная процесса: {activity_id} = '{converted_value}' (исходное: '{uf_result_answer_text}')")
                    else:
                        # Ответ требуется, но не найден - используем значение по умолчанию
                        # Это может произойти, если задача была завершена без ответа
                        # ВАЖНО: не затираем существующее значение переменной (если оно уже есть в процессе).
                        # По умолчанию ставим 'no' (безопаснее для conditional flow, чем всегда 'ok').
                        variables.setdefault(activity_id, "no")
                        logger.debug(f"Ответ требуется (ufResultExpected truthy), но ufResultAnswer_text не найден для activity_id: {activity_id}. Устанавливаем значение по умолчанию 'no'")
                else:
                    # Задача не требует ответа от пользователя — НЕ создаем переменную activity_id.
                    logger.debug(
                        f"Задача {task_id} не требует ответа от пользователя "
                        f"(ufResultExpected: {uf_result_expected}); переменная {activity_id} не будет создана"
                    )
            else:
                logger.warning("Не найден activity_id в original_message")
            
            # Завершаем задачу в Camunda
            return self._complete_task_in_camunda(task_id, variables)
            
        except Exception as e:
            error_msg = f"Ошибка обработки ответного сообщения: {e}"
            logger.error(error_msg)
            return False, {
                "type": "processing_exception",
                "message": error_msg
            }
    
    def _extract_response_data(self, response_data: Dict[str, Any], variables: Dict[str, Any]):
        """Извлечение данных из ответа системы и добавление в переменные Camunda"""
        try:
            # Получаем результат из response_data
            result = response_data.get("result", {})
            
            # Логируем структуру для отладки
            logger.debug(f"Извлекаем данные из response_data.result: {result}")
            
            # Извлекаем данные задачи (например, от Bitrix24)
            task_data = result.get("task", {})
            if task_data:
                # Вспомогательная функция для получения значения с поддержкой обоих регистров
                def get_field(key_upper: str, key_lower: str = None) -> Any:
                    """Получает значение поля, проверяя оба регистра"""
                    if key_lower is None:
                        # Автоматически создаем camelCase версию из UPPER_CASE
                        # ID -> id, TITLE -> title, CREATED_DATE -> createdDate
                        key_lower = key_upper.lower()
                        if '_' in key_upper:
                            # Для полей с подчеркиванием: CREATED_DATE -> createdDate
                            parts = key_upper.lower().split('_')
                            key_lower = parts[0] + ''.join(p.capitalize() for p in parts[1:])
                    return task_data.get(key_upper) or task_data.get(key_lower)
                
                # Основные данные задачи (поддержка обоих регистров)
                task_id = get_field("ID", "id")
                if task_id:
                    variables["bitrix_task_id"] = str(task_id)
                
                task_title = get_field("TITLE", "title")
                if task_title:
                    variables["bitrix_task_title"] = str(task_title)
                
                task_status = get_field("STATUS", "status")
                if task_status:
                    variables["bitrix_task_status"] = str(task_status)
                
                # НЕ добавляем пользовательские поля (UF_) в переменные процесса,
                # так как они специфичны для конкретной задачи и не должны влиять на весь процесс
                # УДаляем закомментированную секцию "Пользовательские поля (UF_)"
                
                logger.info(f"Извлечены данные задачи Bitrix24: ID={task_id}, Title={task_title}")
            
            # НЕ извлекаем системные данные из result в переменные процесса
            # так как они не нужны для логики процесса
            # Удаляем секцию извлечения success, message, error
            
            # НЕ сохраняем полный response_data в переменные процесса
            # так как это может привести к разрастанию переменных и проблемам с памятью
            # Удаляем строку variables["response_data"] = response_data
            
        except Exception as e:
            logger.error(f"Ошибка извлечения данных из response_data: {e}")
            # Не прерываем выполнение, просто логируем ошибку
    
    def _complete_task_in_camunda(self, task_id: str, variables: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Завершение задачи в Camunda через REST API.
        
        Returns:
            Tuple[bool, Optional[Dict]]: 
                - (True, None) при успехе
                - (False, error_info) при ошибке, где error_info содержит детали ошибки
        """
        try:
            # Формируем URL для завершения задачи
            base_url = self.config.base_url.rstrip('/')
            if base_url.endswith('/engine-rest'):
                api_base_url = base_url
            else:
                api_base_url = f"{base_url}/engine-rest"
            
            url = f"{api_base_url}/external-task/{task_id}/complete"
            
            # Подготавливаем payload
            formatted_variables = self._format_variables(variables)
            payload = {
                "workerId": self.config.worker_id,
                "variables": formatted_variables
            }
            
            # Настраиваем аутентификацию
            auth = None
            if self.config.auth_enabled:
                auth = (self.config.auth_username, self.config.auth_password)
            
            import time
            start_time = time.time()
            
            try:
                response = requests.post(
                    url, 
                    json=payload, 
                    auth=auth, 
                    timeout=10,  # Короткий таймаут - 10 секунд
                    headers={'Content-Type': 'application/json'}
                )
                
                request_duration = time.time() - start_time
                
            except requests.exceptions.Timeout:
                error_msg = f"Таймаут запроса к Camunda для задачи {task_id} (>10с)"
                logger.error(f"⏰ {error_msg}")
                return False, {
                    "type": "timeout_error",
                    "message": error_msg,
                    "http_status_code": None
                }
            except requests.exceptions.ConnectionError as e:
                error_msg = f"Ошибка соединения с Camunda для задачи {task_id}: {e}"
                logger.error(f"🔌 {error_msg}")
                return False, {
                    "type": "connection_error",
                    "message": error_msg,
                    "http_status_code": None
                }
            except requests.exceptions.RequestException as e:
                error_msg = f"Ошибка HTTP запроса к Camunda для задачи {task_id}: {e}"
                logger.error(f"🌐 {error_msg}")
                return False, {
                    "type": "request_error",
                    "message": error_msg,
                    "http_status_code": None
                }
            
            if response.status_code == 204:
                self.stats["successful_completions"] += 1
                return True, None
            elif response.status_code == 404:
                logger.warning(f"🔍 Задача {task_id} не найдена в Camunda (возможно уже завершена или истёк lock)")
                # Считаем это успехом - задача больше не активна
                self.stats["successful_completions"] += 1
                return True, None
            elif response.status_code == 500:
                logger.error(f"💥 Внутренняя ошибка Camunda для задачи {task_id}: {response.text}")
                # Получаем детальную информацию об ошибке
                error_info = {
                    "type": "camunda_internal_error",
                    "message": f"Internal server error from Camunda",
                    "http_status_code": 500,
                    "raw_response": response.text
                }
                try:
                    error_data = response.json()
                    error_type = error_data.get("type", "unknown")
                    error_message = error_data.get("message", "unknown")
                    logger.error(f"   Тип ошибки: {error_type}")
                    logger.error(f"   Сообщение: {error_message}")
                    error_info["camunda_error_type"] = error_type
                    error_info["camunda_error_message"] = error_message
                except:
                    pass
                self.stats["failed_completions"] += 1
                return False, error_info
            else:
                error_msg = f"Неожиданный код ответа от Camunda: HTTP {response.status_code}"
                logger.error(f"❌ {error_msg} для задачи {task_id} - {response.text}")
                self.stats["failed_completions"] += 1
                return False, {
                    "type": "unexpected_http_status",
                    "message": error_msg,
                    "http_status_code": response.status_code,
                    "raw_response": response.text
                }
                
        except Exception as e:
            error_msg = f"Исключение при завершении задачи {task_id} в Camunda: {e}"
            logger.error(f"💥 {error_msg}")
            import traceback
            traceback.print_exc()
            self.stats["failed_completions"] += 1
            return False, {
                "type": "exception",
                "message": error_msg,
                "http_status_code": None
            }
    
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
        """Поток мониторинга соединений и обработки ответов"""
        last_response_check = 0
        
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                
                if self.running and self.stats["start_time"]:
                    # Проверка соединения с RabbitMQ
                    if not self.rabbitmq_client.is_connected():
                        logger.warning("RabbitMQ соединение потеряно, попытка переподключения...")
                        self.rabbitmq_client.reconnect()
                    
                    # Проверка очереди ответов с интервалом heartbeat_interval
                    if current_time - last_response_check >= self.worker_config.heartbeat_interval:
                        self._check_response_queue()
                        last_response_check = current_time
                
                # Проверка каждые heartbeat_interval секунд
                self.stop_event.wait(self.worker_config.heartbeat_interval)
                
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