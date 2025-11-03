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
from typing import Dict, Any, Optional
from loguru import logger

# SSL Patch - ДОЛЖЕН быть импортирован ДО ExternalTaskClient
import ssl_patch
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
            
            # Логирование исходных данных для отладки
            logger.debug(f"Исходные данные задачи {task_id}: {json.dumps(task_data, ensure_ascii=False, indent=2)}")
            
            # Подготовка расширенных данных для RabbitMQ
            task_payload = {
                "id": task_id,
                "topic": topic,
                "variables": task.get_variables(),
                "processInstanceId": task.get_process_instance_id(),
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
                "metadata": metadata
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
                # ACK даже при ошибке парсинга - чтобы не блокировать очередь
                self.rabbitmq_client.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                return True
            
            # DEBUG: Сохраняем сообщение в отладочный файл перед обработкой (если включено)
            if self.config.debug_save_response_messages:
                self._save_response_message_debug(message_data)
            
            self.stats["processed_responses"] += 1
            
            # Обрабатываем ответное сообщение
            success = self._process_response_message(message_data)
            
            # ВСЕГДА ACK, даже если обработка не удалась
            # Т.к. Camunda API может вернуть 404 если задача уже завершена (retry)
            self.rabbitmq_client.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
            
            if not success:
                # Логируем, но не requeue - избегаем бесконечного цикла
                task_id = message_data.get("original_message", {}).get("task_id", "unknown")
                logger.error(f"Failed to process response for task {task_id}, but ACK sent to avoid loop")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения из очереди ответов: {e}")
            # При критической ошибке - ACK чтобы не блокировать очередь
            if 'method_frame' in locals() and method_frame:
                try:
                    self.rabbitmq_client.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                except:
                    pass  # Игнорируем ошибки ACK при критических ошибках
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

    def _process_response_message(self, message_data: Dict[str, Any]) -> bool:
        """
        Обработка ответного сообщения и завершение задачи в Camunda
        
        ИСПРАВЛЕНИЯ (2025-01-13):
        - Убрано загрязнение переменных процесса битрикс-специфичными полями
        - Удалена переменная result из переменных процесса  
        - Логика проверки ответа использует ufResultExpected вместо checkListCanAdd
        - Данные извлекаются только из строго определенных полей API ответа
        """
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
            # Поддерживаем оба статуса: completed (прямой ответ) и completed_by_tracker (через tracker)
            if processing_status not in ["completed", "completed_by_tracker"]:
                logger.warning(f"Задача {task_id} имеет неподдерживаемый статус '{processing_status}', пропускаем")
                return True  # Считаем успешным, удаляем сообщение
            
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
            
            # Новая логика для conditionExpression с activity_id
            activity_id = original_message.get("activity_id")
            if activity_id:
                # Извлекаем данные задачи из response_data
                task_data = response_data.get("result", {}).get("task", {})
                
                # Проверяем, требуется ли ответ от пользователя по полю ufResultExpected
                # Это поле устанавливается при создании задачи на основе UF_RESULT_EXPECTED из metadata
                uf_result_expected = task_data.get("ufResultExpected")
                
                # Задача требует ответа только если ufResultExpected равно "1" (Y в Bitrix24)
                if uf_result_expected == "1":
                    # Задача требует ответа от пользователя
                    uf_result_answer_text = task_data.get("ufResultAnswer_text")
                    
                    if uf_result_answer_text:
                        # Конвертируем значение для использования в Camunda
                        converted_value = self._convert_uf_result_answer(uf_result_answer_text)
                        
                        # Создаем переменную с именем activity_id
                        variables[activity_id] = converted_value
                        
                        logger.info(f"Создана переменная процесса: {activity_id} = '{converted_value}' (исходное: '{uf_result_answer_text}')")
                    else:
                        logger.warning(f"Не найдено значение ufResultAnswer_text для activity_id: {activity_id}")
                else:
                    # Задача не требует ответа от пользователя (ufResultExpected != "1")
                    logger.info(f"Задача {task_id} не требует ответа от пользователя (ufResultExpected: {uf_result_expected}), пропускаем установку переменной {activity_id}")
            else:
                logger.warning("Не найден activity_id в original_message")
            
            # Завершаем задачу в Camunda
            return self._complete_task_in_camunda(task_id, variables)
            
        except Exception as e:
            logger.error(f"Ошибка обработки ответного сообщения: {e}")
            return False
    
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
                # Основные данные задачи
                if "ID" in task_data:
                    variables["bitrix_task_id"] = str(task_data["ID"])
                if "TITLE" in task_data:
                    variables["bitrix_task_title"] = str(task_data["TITLE"])
                if "DESCRIPTION" in task_data:
                    variables["bitrix_task_description"] = str(task_data["DESCRIPTION"])
                if "STATUS" in task_data:
                    variables["bitrix_task_status"] = str(task_data["STATUS"])
                if "PRIORITY" in task_data:
                    variables["bitrix_task_priority"] = str(task_data["PRIORITY"])
                
                # Даты
                if "CREATED_DATE" in task_data:
                    variables["bitrix_task_created_date"] = str(task_data["CREATED_DATE"])
                if "CHANGED_DATE" in task_data:
                    variables["bitrix_task_changed_date"] = str(task_data["CHANGED_DATE"])
                if "DEADLINE" in task_data:
                    variables["bitrix_task_deadline"] = str(task_data["DEADLINE"])
                
                # Пользователи
                if "CREATED_BY" in task_data:
                    variables["bitrix_task_created_by"] = str(task_data["CREATED_BY"])
                if "RESPONSIBLE_ID" in task_data:
                    variables["bitrix_task_responsible_id"] = str(task_data["RESPONSIBLE_ID"])
                
                # Дополнительные данные
                if "GROUP_ID" in task_data:
                    variables["bitrix_task_group_id"] = str(task_data["GROUP_ID"])
                if "PARENT_ID" in task_data:
                    variables["bitrix_task_parent_id"] = str(task_data["PARENT_ID"])
                
                # НЕ добавляем пользовательские поля (UF_) в переменные процесса,
                # так как они специфичны для конкретной задачи и не должны влиять на весь процесс
                # УДаляем закомментированную секцию "Пользовательские поля (UF_)"
                
                logger.info(f"Извлечены данные задачи Bitrix24: ID={task_data.get('ID')}, Title={task_data.get('TITLE')}")
            
            # НЕ извлекаем системные данные из result в переменные процесса
            # так как они не нужны для логики процесса
            # Удаляем секцию извлечения success, message, error
            
            # НЕ сохраняем полный response_data в переменные процесса
            # так как это может привести к разрастанию переменных и проблемам с памятью
            # Удаляем строку variables["response_data"] = response_data
            
        except Exception as e:
            logger.error(f"Ошибка извлечения данных из response_data: {e}")
            # Не прерываем выполнение, просто логируем ошибку
    
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
                logger.error(f"⏰ Таймаут запроса к Camunda для задачи {task_id} (>10с)")
                return False
            except requests.exceptions.ConnectionError as e:
                logger.error(f"🔌 Ошибка соединения с Camunda для задачи {task_id}: {e}")
                return False
            except requests.exceptions.RequestException as e:
                logger.error(f"🌐 Ошибка HTTP запроса к Camunda для задачи {task_id}: {e}")
                return False
            

            
            if response.status_code == 204:
                self.stats["successful_completions"] += 1
                return True
            elif response.status_code == 404:
                logger.warning(f"🔍 Задача {task_id} не найдена в Camunda (возможно уже завершена или истёк lock)")
                # Считаем это успехом - задача больше не активна
                self.stats["successful_completions"] += 1
                return True
            elif response.status_code == 500:
                logger.error(f"💥 Внутренняя ошибка Camunda для задачи {task_id}: {response.text}")
                # Попробуем получить более детальную информацию об ошибке
                try:
                    error_data = response.json()
                    error_type = error_data.get("type", "unknown")
                    error_message = error_data.get("message", "unknown")
                    logger.error(f"   Тип ошибки: {error_type}")
                    logger.error(f"   Сообщение: {error_message}")
                except:
                    pass
                self.stats["failed_completions"] += 1
                return False
            else:
                logger.error(f"❌ Неожиданный код ответа от Camunda для задачи {task_id}: HTTP {response.status_code} - {response.text}")
                self.stats["failed_completions"] += 1
                return False
                
        except Exception as e:
            logger.error(f"💥 Исключение при завершении задачи {task_id} в Camunda: {e}")
            import traceback
            traceback.print_exc()
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