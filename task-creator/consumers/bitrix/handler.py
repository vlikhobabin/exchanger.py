#!/usr/bin/env python3
"""
Обработчик сообщений для создания задач в Bitrix24
"""
import os
import json
import time
import yaml
import pika
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple
from datetime import datetime, timedelta
import requests
from loguru import logger
from .config import bitrix_config, worker_config
from rabbitmq_publisher import RabbitMQPublisher


class BitrixTaskHandler:
    """Обработчик для создания задач в Bitrix24"""
    
    def __init__(self):
        self.config = bitrix_config
        self.worker_config = worker_config
        self.task_add_url = f"{self.config.webhook_url.rstrip('/')}/tasks.task.add.json"
        
        # RabbitMQ Publisher для отправки успешных сообщений
        self.publisher = RabbitMQPublisher()
        self._template_file_attachment_supported = True
        
        
        # Статистика
        self.stats = {
            "total_messages": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "start_time": time.time(),
            "last_message_time": None,
            "sent_to_success_queue": 0,
            "failed_to_send_success": 0,
            "sync_requests_sent": 0,
            "sync_requests_failed": 0,
            "templates_requested": 0,
            "templates_found": 0,
            "templates_not_found": 0,
            "templates_api_errors": 0,
            "template_files_found": 0,
            "template_files_attached": 0,
            "template_files_failed": 0,
            "dependencies_attempted": 0,
            "dependencies_created": 0,
            "dependencies_failed": 0,
            "predecessor_results_fetched": 0,
            "predecessor_results_failed": 0,
            "predecessor_files_attached": 0,
            "predecessor_files_failed": 0,
            "questionnaires_found": 0,
            "questionnaires_sent": 0,
            "questionnaires_failed": 0
        }

        # Кэш параметров диаграмм Camunda -> Bitrix24
        self.diagram_properties_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.diagram_details_cache: Dict[str, Dict[str, Any]] = {}
        self.element_predecessors_cache: Dict[Tuple[Optional[str], Optional[str], str], List[str]] = {}
        self.responsible_cache: Dict[Tuple[Optional[str], Optional[str], str], Optional[Dict[str, Any]]] = {}
        # Кэш задач по element_id и process_instance_id: ключ = (element_id, process_instance_id)
        self.element_task_cache: Dict[Tuple[Optional[str], Optional[str]], Dict[str, Any]] = {}
        
        # КРИТИЧЕСКАЯ ПРОВЕРКА: Проверяем существование обязательного поля UF_CAMUNDA_ID_EXTERNAL_TASK
        self._check_required_user_field()
    
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
                
                # Отправка успешного результата в очередь bitrix24.sent.queue с retry
                success_sent = self._send_success_message_with_retry(message_data, result, "bitrix24.queue")
                if success_sent:
                    self.stats["sent_to_success_queue"] += 1
                else:
                    self.stats["failed_to_send_success"] += 1
                    logger.warning("Не удалось отправить результат в очередь успешных сообщений")
                
                # ОБЯЗАТЕЛЬНАЯ синхронизация (критически важно для корректной работы)
                logger.debug(f"Попытка синхронизации для задачи {task_id}, данные сообщения: {message_data}")
                sync_success = self._send_sync_request(message_data)
                if sync_success:
                    logger.info(f"Синхронизация выполнена успешно для задачи {task_id}")
                else:
                    logger.error(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось выполнить синхронизацию для задачи {task_id}")
                    # Синхронизация обязательна - это не просто предупреждение
                
                return True
            else:
                self.stats["failed_tasks"] += 1
                error_msg = result.get('error_description', 'Unknown error') if result else 'No response'
                
                # Проверяем, является ли это ошибкой assigneeId
                if result and result.get('error') == 'ASSIGNEE_ID_ERROR':
                    logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА assigneeId: {error_msg}")
                    # Отправляем в очередь ошибок для ручного разбора
                    self._send_to_error_queue(message_data, error_msg)
                    # ВАЖНО: Возвращаем True чтобы сообщение было ACK'нуто и не обрабатывалось повторно
                    return True
                
                logger.error(f"Ошибка создания задачи в Bitrix24: {error_msg}")
                return False
                
        except ValueError as e:
            # Критическая ошибка с assigneeId - отправляем в очередь ошибок
            self.stats["failed_tasks"] += 1
            logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА assigneeId: {e}")
            
            # Отправляем в очередь ошибок для ручного разбора
            self._send_to_error_queue(message_data, str(e))
            # ВАЖНО: Возвращаем True чтобы сообщение было ACK'нуто и не обрабатывалось повторно
            return True
            
        except Exception as e:
            self.stats["failed_tasks"] += 1
            logger.error(f"Критическая ошибка при обработке сообщения: {e}")
            return False
    
    def _create_bitrix_task(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Идемпотентное создание задачи в Bitrix24 на основе данных шаблона из API
        
        Логика:
        1. Извлечь task_id (External Task ID) из message_data
        2. Проверить существование задачи в Bitrix24 по UF_CAMUNDA_ID_EXTERNAL_TASK
        3. Если задача существует:
           - Логировать WARNING о повторной попытке создания
           - Вернуть её данные (как будто только что создали)
        4. Если задачи нет:
           - Получить шаблон задачи через API imena.camunda.tasktemplate.get
           - Если шаблон найден: создать задачу из шаблона
           - Если шаблон не найден: создать задачу с минимальными данными (fallback)
           - Вернуть результат создания
        
        Args:
            message_data: Данные сообщения из RabbitMQ
            
        Returns:
            Ответ от API Bitrix24
        """
        try:
            # Извлечение данных из сообщения
            task_id = message_data.get('task_id', 'unknown')
            metadata = message_data.get('metadata', {})
            
            # Шаг 1: Проверка существования задачи по External Task ID
            existing_task = self._find_task_by_external_id(task_id)
            
            if existing_task:
                # Задача уже существует - возвращаем её (идемпотентность)
                # Поле UF_CAMUNDA_ID_EXTERNAL_TASK должно быть уникальным и соответствовать 1 задаче в ExternalTask
                logger.warning(f"Задача с UF_CAMUNDA_ID_EXTERNAL_TASK={task_id} уже существует в Bitrix24 (ID: {existing_task['id']})")
                logger.warning(f"Это повторная попытка создания. Возвращаем существующую задачу.")
                
                # Формируем ответ в том же формате, что и при создании
                return {
                    "result": {
                        "task": existing_task
                    },
                    "time": {
                        "start": int(time.time()),
                        "finish": int(time.time())
                    }
                }
            
            # Шаг 2: Получение шаблона задачи через API
            camunda_process_id, element_id, diagram_id = self._extract_template_params(message_data)
            
            if not camunda_process_id or not element_id:
                logger.warning(f"Не удалось извлечь параметры для запроса шаблона (camundaProcessId={camunda_process_id}, elementId={element_id})")
                logger.warning("Переход к fallback: создание задачи с минимальными данными")
                return self._create_task_fallback(message_data)
            
            responsible_info = self._get_responsible_info(camunda_process_id, diagram_id, element_id)
            responsible_template_id = None
            if responsible_info:
                responsible_template_id = (
                    responsible_info.get('TEMPLATE_ID') or
                    responsible_info.get('templateId')
                )
            diagram_id_from_responsible = None
            if responsible_info:
                diagram_id_from_responsible = (
                    responsible_info.get('DIAGRAM_ID') or
                    responsible_info.get('diagramId')
                )
            
            template_data = self._get_task_template(
                camunda_process_id,
                element_id,
                template_id=responsible_template_id
            )
            
            if not template_data:
                # Шаблон не найден - используем fallback
                logger.warning(f"Шаблон не найден для camundaProcessId={camunda_process_id}, elementId={element_id}. Переход к fallback")
                if responsible_template_id:
                    logger.warning(
                        f"Для elementId={element_id} найден TEMPLATE_ID={responsible_template_id}, "
                        "но imena.camunda.tasktemplate.get не вернул шаблон. Проверьте настройки Bitrix24."
                    )
                return self._create_task_fallback(message_data)

            questionnaires_data: List[Dict[str, Any]] = self._extract_questionnaires_from_template(template_data)

            diagram_id = self._resolve_diagram_id(
                diagram_id,
                camunda_process_id,
                metadata,
                template_data
            )
            if not diagram_id and diagram_id_from_responsible:
                diagram_id = diagram_id_from_responsible
            
            # Шаг 3: Формирование task_data из шаблона
            task_data, template_files = self._build_task_data_from_template(
                template_data,
                message_data,
                task_id,
                element_id
            )
            if template_files:
                self.stats["template_files_found"] += len(template_files)
                logger.debug(f"Найдено {len(template_files)} файлов в шаблоне для дальнейшего прикрепления (task_id={task_id})")

            # Шаг 3.05: Добавление блока анкет (questionnairesInDescription) в описание задачи
            # Блок анкет вставляется ПЕРЕД блоком переменных процесса
            qid_data = self._extract_questionnaires_in_description(template_data)
            if qid_data:
                # Получаем переменные процесса для формирования ответов
                process_variables = {}
                if isinstance(metadata, dict):
                    pv_from_metadata = metadata.get('processVariables')
                    if isinstance(pv_from_metadata, dict):
                        process_variables = pv_from_metadata
                if not process_variables:
                    pv_direct = message_data.get('process_variables')
                    if isinstance(pv_direct, dict):
                        process_variables = pv_direct

                questionnaires_block = self._build_questionnaires_description_block(
                    qid_data,
                    process_variables,
                    element_id
                )
                if questionnaires_block:
                    current_description = task_data.get('DESCRIPTION', '') or ''
                    if current_description:
                        task_data['DESCRIPTION'] = f"{current_description.rstrip()}\n\n---\n{questionnaires_block}"
                    else:
                        task_data['DESCRIPTION'] = questionnaires_block
                    logger.debug(f"Добавлен блок анкет (questionnairesInDescription) в описание задачи {task_id}")

            # Шаг 3.1: Добавление блока переменных процесса в описание задачи
            variables_block = self._build_process_variables_block(message_data, camunda_process_id, task_id)
            if variables_block:
                current_description = task_data.get('DESCRIPTION', '') or ''
                if current_description:
                    task_data['DESCRIPTION'] = f"{current_description.rstrip()}\n\n---\n{variables_block}"
                else:
                    task_data['DESCRIPTION'] = variables_block
                logger.debug(f"Добавлен блок переменных процесса в описание задачи {task_id}")

            # Шаг 3.2: Добавление списка предшественников
            # Извлекаем process_instance_id для поиска предшественников в рамках одного экземпляра процесса
            process_instance_id = message_data.get('processInstanceId') or message_data.get('process_instance_id')
            predecessor_task_ids = self._apply_predecessor_dependencies(
                task_data,
                camunda_process_id,
                diagram_id,
                element_id,
                responsible_info=responsible_info,
                process_instance_id=process_instance_id
            )
            
            # Шаг 3.3: Получение и добавление результатов предшествующих задач
            predecessor_results: Dict[int, List[Dict[str, Any]]] = {}
            if predecessor_task_ids:
                predecessor_results = self._get_predecessor_results(predecessor_task_ids)
                if predecessor_results:
                    # Добавляем блок текста с результатами в описание
                    results_block = self._build_predecessor_results_block(predecessor_results)
                    if results_block:
                        current_description = task_data.get('DESCRIPTION', '') or ''
                        if current_description:
                            task_data['DESCRIPTION'] = f"{current_description.rstrip()}\n\n---\n{results_block}"
                        else:
                            task_data['DESCRIPTION'] = results_block
                        logger.debug(f"Добавлен блок результатов предшественников в описание задачи {task_id}")
            
            # Шаг 4: Создание задачи в Bitrix24
            result = self._send_task_to_bitrix(task_data)
            
            if result and result.get('error'):
                logger.error(f"Ошибка API Bitrix24 при создании задачи: {result['error']}")
                return result
            
            # Шаг 5: Если задача создана успешно, прикрепляем файлы и создаем чек-листы из шаблона
            if result and result.get('result') and result['result'].get('task'):
                created_task_id = result['result']['task'].get('id')
                if created_task_id:
                    # Прикрепление файлов из шаблона к задаче
                    if template_files:
                        try:
                            self._attach_files_to_task(int(created_task_id), template_files)
                        except Exception as e:
                            logger.error(f"Ошибка прикрепления файлов шаблона к задаче {created_task_id}: {e}")
                            # Не прерываем выполнение, задача уже создана
                    
                    # Создаем зависимости через кастомный REST API
                    try:
                        self._create_task_dependencies(int(created_task_id), predecessor_task_ids)
                    except Exception as e:
                        logger.error(f"Ошибка создания зависимостей для задачи {created_task_id}: {e}")
                    
                    # Прикрепление файлов из результатов предшествующих задач
                    if predecessor_results:
                        try:
                            self._attach_predecessor_files(int(created_task_id), predecessor_results)
                        except Exception as e:
                            logger.error(f"Ошибка прикрепления файлов предшественников к задаче {created_task_id}: {e}")

                    if questionnaires_data:
                        try:
                            logger.info(f"Добавление {len(questionnaires_data)} анкет в задачу {created_task_id}")
                            success = self._add_questionnaires_to_task(int(created_task_id), questionnaires_data)
                            if success:
                                logger.info(f"✅ Анкеты успешно добавлены к задаче {created_task_id}")
                            else:
                                logger.warning(f"⚠️ Анкеты не были добавлены к задаче {created_task_id}")
                        except Exception as e:
                            logger.error(f"Ошибка добавления анкет к задаче {created_task_id}: {e}")
                    
                    checklists_data = self._extract_checklists_from_template(template_data)
                    
                    if checklists_data:
                        logger.info(f"Создание чек-листов для задачи {created_task_id}")
                        try:
                            success = self.create_task_checklists_sync(int(created_task_id), checklists_data)
                            if success:
                                logger.info(f"✅ Чек-листы успешно созданы для задачи {created_task_id}")
                            else:
                                logger.warning(f"⚠️ Не все чек-листы созданы для задачи {created_task_id}")
                        except Exception as e:
                            logger.error(f"Ошибка создания чек-листов для задачи {created_task_id}: {e}")
                            # Не прерываем выполнение, задача уже создана
                    else:
                        logger.debug(f"Нет данных чек-листов для задачи {created_task_id}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            error_result = {
                'error': 'REQUEST_ERROR',
                'error_description': f'Ошибка запроса: {str(e)}'
            }
            logger.error(f"Ошибка при отправке запроса в Bitrix24: {e}")
            
            # Если это HTTP ошибка, попробуем получить детали ответа
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details = e.response.text
                    logger.error(f"Детали ошибки от Bitrix24: {error_details}")
                    
                    # Проверяем, является ли ошибка связанной с неверным пользователем
                    if "не найден" in error_details and ("Исполнитель" in error_details or "Ответственный" in error_details):
                        logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Пользователь assigneeId не найден в Bitrix24")
                        # Возвращаем специальный результат с ошибкой для обработки в process_message
                        return {
                            'error': 'ASSIGNEE_ID_ERROR',
                            'error_description': f'Пользователь assigneeId не найден в Bitrix24: {error_details}'
                        }
                        
                except:
                    pass
            
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
    
    def _build_process_variables_block(self, message_data: Dict[str, Any], camunda_process_id: str, task_id: str) -> Optional[str]:
        """
        Формирование текстового блока значений переменных процесса для описания задачи
        """
        if not camunda_process_id:
            logger.debug(f"Пропуск построения блока переменных: отсутствует camundaProcessId для задачи {task_id}")
            return None
        
        properties = self._get_diagram_properties(camunda_process_id)
        if not properties:
            logger.debug(f"Список параметров диаграммы пуст для процесса {camunda_process_id}, задача {task_id}")
            return None
        
        metadata = message_data.get('metadata') or {}
        process_variables = {}
        if isinstance(metadata, dict):
            pv_from_metadata = metadata.get('processVariables')
            if isinstance(pv_from_metadata, dict):
                process_variables = pv_from_metadata
        
        if not process_variables:
            pv_direct = message_data.get('process_variables')
            if isinstance(pv_direct, dict):
                process_variables = pv_direct
        
        lines: List[str] = []
        
        def sort_key(prop: Dict[str, Any]) -> int:
            sort_raw = prop.get('SORT', 0)
            try:
                return int(sort_raw)
            except (TypeError, ValueError):
                return 0
        
        for prop in sorted(properties, key=sort_key):
            code = prop.get('CODE')
            name = prop.get('NAME') or code or ''
            property_type = prop.get('TYPE', '')
            
            value_entry = process_variables.get(code) if code else None
            formatted_value = self._format_process_variable_value(property_type, value_entry)
            lines.append(f"{name}: {formatted_value};")
        
        if not lines:
            logger.debug(f"Не удалось сформировать строки значений переменных процесса для задачи {task_id}")
            return None
        
        return "\n".join(lines)

    def _get_diagram_properties(self, camunda_process_id: str) -> List[Dict[str, Any]]:
        """
        Получение списка параметров диаграммы процесса через Bitrix24 REST API
        """
        if not camunda_process_id:
            return []
        
        if camunda_process_id in self.diagram_properties_cache:
            return self.diagram_properties_cache[camunda_process_id]
        
        api_url = f"{self.config.webhook_url.rstrip('/')}/imena.camunda.diagram.properties.list"
        params = {'camundaProcessId': camunda_process_id}
        
        try:
            logger.debug(f"Запрос списка параметров диаграммы: camundaProcessId={camunda_process_id}")
            response = requests.get(api_url, params=params, timeout=self.config.request_timeout)
            response.raise_for_status()
            data = response.json()
            
            result = data.get('result', {})
            if not result.get('success'):
                logger.warning(f"Bitrix24 вернул пустой список параметров для процесса {camunda_process_id}: {result.get('error')}")
                self.diagram_properties_cache[camunda_process_id] = []
                self.diagram_details_cache[camunda_process_id] = {}
                return []
            
            properties_data = result.get('data', {})
            diagram_info = properties_data.get('diagram') or {}
            self.diagram_details_cache[camunda_process_id] = diagram_info
            properties = properties_data.get('properties', [])
            if isinstance(properties, list):
                self.diagram_properties_cache[camunda_process_id] = properties
                logger.debug(f"Получено {len(properties)} параметров диаграммы для процесса {camunda_process_id}")
                return properties
            
            logger.warning(f"Неожиданный формат списка параметров для процесса {camunda_process_id}")
            self.diagram_properties_cache[camunda_process_id] = []
            if camunda_process_id not in self.diagram_details_cache:
                self.diagram_details_cache[camunda_process_id] = {}
            return []
        
        except requests.exceptions.Timeout:
            logger.error(f"Таймаут запроса параметров диаграммы (timeout={self.config.request_timeout}s) для процесса {camunda_process_id}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса параметров диаграммы для процесса {camunda_process_id}: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON ответа параметров диаграммы: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе параметров диаграммы {camunda_process_id}: {e}")
        
        self.diagram_properties_cache[camunda_process_id] = []
        self.diagram_details_cache[camunda_process_id] = {}
        return []

    def _resolve_diagram_id(
        self,
        diagram_id: Optional[str],
        camunda_process_id: Optional[str],
        metadata: Optional[Dict[str, Any]],
        template_data: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Попытка определить ID диаграммы Storm различными способами.
        """
        if diagram_id:
            resolved = str(diagram_id)
            logger.debug(f"diagramId извлечён из входных данных: {resolved}")
            return resolved

        metadata = metadata or {}
        process_properties = metadata.get('processProperties', {})
        if isinstance(process_properties, dict):
            for key in ('diagramId', 'diagram_id', 'diagramID', 'stormDiagramId'):
                value = process_properties.get(key)
                if value:
                    resolved = str(value)
                    logger.debug(f"diagramId найден в processProperties[{key}]: {resolved}")
                    return resolved

        diagram_meta = metadata.get('diagram', {})
        if isinstance(diagram_meta, dict):
            for key in ('id', 'ID'):
                value = diagram_meta.get(key)
                if value:
                    resolved = str(value)
                    logger.debug(f"diagramId найден в metadata.diagram.{key}: {resolved}")
                    return resolved

        template_meta = (template_data or {}).get('meta', {})
        if isinstance(template_meta, dict):
            for key in ('diagramId', 'diagram_id', 'diagramID'):
                value = template_meta.get(key)
                if value:
                    resolved = str(value)
                    logger.debug(f"diagramId найден в template.meta[{key}]: {resolved}")
                    return resolved

        if camunda_process_id:
            # Вызываем API параметров диаграммы, чтобы заполнить кэш
            self._get_diagram_properties(camunda_process_id)
            cached_info = self.diagram_details_cache.get(camunda_process_id) or {}
            value = cached_info.get('ID') or cached_info.get('id')
            if value:
                resolved = str(value)
                logger.debug(f"diagramId получен из кэша параметров диаграммы: {resolved}")
                return resolved

        logger.debug("diagramId не удалось определить по доступным данным")
        return None

    def _get_responsible_info(
        self,
        camunda_process_id: Optional[str],
        diagram_id: Optional[str],
        element_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Получение полной записи ответственого элемента диаграммы.
        """
        if not element_id:
            return None

        cache_key = (camunda_process_id, diagram_id, element_id)
        if cache_key in self.responsible_cache:
            return self.responsible_cache[cache_key]

        if not camunda_process_id and not diagram_id:
            logger.debug("Пропуск запроса ответственного: отсутствуют camundaProcessId и diagramId")
            self.responsible_cache[cache_key] = None
            return None

        api_url = f"{self.config.webhook_url.rstrip('/')}/imena.camunda.diagram.responsible.get"
        params = {
            'elementId': element_id
        }
        if camunda_process_id:
            params['camundaProcessId'] = camunda_process_id
        elif diagram_id:
            params['diagramId'] = diagram_id

        try:
            logger.debug(f"Запрос ответственного элемента: camundaProcessId={camunda_process_id}, diagramId={diagram_id}, elementId={element_id}")
            response = requests.get(api_url, params=params, timeout=self.config.request_timeout)
            response.raise_for_status()
            data = response.json()

            result = data.get('result', {})
            if not result.get('success'):
                logger.warning(f"Bitrix24 вернул ошибку при получении ответственного elementId={element_id}: {result.get('error')}")
                self.responsible_cache[cache_key] = None
                return None

            responsible = result.get('data', {}).get('responsible')
            if responsible:
                self.responsible_cache[cache_key] = responsible
                return responsible

            logger.debug(f"Ответственный elementId={element_id} не найден")
            self.responsible_cache[cache_key] = None
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса ответственного elementId={element_id}: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования ответа ответственного elementId={element_id}: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении ответственного elementId={element_id}: {e}")

        self.responsible_cache[cache_key] = None
        return None

    def _get_element_predecessor_ids(
        self,
        camunda_process_id: Optional[str],
        diagram_id: Optional[str],
        element_id: Optional[str],
        responsible_info: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Получение списка ID элементов-предшественников для указанного элемента диаграммы.
        """
        if not element_id:
            return []
        if not camunda_process_id and not diagram_id:
            logger.debug("Пропуск запроса предшественников: отсутствуют camundaProcessId и diagramId")
            return []

        cache_key = (camunda_process_id, diagram_id, element_id)
        if cache_key in self.element_predecessors_cache:
            return self.element_predecessors_cache[cache_key]

        if not responsible_info:
            responsible_info = self._get_responsible_info(camunda_process_id, diagram_id, element_id)

        if not responsible_info:
            self.element_predecessors_cache[cache_key] = []
            return []

        raw_predecessors = responsible_info.get('PREDECESSOR_IDS', [])
        normalized: List[str] = []

        if isinstance(raw_predecessors, list):
            normalized = [str(item).strip() for item in raw_predecessors if item]
        elif isinstance(raw_predecessors, str):
            raw_predecessors = raw_predecessors.strip()
            if raw_predecessors.startswith('['):
                try:
                    parsed = json.loads(raw_predecessors)
                    if isinstance(parsed, list):
                        normalized = [str(item).strip() for item in parsed if item]
                except json.JSONDecodeError:
                    logger.warning(f"Не удалось распарсить PREDECESSOR_IDS как JSON: {raw_predecessors}")
            elif raw_predecessors:
                normalized = [raw_predecessors]
        elif raw_predecessors:
            normalized = [str(raw_predecessors).strip()]

        normalized = [pid for pid in normalized if pid]
        if normalized:
            logger.info(f"Получено {len(normalized)} предшественников для elementId={element_id}")
        else:
            logger.debug(f"Предшественники для elementId={element_id} отсутствуют")

        self.element_predecessors_cache[cache_key] = normalized
        return normalized

    def _apply_predecessor_dependencies(
        self,
        task_data: Dict[str, Any],
        camunda_process_id: Optional[str],
        diagram_id: Optional[str],
        element_id: Optional[str],
        responsible_info: Optional[Dict[str, Any]] = None,
        process_instance_id: Optional[str] = None
    ) -> List[int]:
        """
        Добавляет сведения о задачах-предшественниках в task_data, если они найдены.
        
        Args:
            task_data: Данные задачи для модификации
            camunda_process_id: ID процесса Camunda (processDefinitionKey)
            diagram_id: ID диаграммы Storm
            element_id: ID элемента BPMN
            responsible_info: Информация об ответственном элементе
            process_instance_id: ID экземпляра процесса (для поиска предшественников в рамках одного экземпляра)
        
        Returns:
            Список ID задач-предшественников в Bitrix24
        """
        if not element_id:
            logger.debug("Пропуск добавления предшественников: отсутствует elementId")
            return []

        predecessor_elements = self._get_element_predecessor_ids(
            camunda_process_id,
            diagram_id,
            element_id,
            responsible_info=responsible_info
        )
        if not predecessor_elements:
            return []

        dependencies: List[Dict[str, Any]] = []
        missing_elements: List[str] = []
        predecessor_task_ids: List[int] = []

        for predecessor_element_id in predecessor_elements:
            existing_task = self._find_task_by_element_and_instance(predecessor_element_id, process_instance_id)
            if not existing_task:
                missing_elements.append(predecessor_element_id)
                continue

            bitrix_task_id = existing_task.get('id') or existing_task.get('ID')
            try:
                bitrix_task_int = int(bitrix_task_id)
            except (ValueError, TypeError):
                logger.warning(f"Некорректный ID задачи для предшественника {predecessor_element_id}: {bitrix_task_id}")
                continue

            dependencies.append({
                'DEPENDS_ON_ID': bitrix_task_int,
                'TYPE': 2  # Finish-Start зависимость
            })
            predecessor_task_ids.append(bitrix_task_int)

        if dependencies:
            existing = task_data.get('SE_PROJECTDEPENDENCE')
            if isinstance(existing, list):
                existing.extend(dependencies)
            elif existing:
                logger.warning("Поле SE_PROJECTDEPENDENCE имеет неожиданный формат, будет перезаписано")
                task_data['SE_PROJECTDEPENDENCE'] = dependencies
            else:
                task_data['SE_PROJECTDEPENDENCE'] = dependencies
            logger.info(f"Добавлено {len(dependencies)} предшественников для elementId={element_id}")

        if missing_elements:
            logger.warning(f"Не найдены задачи в Bitrix24 для предшественников: {missing_elements}")

        return predecessor_task_ids

    def _create_task_dependencies(self, task_id: int, predecessor_ids: List[int]) -> None:
        """
        Создание зависимостей задач через кастомный REST API Bitrix24.
        """
        if not predecessor_ids:
            return

        api_url = f"{self.config.webhook_url.rstrip('/')}/imena.camunda.task.dependency.add"
        unique_predecessors: List[int] = []
        for predecessor_id in predecessor_ids:
            if predecessor_id == task_id:
                logger.warning(f"Предшественник совпадает с текущей задачей ({task_id}), пропуск")
                continue
            if predecessor_id not in unique_predecessors:
                unique_predecessors.append(predecessor_id)

        for predecessor_id in unique_predecessors:
            payload = {
                "taskId": task_id,
                "dependsOnId": predecessor_id
            }

            try:
                self.stats["dependencies_attempted"] += 1
                response = requests.post(
                    api_url,
                    json=payload,
                    timeout=self.config.request_timeout
                )
                response.raise_for_status()
                data = response.json()

                result = data.get('result', {})
                if result.get('success'):
                    self.stats["dependencies_created"] += 1
                    logger.info(f"✅ Добавлена зависимость: задача {task_id} зависит от {predecessor_id}")
                else:
                    self.stats["dependencies_failed"] += 1
                    error_msg = result.get('error') or result.get('message') or 'unknown error'
                    logger.warning(
                        f"Не удалось добавить зависимость taskId={task_id} -> dependsOnId={predecessor_id}: {error_msg}"
                    )

            except requests.exceptions.RequestException as e:
                self.stats["dependencies_failed"] += 1
                logger.error(
                    f"Ошибка запроса при добавлении зависимости taskId={task_id} -> dependsOnId={predecessor_id}: {e}"
                )
            except json.JSONDecodeError as e:
                self.stats["dependencies_failed"] += 1
                logger.error(
                    f"Ошибка декодирования ответа при добавлении зависимости taskId={task_id}: {e}"
                )
            except Exception as e:
                self.stats["dependencies_failed"] += 1
                logger.error(
                    f"Неожиданная ошибка при добавлении зависимости taskId={task_id}: {e}"
                )

    def _get_task_results(self, task_id: int) -> List[Dict[str, Any]]:
        """
        Получение результатов задачи через API tasks.task.result.list
        и дополнительных данных о файлах через task.commentitem.get.
        
        Args:
            task_id: ID задачи в Bitrix24
            
        Returns:
            Список результатов с текстом и информацией о файлах:
            [
                {
                    'id': int,
                    'text': str,
                    'formattedText': str,
                    'createdAt': str,
                    'files': [
                        {
                            'name': str,
                            'size': int,
                            'fileId': int,
                            'attachmentId': int,
                            'downloadUrl': str
                        }
                    ]
                }
            ]
        """
        results = []
        
        try:
            # Шаг 1: Получаем результаты задачи
            result_list_url = f"{self.config.webhook_url.rstrip('/')}/tasks.task.result.list.json"
            response = requests.post(
                result_list_url,
                json={"taskId": task_id},
                timeout=self.config.request_timeout
            )
            response.raise_for_status()
            data = response.json()
            
            raw_results = data.get('result', [])
            if not raw_results:
                logger.debug(f"Нет результатов для задачи {task_id}")
                return []
            
            # Шаг 2: Для каждого результата получаем детали комментария (для файлов)
            for result_item in raw_results:
                comment_id = result_item.get('commentId')
                result_entry = {
                    'id': result_item.get('id'),
                    'text': result_item.get('text', ''),
                    'formattedText': result_item.get('formattedText', ''),
                    'createdAt': result_item.get('createdAt', ''),
                    'files': []
                }
                
                # Если есть файлы, получаем детали через task.commentitem.get
                file_ids = result_item.get('files', [])
                if file_ids and comment_id:
                    try:
                        comment_url = f"{self.config.webhook_url.rstrip('/')}/task.commentitem.get.json"
                        comment_response = requests.post(
                            comment_url,
                            json={"TASKID": task_id, "ITEMID": comment_id},
                            timeout=self.config.request_timeout
                        )
                        comment_response.raise_for_status()
                        comment_data = comment_response.json()
                        
                        attached_objects = comment_data.get('result', {}).get('ATTACHED_OBJECTS', {})
                        for attach_id, attach_info in attached_objects.items():
                            file_entry = {
                                'name': attach_info.get('NAME', f'file_{attach_id}'),
                                'size': int(attach_info.get('SIZE', 0)),
                                'fileId': int(attach_info.get('FILE_ID', 0)),
                                'attachmentId': int(attach_info.get('ATTACHMENT_ID', attach_id)),
                                'downloadUrl': attach_info.get('DOWNLOAD_URL', '')
                            }
                            result_entry['files'].append(file_entry)
                            
                    except Exception as e:
                        logger.warning(f"Ошибка получения файлов комментария {comment_id} задачи {task_id}: {e}")
                
                results.append(result_entry)
            
            self.stats["predecessor_results_fetched"] += 1
            logger.debug(f"Получено {len(results)} результатов задачи {task_id}")
            
        except requests.exceptions.RequestException as e:
            self.stats["predecessor_results_failed"] += 1
            logger.warning(f"Ошибка запроса результатов задачи {task_id}: {e}")
        except Exception as e:
            self.stats["predecessor_results_failed"] += 1
            logger.warning(f"Неожиданная ошибка получения результатов задачи {task_id}: {e}")
        
        return results

    def _get_predecessor_results(
        self, 
        predecessor_task_ids: List[int]
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        Получение результатов всех задач-предшественников.
        
        Args:
            predecessor_task_ids: Список ID задач-предшественников
            
        Returns:
            Словарь {task_id: [results]}
        """
        if not predecessor_task_ids:
            return {}
        
        predecessor_results: Dict[int, List[Dict[str, Any]]] = {}
        
        for task_id in predecessor_task_ids:
            results = self._get_task_results(task_id)
            if results:
                predecessor_results[task_id] = results
                logger.info(f"Получено {len(results)} результатов от задачи-предшественника {task_id}")
        
        return predecessor_results

    def _build_predecessor_results_block(
        self, 
        predecessor_results: Dict[int, List[Dict[str, Any]]]
    ) -> Optional[str]:
        """
        Формирование блока текста с результатами предшествующих задач.
        
        Args:
            predecessor_results: Словарь {task_id: [results]} с результатами задач
            
        Returns:
            Отформатированный блок текста или None если результатов нет
        """
        if not predecessor_results:
            return None
        
        lines = ["[B]📋 Результаты предшествующих задач:[/B]"]
        lines.append("")
        
        for task_id, results in predecessor_results.items():
            lines.append(f"[B]Задача №{task_id}:[/B]")
            
            for idx, result in enumerate(results, 1):
                # Очищаем текст от HTML-сущностей
                text = result.get('text', '') or result.get('formattedText', '')
                if text:
                    # Заменяем HTML-сущности
                    text = text.replace('&quot;', '"').replace('&amp;', '&')
                    text = text.replace('&lt;', '<').replace('&gt;', '>')
                    text = text.replace('\u00a0', ' ')  # неразрывный пробел
                    
                    if len(results) > 1:
                        lines.append(f"  {idx}. {text}")
                    else:
                        lines.append(f"  • {text}")
                
                # Если есть файлы, указываем их
                files = result.get('files', [])
                if files:
                    file_names = [f.get('name', 'файл') for f in files]
                    lines.append(f"     📎 Файлы: {', '.join(file_names)}")
            
            lines.append("")
        
        return "\n".join(lines)

    def _attach_predecessor_files(
        self, 
        task_id: int, 
        predecessor_results: Dict[int, List[Dict[str, Any]]]
    ) -> None:
        """
        Прикрепление файлов из результатов предшествующих задач к созданной задаче.
        
        Использует скачивание файлов через DOWNLOAD_URL и загрузку через disk API,
        затем прикрепление к задаче.
        
        Args:
            task_id: ID созданной задачи
            predecessor_results: Словарь с результатами предшественников
        """
        if not predecessor_results:
            return
        
        # Собираем все файлы из результатов
        all_files: List[Dict[str, Any]] = []
        for pred_task_id, results in predecessor_results.items():
            for result in results:
                for file_info in result.get('files', []):
                    file_info['source_task_id'] = pred_task_id
                    all_files.append(file_info)
        
        if not all_files:
            logger.debug(f"Нет файлов для прикрепления от предшественников к задаче {task_id}")
            return
        
        logger.info(f"Прикрепление {len(all_files)} файлов от предшественников к задаче {task_id}")
        
        # Прикрепляем файлы через FILE_ID (disk file id)
        api_url = f"{self.config.webhook_url.rstrip('/')}/tasks.task.files.attach.json"
        
        for file_info in all_files:
            file_id = file_info.get('fileId')
            file_name = file_info.get('name', 'unknown')
            source_task = file_info.get('source_task_id')
            
            if not file_id:
                logger.warning(f"Пропуск файла '{file_name}' без fileId (source_task={source_task})")
                self.stats["predecessor_files_failed"] += 1
                continue
            
            payload = {
                "taskId": task_id,
                "fileId": file_id
            }
            
            try:
                logger.debug(f"Прикрепление файла '{file_name}' (fileId={file_id}) от задачи {source_task}")
                response = requests.post(api_url, data=payload, timeout=self.config.request_timeout)
                
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    self.stats["predecessor_files_failed"] += 1
                    logger.error(f"Некорректный JSON при прикреплении файла '{file_name}': {response.text}")
                    continue
                
                if response.status_code != 200 or data.get('error'):
                    error_desc = data.get('error_description', data.get('error', 'Неизвестная ошибка'))
                    logger.warning(f"Ошибка прикрепления файла '{file_name}' к задаче {task_id}: {error_desc}")
                    self.stats["predecessor_files_failed"] += 1
                    continue
                
                self.stats["predecessor_files_attached"] += 1
                logger.info(f"✅ Файл '{file_name}' от задачи {source_task} прикреплён к задаче {task_id}")
                
            except requests.exceptions.RequestException as e:
                self.stats["predecessor_files_failed"] += 1
                logger.error(f"Ошибка запроса при прикреплении файла '{file_name}': {e}")
            except Exception as e:
                self.stats["predecessor_files_failed"] += 1
                logger.error(f"Неожиданная ошибка при прикреплении файла '{file_name}': {e}")

    def _find_task_by_element_and_instance(
        self, 
        element_id: Optional[str], 
        process_instance_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Поиск задачи в Bitrix24 по значениям пользовательских полей UF_ELEMENT_ID и UF_PROCESS_INSTANCE_ID.
        
        Поиск осуществляется по двум полям одновременно, чтобы найти задачу-предшественник
        именно в рамках того же экземпляра процесса Camunda.
        
        Args:
            element_id: ID элемента BPMN (activityId)
            process_instance_id: ID экземпляра процесса Camunda (для поиска в рамках одного экземпляра)
            
        Returns:
            Данные задачи если найдена, None если не найдена
        """
        if not element_id:
            return None

        # Ключ кэша включает оба параметра
        cache_key = (element_id, process_instance_id)
        if cache_key in self.element_task_cache:
            return self.element_task_cache[cache_key]

        try:
            url = f"{self.config.webhook_url}/tasks.task.list.json"
            
            # Формируем фильтр с учётом process_instance_id
            filter_params = {
                "UF_ELEMENT_ID": element_id
            }
            
            # Добавляем фильтр по process_instance_id если он указан
            if process_instance_id:
                filter_params["UF_PROCESS_INSTANCE_ID"] = process_instance_id
                logger.debug(f"Поиск предшественника: UF_ELEMENT_ID={element_id}, UF_PROCESS_INSTANCE_ID={process_instance_id}")
            else:
                logger.warning(f"Поиск предшественника без process_instance_id: UF_ELEMENT_ID={element_id} (может вернуть задачу из другого экземпляра процесса!)")
            
            params = {
                "filter": filter_params,
                "select": ["*", "UF_*"]
            }

            response = requests.post(url, json=params, timeout=self.config.request_timeout)
            if response.status_code != 200:
                logger.warning(f"Bitrix24 вернул статус {response.status_code} при поиске по UF_ELEMENT_ID={element_id}, UF_PROCESS_INSTANCE_ID={process_instance_id}")
                return None

            result = response.json()
            tasks = result.get('result', {}).get('tasks', [])

            if tasks:
                task = tasks[0]
                self.element_task_cache[cache_key] = task
                logger.debug(f"Найдена задача {task.get('id')} для UF_ELEMENT_ID={element_id}, UF_PROCESS_INSTANCE_ID={process_instance_id}")
                return task

            logger.debug(f"Задачи с UF_ELEMENT_ID={element_id}, UF_PROCESS_INSTANCE_ID={process_instance_id} не найдены")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса при поиске задачи по UF_ELEMENT_ID={element_id}, UF_PROCESS_INSTANCE_ID={process_instance_id}: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования ответа при поиске задачи по UF_ELEMENT_ID={element_id}: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при поиске задачи по UF_ELEMENT_ID={element_id}, UF_PROCESS_INSTANCE_ID={process_instance_id}: {e}")

        return None

    def _format_process_variable_value(self, property_type: Optional[str], value_entry: Any) -> str:
        """
        Форматирование значения переменной процесса в человекочитаемый вид
        """
        value = value_entry
        if isinstance(value_entry, dict):
            if 'value' in value_entry:
                value = value_entry.get('value')
            elif 'VALUE' in value_entry:
                value = value_entry.get('VALUE')
        
        if isinstance(value, dict) and 'value' in value:
            value = value.get('value')
        
        if value is None:
            return ""
        
        normalized_type = (property_type or '').lower()
        
        if normalized_type == 'boolean':
            bool_value: Optional[bool] = None
            if isinstance(value, bool):
                bool_value = value
            elif isinstance(value, (int, float)):
                bool_value = value != 0
            elif isinstance(value, str):
                bool_value = value.strip().lower() in {'true', '1', 'y', 'yes', 'да', 'истина'}
            
            if bool_value is None:
                return ""
            return "Да" if bool_value else "Нет"
        
        if normalized_type in {'date', 'datetime'}:
            if isinstance(value, datetime):
                return value.strftime("%d.%m.%Y")
            if isinstance(value, str):
                iso_value = value.strip()
                if not iso_value:
                    return ""
                try:
                    normalized = iso_value.replace('Z', '+00:00')
                    dt = datetime.fromisoformat(normalized)
                    return dt.strftime("%d.%m.%Y")
                except ValueError:
                    try:
                        date_part = iso_value.split('T')[0]
                        dt = datetime.strptime(date_part, "%Y-%m-%d")
                        return dt.strftime("%d.%m.%Y")
                    except ValueError:
                        return iso_value
            return str(value)
        
        if isinstance(value, list):
            return ", ".join(str(item) for item in value)
        
        return str(value)
    
    def _get_camunda_int(self, variables: Optional[Dict[str, Any]], key: str) -> Optional[int]:
        """
        Безопасно извлекает целочисленное значение переменной Camunda (raw или {"value": ...}).
        """
        if not variables or not isinstance(variables, dict):
            return None
        
        raw_value = variables.get(key)
        if raw_value is None:
            return None
        
        if isinstance(raw_value, dict):
            raw_value = raw_value.get('value', raw_value.get('VALUE'))
        
        if isinstance(raw_value, str):
            raw_value = raw_value.strip()
            if raw_value == "":
                return None
        
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            logger.warning(f"Некорректное значение переменной {key}: {raw_value}")
            return None

    def _get_camunda_datetime(self, variables: Optional[Dict[str, Any]], key: str) -> Optional[datetime]:
        """
        Безопасно извлекает datetime из переменной Camunda (ISO 8601 формат).

        Поддерживаемые форматы:
        - "2024-12-31T00:00:00" (ISO 8601 без timezone)
        - "2024-12-31" (только дата)
        - {"value": "2024-12-31T00:00:00"} (Camunda object format)

        Returns:
            datetime объект или None если значение отсутствует или некорректно
        """
        if not variables or not isinstance(variables, dict):
            return None

        raw_value = variables.get(key)
        if raw_value is None:
            return None

        # Извлечение значения из Camunda object format
        if isinstance(raw_value, dict):
            raw_value = raw_value.get('value', raw_value.get('VALUE'))

        if not isinstance(raw_value, str):
            logger.warning(f"Некорректный тип переменной {key}: ожидается строка, получено {type(raw_value)}")
            return None

        raw_value = raw_value.strip()
        if not raw_value:
            return None

        # Попытка парсинга различных форматов ISO 8601
        formats = [
            '%Y-%m-%dT%H:%M:%S',      # 2024-12-31T00:00:00
            '%Y-%m-%d %H:%M:%S',      # 2024-12-31 00:00:00
            '%Y-%m-%d',               # 2024-12-31
        ]

        for fmt in formats:
            try:
                return datetime.strptime(raw_value, fmt)
            except ValueError:
                continue

        logger.warning(f"Некорректный формат даты переменной {key}: {raw_value}")
        return None

    def _build_task_data_from_template(
        self,
        template_data: Dict[str, Any],
        message_data: Dict[str, Any],
        task_id: str,
        element_id: Optional[str] = None
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Формирование task_data из шаблона задачи
        
        Args:
            template_data: Данные шаблона из API (result.data)
            message_data: Исходные данные сообщения
            task_id: External Task ID
            element_id: BPMN elementId, используется для UF_ELEMENT_ID
            
        Returns:
            Словарь task_data для создания задачи в Bitrix24
        """
        template = template_data.get('template', {})
        template_files = template_data.get('files') or []
        members = template_data.get('members', {})
        tags = template_data.get('tags', [])
        metadata = message_data.get('metadata', {})
        process_properties = metadata.get('processProperties', {})
        variables = message_data.get('variables') or {}
        parent_task_id = self._get_camunda_int(variables, 'parentTaskId')
        diagram_owner_id = self._get_camunda_int(variables, 'diagramOwner')
        group_id_from_variables = self._get_camunda_int(variables, 'groupId')
        
        # Определение инициатора процесса: только startedBy (реальный инициатор), fallback на id=1
        started_by = variables.get('startedBy')
        
        # Используем startedBy как источник инициатора процесса
        if started_by:
            try:
                # Обработка формата Camunda переменных: {"value": ID, "type": "Long"}
                if isinstance(started_by, dict) and 'value' in started_by:
                    initiator_id = str(int(started_by['value']))
                else:
                    # Прямое значение
                    initiator_id = str(int(started_by))
                logger.debug(f"Используется startedBy={started_by} как инициатор процесса: {initiator_id}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Некорректный startedBy={started_by}: {e}, будет использовано значение по умолчанию 1")
                initiator_id = None
        else:
            logger.warning("startedBy отсутствует в переменных процесса, будет использовано значение по умолчанию 1")
            initiator_id = None
        
        # Отладочная информация о доступных данных
        logger.debug(f"Данные для формирования task_data:")
        logger.debug(f"  template.RESPONSIBLE_ID: {template.get('RESPONSIBLE_ID')}")
        logger.debug(f"  template.CREATED_BY: {template.get('CREATED_BY')}")
        logger.debug(f"  members.by_type.R: {members.get('by_type', {}).get('R', [])}")
        logger.debug(f"  startedBy: {started_by}")
        logger.debug(f"  initiator_id (используется): {initiator_id}")
        
        task_data = {}
        
        # Основные поля из шаблона
        if template.get('TITLE'):
            task_data['TITLE'] = template['TITLE']
        
        if template.get('DESCRIPTION'):
            task_data['DESCRIPTION'] = template['DESCRIPTION']
        
        # PRIORITY - строковое значение, конвертируем в int если нужно
        priority = template.get('PRIORITY')
        if priority:
            try:
                task_data['PRIORITY'] = int(priority)
            except (ValueError, TypeError):
                task_data['PRIORITY'] = self.config.default_priority
        else:
            task_data['PRIORITY'] = self.config.default_priority
        
        # GROUP_ID из шаблона
        group_id = template.get('GROUP_ID')
        if group_id:
            try:
                task_data['GROUP_ID'] = int(group_id)
            except (ValueError, TypeError):
                logger.warning(f"Некорректный GROUP_ID в шаблоне: {group_id}")
        
        if not task_data.get('GROUP_ID') and group_id_from_variables:
            task_data['GROUP_ID'] = group_id_from_variables
            logger.debug(f"GROUP_ID получен из переменной процесса groupId: {group_id_from_variables}")
        
        # CREATED_BY с fallback на originatorId и поддержкой руководителя
        # ВАЖНО: Значение 0 в шаблоне означает, что поле не заполнено
        created_by = template.get('CREATED_BY')
        created_by_use_supervisor = template.get('CREATED_BY_USE_SUPERVISOR', 'N')
        
        # Проверяем, что ID валиден (не None, не 0, не пустая строка)
        try:
            created_by_int = int(created_by) if created_by is not None else 0
            is_valid_created_by = created_by_int > 0
        except (ValueError, TypeError):
            is_valid_created_by = False
        
        if is_valid_created_by:
            try:
                task_data['CREATED_BY'] = int(created_by)
                logger.debug(f"CREATED_BY из шаблона: {task_data['CREATED_BY']}")
            except (ValueError, TypeError):
                logger.warning(f"Некорректный CREATED_BY в шаблоне: {created_by}, используем fallback")
                # Fallback: проверяем флаг USE_SUPERVISOR или используем initiatorId
                if created_by_use_supervisor == 'Y' and initiator_id:
                    try:
                        initiator_id_int = int(initiator_id)
                        supervisor_id = self._get_user_supervisor(initiator_id_int)
                        if supervisor_id:
                            task_data['CREATED_BY'] = supervisor_id
                            logger.debug(f"CREATED_BY из руководителя инициатора (initiatorId={initiator_id_int}, supervisorId={supervisor_id})")
                        else:
                            # Руководитель не найден, используем initiatorId
                            task_data['CREATED_BY'] = initiator_id_int
                            logger.debug(f"CREATED_BY из initiatorId (руководитель не найден): {task_data['CREATED_BY']}")
                    except (ValueError, TypeError):
                        task_data['CREATED_BY'] = 1
                        logger.warning(f"Некорректный initiatorId: {initiator_id}, используем значение по умолчанию 1")
                elif initiator_id:
                    try:
                        task_data['CREATED_BY'] = int(initiator_id)
                        logger.debug(f"CREATED_BY из initiatorId (startedBy): {task_data['CREATED_BY']}")
                    except (ValueError, TypeError):
                        task_data['CREATED_BY'] = 1
                        logger.warning(f"Некорректный initiatorId: {initiator_id}, используем значение по умолчанию 1")
                else:
                    task_data['CREATED_BY'] = 1
                    logger.warning("CREATED_BY не указан в шаблоне и startedBy отсутствует, используем значение по умолчанию 1")
        else:
            # CREATED_BY отсутствует или равен 0, проверяем флаг USE_SUPERVISOR или используем initiatorId
            if created_by_use_supervisor == 'Y' and initiator_id:
                try:
                    initiator_id_int = int(initiator_id)
                    supervisor_id = self._get_user_supervisor(initiator_id_int)
                    if supervisor_id:
                        task_data['CREATED_BY'] = supervisor_id
                        logger.debug(f"CREATED_BY из руководителя инициатора (CREATED_BY_USE_SUPERVISOR=Y, initiatorId={initiator_id_int}, supervisorId={supervisor_id})")
                    else:
                        # Руководитель не найден, используем initiatorId
                        task_data['CREATED_BY'] = initiator_id_int
                        logger.debug(f"CREATED_BY из initiatorId (CREATED_BY_USE_SUPERVISOR=Y, но руководитель не найден): {task_data['CREATED_BY']}")
                except (ValueError, TypeError):
                    task_data['CREATED_BY'] = 1
                    logger.warning(f"Некорректный initiatorId: {initiator_id}, используем значение по умолчанию 1")
            elif initiator_id:
                try:
                    task_data['CREATED_BY'] = int(initiator_id)
                    logger.debug(f"CREATED_BY из initiatorId (startedBy, template.CREATED_BY={created_by}): {task_data['CREATED_BY']}")
                except (ValueError, TypeError):
                    task_data['CREATED_BY'] = 1
                    logger.warning(f"Некорректный initiatorId: {initiator_id}, используем значение по умолчанию 1")
            else:
                task_data['CREATED_BY'] = 1
                logger.warning("CREATED_BY не указан в шаблоне и startedBy отсутствует, используем значение по умолчанию 1")
        
        # DEADLINE: приоритет min(deadline процесса, deadline шаблона)
        # deadline процесса - крайний срок всего процесса (ISO 8601 datetime)
        # DEADLINE_AFTER шаблона - секунды от текущего момента
        process_deadline = self._get_camunda_datetime(variables, 'deadline')
        template_deadline: Optional[datetime] = None

        deadline_after = template.get('DEADLINE_AFTER')
        if deadline_after:
            try:
                deadline_after_seconds = int(deadline_after)
                if deadline_after_seconds > 0:
                    template_deadline = datetime.now() + timedelta(seconds=deadline_after_seconds)
                    logger.debug(f"Вычислен deadline из шаблона: {template_deadline} (через {deadline_after_seconds} секунд)")
            except (ValueError, TypeError) as e:
                logger.warning(f"Некорректный DEADLINE_AFTER в шаблоне: {deadline_after}, ошибка: {e}")

        # Определение итогового DEADLINE
        final_deadline: Optional[datetime] = None
        if process_deadline and template_deadline:
            # Оба значения есть - берём минимальный
            final_deadline = min(process_deadline, template_deadline)
            logger.debug(f"DEADLINE: min(процесс={process_deadline}, шаблон={template_deadline}) = {final_deadline}")
        elif process_deadline:
            # Только deadline процесса
            final_deadline = process_deadline
            logger.debug(f"DEADLINE из переменной процесса: {final_deadline}")
        elif template_deadline:
            # Только deadline шаблона
            final_deadline = template_deadline
            logger.debug(f"DEADLINE из шаблона: {final_deadline}")

        if final_deadline:
            task_data['DEADLINE'] = final_deadline.strftime('%Y-%m-%d %H:%M:%S')
        
        # Участники из members.by_type
        members_by_type = members.get('by_type', {})
        
        # RESPONSIBLE_ID: Приоритет - members.R → template.RESPONSIBLE_ID → руководитель/startedBy → id=1
        # ВАЖНО: Значение 0 в шаблоне означает, что поле не заполнено
        responsible_use_supervisor = template.get('RESPONSIBLE_USE_SUPERVISOR', 'N')
        responsibles = members_by_type.get('R', [])
        if responsibles:
            try:
                # Берем первого ответственного из members.R
                responsible_user_id = int(responsibles[0].get('USER_ID', 0))
                # Проверяем, что ID валиден (не 0)
                if responsible_user_id and responsible_user_id > 0:
                    task_data['RESPONSIBLE_ID'] = responsible_user_id
                    logger.debug(f"RESPONSIBLE_ID из шаблона (members.R): {responsible_user_id}")
                else:
                    # USER_ID = 0 означает отсутствие значения, используем fallback
                    logger.debug(f"USER_ID в members.R = 0 (не заполнено), используем fallback")
                    raise ValueError("USER_ID равен 0")
            except (ValueError, TypeError, IndexError, KeyError) as e:
                logger.warning(f"Ошибка обработки RESPONSIBLES из шаблона: {e}")
                # Продолжаем с template.RESPONSIBLE_ID
                responsible_id = template.get('RESPONSIBLE_ID')
                # Проверяем, что ID валиден (не None, не 0, не пустая строка)
                try:
                    responsible_id_int = int(responsible_id) if responsible_id is not None else 0
                    is_valid = responsible_id_int > 0
                except (ValueError, TypeError):
                    is_valid = False
                
                if is_valid:
                    try:
                        task_data['RESPONSIBLE_ID'] = int(responsible_id)
                        logger.debug(f"RESPONSIBLE_ID из шаблона (template.RESPONSIBLE_ID): {task_data['RESPONSIBLE_ID']}")
                    except (ValueError, TypeError):
                        # Fallback: проверяем флаг USE_SUPERVISOR
                        if responsible_use_supervisor == 'Y' and initiator_id:
                            try:
                                initiator_id_int = int(initiator_id)
                                supervisor_id = self._get_user_supervisor(initiator_id_int)
                                if supervisor_id:
                                    task_data['RESPONSIBLE_ID'] = supervisor_id
                                    logger.debug(f"RESPONSIBLE_ID из руководителя инициатора (initiatorId={initiator_id_int}, supervisorId={supervisor_id})")
                                else:
                                    task_data['RESPONSIBLE_ID'] = initiator_id_int
                                    logger.debug(f"RESPONSIBLE_ID из initiatorId (руководитель не найден): {task_data['RESPONSIBLE_ID']}")
                            except (ValueError, TypeError):
                                task_data['RESPONSIBLE_ID'] = 1
                                logger.warning(f"Некорректный initiatorId: {initiator_id}, используем значение по умолчанию 1")
                        elif initiator_id:
                            try:
                                task_data['RESPONSIBLE_ID'] = int(initiator_id)
                                logger.debug(f"RESPONSIBLE_ID из initiatorId: {task_data['RESPONSIBLE_ID']}")
                            except (ValueError, TypeError):
                                task_data['RESPONSIBLE_ID'] = 1
                                logger.warning(f"Некорректный initiatorId: {initiator_id}, используем значение по умолчанию 1")
                        else:
                            task_data['RESPONSIBLE_ID'] = 1
                            logger.warning("RESPONSIBLE_ID не найден, используем значение по умолчанию 1")
                else:
                    # template.RESPONSIBLE_ID отсутствует или равен 0, проверяем флаг USE_SUPERVISOR
                    if responsible_use_supervisor == 'Y' and initiator_id:
                        try:
                            initiator_id_int = int(initiator_id)
                            supervisor_id = self._get_user_supervisor(initiator_id_int)
                            if supervisor_id:
                                task_data['RESPONSIBLE_ID'] = supervisor_id
                                logger.debug(f"RESPONSIBLE_ID из руководителя инициатора (RESPONSIBLE_USE_SUPERVISOR=Y, initiatorId={initiator_id_int}, supervisorId={supervisor_id})")
                            else:
                                task_data['RESPONSIBLE_ID'] = initiator_id_int
                                logger.debug(f"RESPONSIBLE_ID из initiatorId (RESPONSIBLE_USE_SUPERVISOR=Y, но руководитель не найден): {task_data['RESPONSIBLE_ID']}")
                        except (ValueError, TypeError):
                            task_data['RESPONSIBLE_ID'] = 1
                            logger.warning(f"Некорректный initiatorId: {initiator_id}, используем значение по умолчанию 1")
                    elif initiator_id:
                        try:
                            task_data['RESPONSIBLE_ID'] = int(initiator_id)
                            logger.debug(f"RESPONSIBLE_ID из initiatorId (template.RESPONSIBLE_ID={responsible_id}): {task_data['RESPONSIBLE_ID']}")
                        except (ValueError, TypeError):
                            task_data['RESPONSIBLE_ID'] = 1
                            logger.warning(f"Некорректный initiatorId: {initiator_id}, используем значение по умолчанию 1")
                    else:
                        task_data['RESPONSIBLE_ID'] = 1
                        logger.warning("RESPONSIBLE_ID не найден, используем значение по умолчанию 1")
        else:
            # Нет members.R, используем template.RESPONSIBLE_ID
            responsible_id = template.get('RESPONSIBLE_ID')
            # Проверяем, что ID валиден (не None, не 0, не пустая строка)
            try:
                responsible_id_int = int(responsible_id) if responsible_id is not None else 0
                is_valid = responsible_id_int > 0
            except (ValueError, TypeError):
                is_valid = False
            
            if is_valid:
                try:
                    task_data['RESPONSIBLE_ID'] = int(responsible_id)
                    logger.debug(f"RESPONSIBLE_ID из шаблона (template.RESPONSIBLE_ID): {task_data['RESPONSIBLE_ID']}")
                except (ValueError, TypeError):
                    # Fallback: проверяем флаг USE_SUPERVISOR
                    if responsible_use_supervisor == 'Y' and initiator_id:
                        try:
                            initiator_id_int = int(initiator_id)
                            supervisor_id = self._get_user_supervisor(initiator_id_int)
                            if supervisor_id:
                                task_data['RESPONSIBLE_ID'] = supervisor_id
                                logger.debug(f"RESPONSIBLE_ID из руководителя инициатора (initiatorId={initiator_id_int}, supervisorId={supervisor_id})")
                            else:
                                task_data['RESPONSIBLE_ID'] = initiator_id_int
                                logger.debug(f"RESPONSIBLE_ID из initiatorId (руководитель не найден): {task_data['RESPONSIBLE_ID']}")
                        except (ValueError, TypeError):
                            task_data['RESPONSIBLE_ID'] = 1
                            logger.warning(f"Некорректный initiatorId: {initiator_id}, используем значение по умолчанию 1")
                    elif initiator_id:
                        try:
                            task_data['RESPONSIBLE_ID'] = int(initiator_id)
                            logger.debug(f"RESPONSIBLE_ID из initiatorId: {task_data['RESPONSIBLE_ID']}")
                        except (ValueError, TypeError):
                            task_data['RESPONSIBLE_ID'] = 1
                            logger.warning(f"Некорректный initiatorId: {initiator_id}, используем значение по умолчанию 1")
                    else:
                        task_data['RESPONSIBLE_ID'] = 1
                        logger.warning("RESPONSIBLE_ID не указан в шаблоне и initiatorId отсутствует, используем значение по умолчанию 1")
            else:
                # template.RESPONSIBLE_ID отсутствует или равен 0, проверяем флаг USE_SUPERVISOR
                if responsible_use_supervisor == 'Y' and initiator_id:
                    try:
                        initiator_id_int = int(initiator_id)
                        supervisor_id = self._get_user_supervisor(initiator_id_int)
                        if supervisor_id:
                            task_data['RESPONSIBLE_ID'] = supervisor_id
                            logger.debug(f"RESPONSIBLE_ID из руководителя инициатора (RESPONSIBLE_USE_SUPERVISOR=Y, initiatorId={initiator_id_int}, supervisorId={supervisor_id})")
                        else:
                            task_data['RESPONSIBLE_ID'] = initiator_id_int
                            logger.debug(f"RESPONSIBLE_ID из initiatorId (RESPONSIBLE_USE_SUPERVISOR=Y, но руководитель не найден): {task_data['RESPONSIBLE_ID']}")
                    except (ValueError, TypeError):
                        task_data['RESPONSIBLE_ID'] = 1
                        logger.warning(f"Некорректный initiatorId: {initiator_id}, используем значение по умолчанию 1")
                elif initiator_id:
                    try:
                        task_data['RESPONSIBLE_ID'] = int(initiator_id)
                        logger.debug(f"RESPONSIBLE_ID из initiatorId (template.RESPONSIBLE_ID={responsible_id}): {task_data['RESPONSIBLE_ID']}")
                    except (ValueError, TypeError):
                        task_data['RESPONSIBLE_ID'] = 1
                        logger.warning(f"Некорректный initiatorId: {initiator_id}, используем значение по умолчанию 1")
                else:
                    task_data['RESPONSIBLE_ID'] = 1
                    logger.warning("RESPONSIBLE_ID не указан в шаблоне и initiatorId отсутствует, используем значение по умолчанию 1")
        
        # ACCOMPLICES (A) - список всех соисполнителей
        accomplices = members_by_type.get('A', [])
        accomplice_ids = []
        
        if accomplices:
            try:
                accomplice_ids = [int(m.get('USER_ID')) for m in accomplices if m.get('USER_ID')]
                if accomplice_ids:
                    task_data['ACCOMPLICES'] = accomplice_ids
                    logger.debug(f"ACCOMPLICES из шаблона: {accomplice_ids}")
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Ошибка обработки ACCOMPLICES из шаблона: {e}")
        
        # Проверяем флаг RESPONSIBLES_USE_SUPERVISOR для добавления руководителя
        responsibles_use_supervisor = template.get('RESPONSIBLES_USE_SUPERVISOR', 'N')
        if responsibles_use_supervisor == 'Y' and initiator_id:
            try:
                initiator_id_int = int(initiator_id)
                supervisor_id = self._get_user_supervisor(initiator_id_int)
                if supervisor_id:
                    # Инициализируем список, если его еще нет
                    if 'ACCOMPLICES' not in task_data:
                        task_data['ACCOMPLICES'] = []
                    elif not isinstance(task_data['ACCOMPLICES'], list):
                        task_data['ACCOMPLICES'] = [task_data['ACCOMPLICES']] if task_data['ACCOMPLICES'] else []
                    
                    # Добавляем руководителя, если его еще нет в списке
                    if supervisor_id not in task_data['ACCOMPLICES']:
                        task_data['ACCOMPLICES'].append(supervisor_id)
                        logger.debug(f"Добавлен руководитель к ACCOMPLICES (RESPONSIBLES_USE_SUPERVISOR=Y, supervisorId={supervisor_id}): {task_data['ACCOMPLICES']}")
                    else:
                        logger.debug(f"Руководитель уже в списке ACCOMPLICES (supervisorId={supervisor_id})")
                else:
                    logger.debug(f"Руководитель не найден для добавления в ACCOMPLICES (initiatorId={initiator_id_int})")
            except (ValueError, TypeError) as e:
                logger.warning(f"Ошибка при добавлении руководителя в ACCOMPLICES: {e}")
        
        # AUDITORS (U) - список всех наблюдателей
        auditors = members_by_type.get('U', [])
        auditor_ids = []
        
        if auditors:
            try:
                auditor_ids = [int(m.get('USER_ID')) for m in auditors if m.get('USER_ID')]
                if auditor_ids:
                    task_data['AUDITORS'] = auditor_ids
                    logger.debug(f"AUDITORS из шаблона: {auditor_ids}")
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Ошибка обработки AUDITORS из шаблона: {e}")
        
        # Проверяем флаг AUDITORS_USE_SUPERVISOR для добавления руководителя
        auditors_use_supervisor = template.get('AUDITORS_USE_SUPERVISOR', 'N')
        if auditors_use_supervisor == 'Y' and initiator_id:
            try:
                initiator_id_int = int(initiator_id)
                supervisor_id = self._get_user_supervisor(initiator_id_int)
                if supervisor_id:
                    # Инициализируем список, если его еще нет
                    if 'AUDITORS' not in task_data:
                        task_data['AUDITORS'] = []
                    elif not isinstance(task_data['AUDITORS'], list):
                        task_data['AUDITORS'] = [task_data['AUDITORS']] if task_data['AUDITORS'] else []
                    
                    # Добавляем руководителя, если его еще нет в списке
                    if supervisor_id not in task_data['AUDITORS']:
                        task_data['AUDITORS'].append(supervisor_id)
                        logger.debug(f"Добавлен руководитель к AUDITORS (AUDITORS_USE_SUPERVISOR=Y, supervisorId={supervisor_id}): {task_data['AUDITORS']}")
                    else:
                        logger.debug(f"Руководитель уже в списке AUDITORS (supervisorId={supervisor_id})")
                else:
                    logger.debug(f"Руководитель не найден для добавления в AUDITORS (initiatorId={initiator_id_int})")
            except (ValueError, TypeError) as e:
                logger.warning(f"Ошибка при добавлении руководителя в AUDITORS: {e}")

        existing_auditors = task_data.get('AUDITORS')
        has_auditors = bool(existing_auditors)
        if isinstance(existing_auditors, list):
            has_auditors = len(existing_auditors) > 0

        if diagram_owner_id and not has_auditors:
            task_data['AUDITORS'] = [diagram_owner_id]
            logger.debug(f"AUDITORS получены из переменной процесса diagramOwner: {diagram_owner_id}")
        
        # Теги из tags
        if tags:
            try:
                tag_names = [tag.get('NAME') for tag in tags if tag.get('NAME')]
                if tag_names:
                    task_data['TAGS'] = ', '.join(tag_names)
                    logger.debug(f"TAGS из шаблона: {task_data['TAGS']}")
            except (TypeError, KeyError, AttributeError) as e:
                logger.warning(f"Ошибка обработки тегов из шаблона: {e}")
        
        # Всегда добавляем UF_CAMUNDA_ID_EXTERNAL_TASK
        task_data['UF_CAMUNDA_ID_EXTERNAL_TASK'] = task_id
        
        # Извлекаем и добавляем пользовательские поля из метаданных сообщения
        # (UF_RESULT_EXPECTED, UF_RESULT_QUESTION и другие)
        user_fields = self._extract_user_fields(metadata)
        if user_fields:
            task_data.update(user_fields)
            logger.debug(f"Добавлены пользовательские поля из метаданных: {list(user_fields.keys())}")

        if parent_task_id:
            task_data['PARENT_ID'] = parent_task_id
            task_data['SUBORDINATE'] = 'Y'
            logger.debug(f"Установлены родительская задача {parent_task_id} и признак подзадачи")

        if element_id:
            task_data['UF_ELEMENT_ID'] = element_id
            logger.debug(f"Добавлено пользовательское поле UF_ELEMENT_ID={element_id} для задачи {task_id}")
        
        # UF_PROCESS_INSTANCE_ID - идентификатор экземпляра процесса Camunda
        # Необходим для поиска предшественников в рамках одного экземпляра процесса
        process_instance_id = message_data.get('processInstanceId') or message_data.get('process_instance_id')
        if process_instance_id:
            task_data['UF_PROCESS_INSTANCE_ID'] = str(process_instance_id)
            logger.debug(f"Добавлено пользовательское поле UF_PROCESS_INSTANCE_ID={process_instance_id} для задачи {task_id}")
        else:
            logger.warning(f"processInstanceId не найден в message_data для задачи {task_id}, UF_PROCESS_INSTANCE_ID не будет установлен")
        
        # Логирование финальных значений для отладки
        logger.debug(f"Формирование task_data из шаблона (templateId={template_data.get('meta', {}).get('templateId', 'N/A')}):")
        logger.debug(f"  TITLE: {task_data.get('TITLE', 'N/A')}")
        logger.debug(f"  RESPONSIBLE_ID: {task_data.get('RESPONSIBLE_ID', 'НЕ УСТАНОВЛЕН')}")
        logger.debug(f"  CREATED_BY: {task_data.get('CREATED_BY', 'НЕ УСТАНОВЛЕН')}")
        logger.debug(f"  GROUP_ID: {task_data.get('GROUP_ID', 'НЕ УСТАНОВЛЕН')}")
        logger.debug(f"  PRIORITY: {task_data.get('PRIORITY', 'N/A')}")
        logger.debug(f"  DEADLINE: {task_data.get('DEADLINE', 'НЕ УСТАНОВЛЕН')}")
        logger.debug(f"  ACCOMPLICES: {task_data.get('ACCOMPLICES', [])}")
        logger.debug(f"  AUDITORS: {task_data.get('AUDITORS', [])}")
        logger.debug(f"  TAGS: {task_data.get('TAGS', 'НЕТ')}")
        logger.debug(f"  Пользовательские поля: {list(user_fields.keys()) if user_fields else 'НЕТ'}")
        
        return task_data, template_files

    def _build_template_files_block(self, files: List[Dict[str, Any]]) -> Optional[str]:
        """
        Формирование текстового блока с ссылками на файлы шаблона.
        """
        if not files:
            return None
        
        base_url = self.config.webhook_url.split('/rest/')[0].rstrip('/')
        lines: List[str] = ["Файлы из шаблона:"]
        for index, file_entry in enumerate(files, start=1):
            name = file_entry.get('NAME') or f"Файл {index}"
            relative_url = file_entry.get('URL')
            if not relative_url:
                lines.append(f"{index}. {name}")
                continue
            full_url = f"{base_url}{relative_url}"
            lines.append(f"{index}. {name}: {full_url}")
        
        return "\n".join(lines)

    def _attach_files_to_task(self, task_id: int, files: List[Dict[str, Any]]) -> None:
        """
        Прикрепление файлов из шаблона к созданной задаче Bitrix24 через tasks.task.files.attach.
        
        Использует метод tasks.task.files.attach для прикрепления файлов диска к задаче.
        Параметры:
        - taskId: ID задачи
        - fileId: ID файла из диска (OBJECT_ID из шаблона)
        """
        if not files:
            logger.debug(f"Нет файлов для прикрепления к задаче {task_id}")
            return
        
        api_url = f"{self.config.webhook_url.rstrip('/')}/tasks.task.files.attach.json"
        
        for file_entry in files:
            object_id = file_entry.get('OBJECT_ID')
            attached_id = file_entry.get('ID')
            file_name = file_entry.get('NAME') or f"object_{object_id}"
            
            if not object_id:
                logger.warning(f"Пропуск файла без OBJECT_ID в шаблоне (task_id={task_id}, file={file_entry})")
                self.stats["template_files_failed"] += 1
                continue
            
            payload = {
                "taskId": task_id,
                "fileId": object_id
            }
            
            try:
                logger.info(f"Прикрепление файла '{file_name}' (OBJECT_ID={object_id}, attachedId={attached_id}) к задаче {task_id}")
                response = requests.post(api_url, data=payload, timeout=self.config.request_timeout)
                
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    self.stats["template_files_failed"] += 1
                    logger.error(f"Некорректный JSON ответ при прикреплении файла '{file_name}' к задаче {task_id}: {response.text}")
                    continue
                
                if response.status_code != 200 or data.get('error'):
                    error_code = data.get('error')
                    error_desc = data.get('error_description', data.get('error', 'Неизвестная ошибка'))
                    logger.warning(f"Bitrix24 вернул ошибку при прикреплении файла '{file_name}' к задаче {task_id}: {error_desc}")
                    self.stats["template_files_failed"] += 1
                    continue
                
                self.stats["template_files_attached"] += 1
                logger.info(f"✅ Файл '{file_name}' успешно прикреплён к задаче {task_id}")
                
            except requests.exceptions.RequestException as e:
                self.stats["template_files_failed"] += 1
                logger.error(f"Ошибка запроса при прикреплении файла '{file_name}' к задаче {task_id}: {e}")
            except Exception as e:
                self.stats["template_files_failed"] += 1
                logger.error(f"Неожиданная ошибка при прикреплении файла '{file_name}' к задаче {task_id}: {e}")
    
    def _create_task_fallback(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Создание задачи с минимальными данными (fallback при отсутствии шаблона)
        
        Args:
            message_data: Данные сообщения из RabbitMQ
            
        Returns:
            Ответ от API Bitrix24
        """
        try:
            task_id = message_data.get('task_id', 'unknown')
            metadata = message_data.get('metadata', {})
            camunda_process_id, element_id, diagram_id = self._extract_template_params(message_data)
            responsible_info = self._get_responsible_info(camunda_process_id, diagram_id, element_id)
            diagram_id_from_responsible = None
            if responsible_info:
                diagram_id_from_responsible = (
                    responsible_info.get('DIAGRAM_ID') or
                    responsible_info.get('diagramId')
                )
            diagram_id = self._resolve_diagram_id(
                diagram_id,
                camunda_process_id,
                metadata,
                None
            )
            if not diagram_id and diagram_id_from_responsible:
                diagram_id = diagram_id_from_responsible
            activity_info = metadata.get('activityInfo', {})
            variables = message_data.get('variables') or {}
            parent_task_id = self._get_camunda_int(variables, 'parentTaskId')
            diagram_owner_id = self._get_camunda_int(variables, 'diagramOwner')
            group_id_from_variables = self._get_camunda_int(variables, 'groupId')
            started_by = variables.get('startedBy')
            
            # TITLE из activityInfo.name или fallback
            title = activity_info.get('name')
            if not title:
                topic = message_data.get('topic', 'unknown')
                title = f'Задача из Camunda процесса ({topic})'
            
            # DESCRIPTION - пустое или дубликат TITLE
            description = title
            variables_block = self._build_process_variables_block(message_data, camunda_process_id, task_id)
            if variables_block:
                description = f"{description.rstrip()}\n\n---\n{variables_block}" if description else variables_block
            
            # CREATED_BY и RESPONSIBLE_ID из startedBy (если доступен), иначе id=1
            created_by = 1
            responsible_id = 1
            if started_by:
                try:
                    # Обработка формата Camunda переменных: {"value": ID, "type": "Long"}
                    if isinstance(started_by, dict) and 'value' in started_by:
                        initiator_id_int = int(started_by['value'])
                    else:
                        # Прямое значение
                        initiator_id_int = int(started_by)
                    created_by = initiator_id_int
                    responsible_id = initiator_id_int
                    logger.debug(f"Fallback: используем startedBy={started_by} как CREATED_BY и RESPONSIBLE_ID: {initiator_id_int}")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Некорректный startedBy: {started_by}, используем значение по умолчанию 1: {e}")
            
            task_data = {
                'TITLE': title,
                'DESCRIPTION': description,
                'RESPONSIBLE_ID': responsible_id,
                'PRIORITY': self.config.default_priority,
                'CREATED_BY': created_by,
                'UF_CAMUNDA_ID_EXTERNAL_TASK': task_id
            }
            
            if group_id_from_variables:
                task_data['GROUP_ID'] = group_id_from_variables
                logger.debug(f"Fallback: GROUP_ID получен из переменной процесса groupId={group_id_from_variables}")
            
            if parent_task_id:
                task_data['PARENT_ID'] = parent_task_id
                task_data['SUBORDINATE'] = 'Y'
                logger.debug(f"Fallback: задача помечена как подзадача родителя {parent_task_id}")

            # DEADLINE из переменной процесса (в fallback режиме нет шаблона)
            process_deadline = self._get_camunda_datetime(variables, 'deadline')
            if process_deadline:
                task_data['DEADLINE'] = process_deadline.strftime('%Y-%m-%d %H:%M:%S')
                logger.debug(f"Fallback: DEADLINE из переменной процесса: {task_data['DEADLINE']}")

            # Извлекаем и добавляем пользовательские поля из метаданных сообщения
            # (UF_RESULT_EXPECTED, UF_RESULT_QUESTION и другие)
            user_fields = self._extract_user_fields(metadata)
            if user_fields:
                task_data.update(user_fields)
                logger.debug(f"Добавлены пользовательские поля из метаданных (fallback): {list(user_fields.keys())}")

            if element_id:
                task_data['UF_ELEMENT_ID'] = element_id
                logger.debug(f"Fallback: установлено пользовательское поле UF_ELEMENT_ID={element_id}")

            # UF_PROCESS_INSTANCE_ID - идентификатор экземпляра процесса Camunda
            process_instance_id = message_data.get('processInstanceId') or message_data.get('process_instance_id')
            if process_instance_id:
                task_data['UF_PROCESS_INSTANCE_ID'] = str(process_instance_id)
                logger.debug(f"Fallback: установлено пользовательское поле UF_PROCESS_INSTANCE_ID={process_instance_id}")
            else:
                logger.warning(f"Fallback: processInstanceId не найден в message_data для задачи {task_id}")

            if diagram_owner_id:
                task_data['AUDITORS'] = [diagram_owner_id]
                logger.debug(f"Fallback: AUDITORS получены из переменной diagramOwner={diagram_owner_id}")
            
            logger.warning(f"Создание задачи в fallback режиме: TITLE={title}, RESPONSIBLE_ID={responsible_id}, CREATED_BY={created_by}")

            predecessor_task_ids = self._apply_predecessor_dependencies(
                task_data,
                camunda_process_id,
                diagram_id,
                element_id,
                responsible_info=responsible_info,
                process_instance_id=process_instance_id
            )
            
            # Получение и добавление результатов предшествующих задач (fallback)
            predecessor_results: Dict[int, List[Dict[str, Any]]] = {}
            if predecessor_task_ids:
                predecessor_results = self._get_predecessor_results(predecessor_task_ids)
                if predecessor_results:
                    results_block = self._build_predecessor_results_block(predecessor_results)
                    if results_block:
                        current_description = task_data.get('DESCRIPTION', '') or ''
                        if current_description:
                            task_data['DESCRIPTION'] = f"{current_description.rstrip()}\n\n---\n{results_block}"
                        else:
                            task_data['DESCRIPTION'] = results_block
                        logger.debug(f"Fallback: Добавлен блок результатов предшественников")
            
            result = self._send_task_to_bitrix(task_data)

            if result and result.get('result') and result['result'].get('task'):
                created_task_id = result['result']['task'].get('id')
                if created_task_id:
                    try:
                        self._create_task_dependencies(int(created_task_id), predecessor_task_ids)
                    except Exception as e:
                        logger.error(f"Ошибка создания зависимостей (fallback) для задачи {created_task_id}: {e}")
                    
                    # Прикрепление файлов из результатов предшествующих задач (fallback)
                    if predecessor_results:
                        try:
                            self._attach_predecessor_files(int(created_task_id), predecessor_results)
                        except Exception as e:
                            logger.error(f"Ошибка прикрепления файлов предшественников (fallback) к задаче {created_task_id}: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка создания задачи в fallback режиме: {e}")
            return {
                'error': 'FALLBACK_ERROR',
                'error_description': f'Ошибка создания задачи в fallback режиме: {str(e)}'
            }
    
    def _send_task_to_bitrix(self, task_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Отправка задачи в Bitrix24
        
        Args:
            task_data: Данные задачи для создания
            
        Returns:
            Ответ от API Bitrix24
        """
        try:
            # Валидация обязательных полей перед отправкой
            responsible_id = task_data.get('RESPONSIBLE_ID')
            # Проверяем, что RESPONSIBLE_ID установлен И валиден (не None, не 0)
            if responsible_id is None or responsible_id == 0:
                error_msg = f"RESPONSIBLE_ID не установлен или невалиден в task_data (значение: {responsible_id})"
                logger.error(f"Валидация перед отправкой: {error_msg}")
                logger.error(f"task_data: {json.dumps(task_data, ensure_ascii=False, indent=2)}")
                return {
                    'error': 'VALIDATION_ERROR',
                    'error_description': error_msg
                }
            
            # Добавляем SE_PARAMETER для всех задач:
            # CODE=3, VALUE='Y' — "Не завершать задачу без результата"
            # Это гарантирует, что задачи из Camunda требуют явного результата при закрытии
            if 'SE_PARAMETER' not in task_data:
                task_data['SE_PARAMETER'] = []
            
            # Проверяем, не установлен ли уже параметр CODE=3
            existing_codes = {p.get('CODE') for p in task_data.get('SE_PARAMETER', []) if isinstance(p, dict)}
            if 3 not in existing_codes:
                task_data['SE_PARAMETER'].append({'CODE': 3, 'VALUE': 'Y'})
                logger.debug("Добавлен параметр SE_PARAMETER: CODE=3 (PARAM_RESULT_REQUIRED), VALUE='Y'")
            
            payload = {'fields': task_data}
            
            logger.info(f"Отправка задачи в Bitrix24: TITLE={task_data.get('TITLE')}, RESPONSIBLE_ID={task_data.get('RESPONSIBLE_ID')}")
            logger.debug(f"Полные данные задачи: {json.dumps(task_data, ensure_ascii=False, indent=2)}")
            logger.debug(f"URL запроса: {self.task_add_url}")
            
            response = requests.post(
                self.task_add_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=self.config.request_timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get('error'):
                logger.error(f"Ошибка API Bitrix24: {result['error']}")
                logger.error(f"Описание ошибки: {result.get('error_description', 'Не указано')}")
                
                # Специальная обработка ошибки "Исполнитель не найден"
                if "Исполнитель" in str(result.get('error_description', '')) and "не найден" in str(result.get('error_description', '')):
                    logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА: RESPONSIBLE_ID={task_data.get('RESPONSIBLE_ID')} не найден в Bitrix24")
                    logger.critical(f"Проверьте, существует ли пользователь с ID={task_data.get('RESPONSIBLE_ID')} в Bitrix24")
                
                return result
            
            return result
            
        except requests.exceptions.RequestException as e:
            error_result = {
                'error': 'REQUEST_ERROR',
                'error_description': f'Ошибка запроса: {str(e)}'
            }
            logger.error(f"Ошибка при отправке запроса в Bitrix24: {e}")
            
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details = e.response.text
                    logger.error(f"Детали ошибки от Bitrix24: {error_details}")
                except:
                    pass
            
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
    
    def _extract_checklists_from_template(self, template_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Извлечение чек-листов из шаблона и преобразование в формат для create_task_checklists_sync()
        
        Args:
            template_data: Данные шаблона из API (result.data)
            
        Returns:
            Список чек-листов в формате [{"name": "...", "items": ["...", "..."]}, ...]
        """
        checklists = template_data.get('checklists', {})
        items = checklists.get('items', [])
        
        if not items:
            logger.debug("Нет элементов чек-листов в шаблоне")
            return []
        
        # Группируем элементы по родительским элементам (уровень 0)
        checklist_groups = {}
        
        # Первый проход: определяем корневые элементы (группы чек-листов)
        for item_data in items:
            item = item_data.get('item', {})
            tree = item_data.get('tree', {})
            
            title = item.get('TITLE', '')
            if not title:
                continue
            
            # Приводим ID к строке для консистентности
            item_id = str(item.get('ID'))
            parent_id = tree.get('parent_id')
            # Приводим parent_id к строке, если он не None
            parent_id_str = str(parent_id) if parent_id is not None else None
            level = tree.get('level', 0)
            
            # Если это корневой элемент (level == 0)
            # В древовидной структуре parent_id корневого элемента равен самому item_id
            if level == 0:
                # Это группа чек-листа
                checklist_groups[item_id] = {
                    'name': title,
                    'items': []
                }
                logger.debug(f"Найдена группа чек-листа: ID={item_id}, name='{title}'")
        
        # Второй проход: собираем дочерние элементы для каждой группы
        for item_data in items:
            item = item_data.get('item', {})
            tree = item_data.get('tree', {})
            
            title = item.get('TITLE', '')
            if not title:
                continue
            
            item_id = str(item.get('ID'))
            parent_id = tree.get('parent_id')
            parent_id_str = str(parent_id) if parent_id is not None else None
            level = tree.get('level', 0)
            
            # Если это дочерний элемент (level > 0)
            if level > 0 and parent_id_str and parent_id_str in checklist_groups:
                # Добавляем элемент в соответствующую группу
                checklist_groups[parent_id_str]['items'].append(title)
                logger.debug(f"Добавлен элемент '{title}' в группу {parent_id_str}")
        
        # Преобразуем в список
        result = list(checklist_groups.values())
        
        # Логируем детальную информацию о каждом чек-листе
        logger.info(f"Извлечено {len(result)} чек-листов из шаблона:")
        for i, checklist in enumerate(result, 1):
            logger.info(f"  Чек-лист {i}: name='{checklist.get('name')}', items={len(checklist.get('items', []))} шт.")
            for j, item in enumerate(checklist.get('items', []), 1):
                logger.debug(f"    - {j}. {item}")
        
        return result

    def _extract_questionnaires_from_template(self, template_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Извлечение анкет из шаблона задачи (questionnaires.items)
        """
        if not template_data:
            return []
        
        questionnaires_section = template_data.get('questionnaires') or {}
        if not isinstance(questionnaires_section, dict):
            logger.debug("Секция questionnaires имеет некорректный формат (ожидался dict)")
            return []
        
        # Логируем вспомогательные поля v2.3 (total, has_codes), если они присутствуют
        total = questionnaires_section.get('total')
        has_codes = questionnaires_section.get('has_codes')
        if isinstance(total, int):
            logger.debug(f"questionnaires.total из шаблона: {total}")
        if isinstance(has_codes, bool):
            logger.debug(f"questionnaires.has_codes: {has_codes}")
        
        items = questionnaires_section.get('items')
        if not items:
            logger.debug("Секция questionnaires отсутствует или items пустой")
            return []
        
        if not isinstance(items, list):
            logger.debug("questionnaires.items имеет некорректный формат (ожидался list)")
            return []
        
        # Лёгкая валидация: CODE у анкеты и вопросов — обязательный в v2.3, но не модифицируем данные
        missing_questionnaire_codes = sum(1 for q in items if isinstance(q, dict) and not q.get('CODE'))
        missing_question_codes = 0
        for q in items:
            if not isinstance(q, dict):
                continue
            questions = q.get('questions') or []
            if isinstance(questions, list):
                missing_question_codes += sum(1 for question in questions if isinstance(question, dict) and not question.get('CODE'))
        if missing_questionnaire_codes or missing_question_codes:
            logger.warning(
                f"Анкеты из шаблона содержат пустые CODE: анкеты={missing_questionnaire_codes}, вопросы={missing_question_codes}"
            )
        
        self.stats["questionnaires_found"] += len(items)
        logger.debug(f"Извлечено {len(items)} анкет из шаблона")
        return items

    def _add_questionnaires_to_task(self, task_id: int, questionnaires: List[Dict[str, Any]]) -> bool:
        """
        Добавление анкет к созданной задаче через кастомный REST API Bitrix24
        """
        if not questionnaires:
            logger.debug("Нет анкет для добавления в задачу")
            return True
        
        api_url = f"{self.config.webhook_url.rstrip('/')}/imena.camunda.task.questionnaire.add"
        
        # Краткий лог: сколько анкет и их коды (если есть)
        sample_codes = []
        for q in questionnaires:
            if isinstance(q, dict) and 'CODE' in q:
                sample_codes.append(q.get('CODE'))
                if len(sample_codes) >= 5:
                    break
        logger.debug(
            f"Подготовка к добавлению анкет в задачу {task_id}: всего={len(questionnaires)}, пример CODE={sample_codes}"
        )
        
        payload = {
            "taskId": task_id,
            "questionnaires": questionnaires
        }
        
        try:
            response = requests.post(
                api_url,
                json=payload,
                timeout=self.config.request_timeout,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            result = response.json()
            
            api_result = result.get('result', {})
            if api_result.get('success'):
                created_ids = api_result.get('data', {}).get('createdIds', [])
                created_count = api_result.get('data', {}).get('totalCreated')
                if created_count is None:
                    created_count = len(created_ids) if created_ids else len(questionnaires)
                self.stats["questionnaires_sent"] += int(created_count)
                logger.debug(f"Анкеты добавлены в задачу {task_id}: created_count={created_count}")
                return True
            
            error_msg = api_result.get('error', 'Unknown error')
            self.stats["questionnaires_failed"] += 1
            logger.warning(f"Bitrix24 вернул ошибку при добавлении анкет в задачу {task_id}: {error_msg}")
            logger.debug(f"Полный ответ API анкет: {json.dumps(api_result, ensure_ascii=False)}")
            return False
        
        except requests.exceptions.Timeout:
            self.stats["questionnaires_failed"] += 1
            logger.error(f"Таймаут при добавлении анкет к задаче {task_id} (timeout={self.config.request_timeout}s)")
            return False
        except requests.exceptions.RequestException as e:
            self.stats["questionnaires_failed"] += 1
            logger.error(f"Ошибка запроса при добавлении анкет к задаче {task_id}: {e}")
            try:
                if getattr(e, "response", None) is not None and e.response is not None:
                    logger.error(f"Тело ответа Bitrix24 при ошибке анкет: {e.response.text}")
            except Exception:
                pass
            return False
        except json.JSONDecodeError as e:
            self.stats["questionnaires_failed"] += 1
            logger.error(f"Ошибка декодирования ответа при добавлении анкет к задаче {task_id}: {e}")
            return False
        except Exception as e:
            self.stats["questionnaires_failed"] += 1
            logger.error(f"Неожиданная ошибка при добавлении анкет к задаче {task_id}: {e}")
            return False

    def _extract_questionnaires_in_description(self, template_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Извлечение анкет для вставки в описание задачи (questionnairesInDescription.items)

        Args:
            template_data: Данные шаблона от API imena.camunda.tasktemplate.get

        Returns:
            Список анкет с вопросами для вставки в описание
        """
        if not template_data:
            return []

        qid_section = template_data.get('questionnairesInDescription') or {}
        if not isinstance(qid_section, dict):
            logger.debug("Секция questionnairesInDescription имеет некорректный формат (ожидался dict)")
            return []

        total = qid_section.get('total', 0)
        if not total:
            logger.debug("questionnairesInDescription.total = 0, анкеты для описания отсутствуют")
            return []

        items = qid_section.get('items')
        if not items:
            logger.debug("questionnairesInDescription.items пустой или отсутствует")
            return []

        if not isinstance(items, list):
            logger.debug("questionnairesInDescription.items имеет некорректный формат (ожидался list)")
            return []

        logger.debug(f"Извлечено {len(items)} анкет для вставки в описание задачи")
        return items

    def _get_user_name_by_id(self, user_id: int) -> Optional[str]:
        """
        Получение имени пользователя Bitrix24 по ID через REST API user.get

        Args:
            user_id: ID пользователя Bitrix24

        Returns:
            Имя пользователя (Фамилия Имя) или None при ошибке
        """
        if not user_id or user_id <= 0:
            return None

        try:
            api_url = f"{self.config.webhook_url.rstrip('/')}/user.get"
            params = {'ID': user_id}

            response = requests.get(api_url, params=params, timeout=self.config.request_timeout)
            response.raise_for_status()
            data = response.json()

            result = data.get('result')
            if result and isinstance(result, list) and len(result) > 0:
                user = result[0]
                last_name = user.get('LAST_NAME', '')
                first_name = user.get('NAME', '')
                full_name = f"{last_name} {first_name}".strip()
                if full_name:
                    return full_name
                # Fallback на email или логин
                return user.get('EMAIL') or user.get('LOGIN') or str(user_id)

            logger.debug(f"Пользователь с ID={user_id} не найден в Bitrix24")
            return None

        except requests.exceptions.RequestException as e:
            logger.warning(f"Ошибка запроса user.get для user_id={user_id}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Неожиданная ошибка при получении имени пользователя {user_id}: {e}")
            return None

    def _get_list_element_name(self, iblock_id: int, element_id: int) -> Optional[str]:
        """
        Получение названия элемента универсального списка Bitrix24 через REST API lists.element.get

        Args:
            iblock_id: ID инфоблока (универсального списка)
            element_id: ID элемента списка

        Returns:
            Название элемента или None при ошибке
        """
        if not iblock_id or not element_id:
            return None

        try:
            api_url = f"{self.config.webhook_url.rstrip('/')}/lists.element.get"
            params = {
                'IBLOCK_TYPE_ID': 'lists',
                'IBLOCK_ID': iblock_id,
                'ELEMENT_ID': element_id
            }

            response = requests.get(api_url, params=params, timeout=self.config.request_timeout)
            response.raise_for_status()
            data = response.json()

            result = data.get('result')
            if result and isinstance(result, list) and len(result) > 0:
                element = result[0]
                name = element.get('NAME')
                if name:
                    return name

            logger.debug(f"Элемент списка iblock_id={iblock_id}, element_id={element_id} не найден")
            return None

        except requests.exceptions.RequestException as e:
            logger.warning(f"Ошибка запроса lists.element.get для iblock_id={iblock_id}, element_id={element_id}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Неожиданная ошибка при получении элемента списка: {e}")
            return None

    def _format_questionnaire_answer(
        self,
        question: Dict[str, Any],
        raw_value: Any
    ) -> str:
        """
        Форматирование ответа на вопрос анкеты в человекочитаемый вид

        Args:
            question: Данные вопроса (CODE, NAME, TYPE, ENUM_OPTIONS и т.д.)
            raw_value: Сырое значение из переменных процесса

        Returns:
            Отформатированное значение для отображения
        """
        if raw_value is None:
            return "-"

        # Извлекаем value из Camunda формата {"value": ..., "type": ...}
        value = raw_value
        if isinstance(raw_value, dict):
            value = raw_value.get('value', raw_value.get('VALUE', raw_value))

        if value is None or value == '':
            return "-"

        question_type = (question.get('TYPE') or '').lower()

        # Boolean: true → Да, false → Нет
        if question_type == 'boolean':
            if isinstance(value, bool):
                return "Да" if value else "Нет"
            if isinstance(value, str):
                return "Да" if value.lower() in ('true', '1', 'yes', 'да') else "Нет"
            if isinstance(value, (int, float)):
                return "Да" if value != 0 else "Нет"
            return "-"

        # Date: ISO → DD.MM.YYYY
        if question_type == 'date':
            if isinstance(value, str):
                try:
                    # Попытка распарсить ISO формат
                    normalized = value.strip().replace('Z', '+00:00')
                    if 'T' in normalized:
                        dt = datetime.fromisoformat(normalized.split('T')[0])
                    else:
                        dt = datetime.fromisoformat(normalized)
                    return dt.strftime("%d.%m.%Y")
                except ValueError:
                    try:
                        dt = datetime.strptime(value.strip()[:10], "%Y-%m-%d")
                        return dt.strftime("%d.%m.%Y")
                    except ValueError:
                        return str(value)
            return str(value)

        # User: ID → Имя пользователя
        if question_type == 'user':
            try:
                user_id = int(value)
                user_name = self._get_user_name_by_id(user_id)
                return user_name if user_name else str(user_id)
            except (TypeError, ValueError):
                return str(value)

        # Universal list: ID → Название элемента
        if question_type == 'universal_list':
            try:
                element_id = int(value)
                # Получаем iblock_id из ENUM_OPTIONS или _iblockId
                iblock_id = None
                enum_options = question.get('ENUM_OPTIONS')
                if isinstance(enum_options, dict):
                    iblock_id = enum_options.get('iblock_id')
                if not iblock_id:
                    iblock_id = question.get('_iblockId')

                if iblock_id:
                    element_name = self._get_list_element_name(int(iblock_id), element_id)
                    return element_name if element_name else str(element_id)
                return str(element_id)
            except (TypeError, ValueError):
                return str(value)

        # Integer
        if question_type == 'integer':
            try:
                return str(int(value))
            except (TypeError, ValueError):
                return str(value)

        # String, enum и остальные типы
        return str(value)

    def _build_questionnaires_description_block(
        self,
        questionnaires: List[Dict[str, Any]],
        process_variables: Dict[str, Any],
        element_id: str
    ) -> Optional[str]:
        """
        Формирование BB-code блока с данными анкет для вставки в описание задачи

        Args:
            questionnaires: Список анкет из questionnairesInDescription.items
            process_variables: Переменные процесса Camunda
            element_id: ID текущего элемента диаграммы (Activity)

        Returns:
            BB-code строка с данными анкет или None если анкет нет
        """
        if not questionnaires:
            return None

        blocks: List[str] = []

        for questionnaire in questionnaires:
            questionnaire_code = questionnaire.get('CODE') or ''
            questionnaire_title = questionnaire.get('TITLE') or questionnaire_code or 'Анкета'
            questions = questionnaire.get('questions') or []

            if not questions:
                continue

            lines: List[str] = []
            # Заголовок анкеты в BB-code (жирный)
            lines.append(f"[B]{questionnaire_title}[/B]")

            for question in questions:
                question_code = question.get('CODE') or ''
                question_name = question.get('NAME') or question_code or 'Вопрос'

                # Формируем ключ переменной: {ELEMENT_ID}_{QUESTIONNAIRE_CODE}_{QUESTION_CODE}
                var_key = f"{element_id}_{questionnaire_code}_{question_code}"
                raw_value = process_variables.get(var_key)

                # Форматируем значение в зависимости от типа
                formatted_value = self._format_questionnaire_answer(question, raw_value)

                # Добавляем строку с вопросом и ответом
                lines.append(f"• {question_name}: {formatted_value}")

            if len(lines) > 1:  # Если есть хотя бы один вопрос кроме заголовка
                blocks.append("\n".join(lines))

        if not blocks:
            return None

        return "\n\n".join(blocks)

    # ЗАКОММЕНТИРОВАНО: Используется API шаблонов задач
    # Дата: 2025-11-03
    # Возможно использование в будущем для fallback или других сценариев
    def _extract_title(self, variables: Dict[str, Any], metadata: Dict[str, Any], topic: str) -> str:
        """Извлечение заголовка задачи из данных сообщения"""
        # ЗАКОММЕНТИРОВАНО: Теперь используем template.TITLE из API шаблонов
        
        # Приоритет 1: Попытка получить заголовок из activityInfo
        if metadata and 'activityInfo' in metadata:
            activity_info = metadata['activityInfo']
            if isinstance(activity_info, dict) and 'name' in activity_info:
                activity_name = activity_info['name']
                if activity_name and isinstance(activity_name, str):
                    return activity_name
        
        # Fallback - создание заголовка на основе топика
        topic_titles = {
            'bitrix_create_task': 'Новая задача из процесса Camunda',
            'bitrix_update_task': 'Обновление задачи из процесса Camunda',
            'bitrix_create_deal': 'Новая сделка из процесса Camunda',
            'bitrix_update_deal': 'Обновление сделки из процесса Camunda',
            'bitrix_create_contact': 'Новый контакт из процесса Camunda',
        }
        
        return topic_titles.get(topic, f'Задача из Camunda процесса ({topic})')
    
    # ЗАКОММЕНТИРОВАНО: Используется API шаблонов задач
    # Дата: 2025-11-03
    # Возможно использование в будущем для fallback или других сценариев
    def _create_description(self, message_data: Dict[str, Any]) -> str:
        """Создание описания задачи (для отладки - все данные сообщения)"""
        # ЗАКОММЕНТИРОВАНО: Теперь используем template.DESCRIPTION из API шаблонов
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
    
    # ЗАКОММЕНТИРОВАНО: Используется API шаблонов задач
    # Дата: 2025-11-03
    # Возможно использование в будущем для fallback или других сценариев
    def _extract_assignee_id(self, variables: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        """Извлечение ID роли (assigneeId) из extensionProperties"""
        # ЗАКОММЕНТИРОВАНО: Теперь используем template.RESPONSIBLE_ID + fallback на originatorId
        logger.debug(f"Извлечение assigneeId: metadata={metadata}")
        # Проверяем наличие extensionProperties с assigneeId
        extension_properties = metadata.get("extensionProperties", {})
        logger.debug(f"extensionProperties: {extension_properties}")
        if "assigneeId" in extension_properties:
            assignee_id = extension_properties["assigneeId"]
            logger.debug(f"Найден assigneeId: {assignee_id}")
            if assignee_id:
                return str(assignee_id)
        
        # Fallback - возвращаем None если роль не найдена
        logger.warning("assigneeId не найден в extensionProperties")
        return None
    
    def _get_responsible_id_by_assignee(self, assignee_id: str) -> int:
        """
        Получение ID пользователя Bitrix24 по ID из BPMN
        Прямое использование assigneeId как responsible_id
        
        Args:
            assignee_id: ID пользователя из BPMN extensionProperties
            
        Returns:
            ID пользователя Bitrix24
            
        Raises:
            ValueError: Если assigneeId не указан или некорректен
        """
        if not assignee_id:
            raise ValueError("assigneeId не указан в BPMN - невозможно определить ответственного")
        
        try:
            responsible_id = int(assignee_id)
            logger.debug(f"Используется assigneeId={assignee_id} как responsible_id={responsible_id}")
            return responsible_id
        except (ValueError, TypeError) as e:
            raise ValueError(f"Некорректный assigneeId={assignee_id}: {e}")
    
    

    

    

    
    
    
    # ЗАКОММЕНТИРОВАНО: Используется API шаблонов задач
    # Дата: 2025-11-03
    # Возможно использование в будущем для fallback или других сценариев
    def _extract_priority(self, variables: Dict[str, Any], metadata: Dict[str, Any]) -> int:
        """Извлечение приоритета задачи"""
        # ЗАКОММЕНТИРОВАНО: Теперь используем template.PRIORITY из API шаблонов
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
    
    # ЗАКОММЕНТИРОВАНО: Используется API шаблонов задач
    # Дата: 2025-11-03
    # Возможно использование в будущем для fallback или других сценариев
    def _extract_deadline(self, variables: Dict[str, Any], metadata: Dict[str, Any]) -> Optional[str]:
        """Извлечение дедлайна задачи"""
        # ЗАКОММЕНТИРОВАНО: Теперь вычисляем из template.DEADLINE_AFTER (секунды → datetime)
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
    
    # ЗАКОММЕНТИРОВАНО: Используется API шаблонов задач
    # Дата: 2025-11-03
    # Возможно использование в будущем для fallback или других сценариев
    def _extract_project_id(self, variables: Dict[str, Any]) -> Optional[int]:
        """Извлечение ID проекта (GROUP_ID) из переменных процесса"""
        # ЗАКОММЕНТИРОВАНО: Теперь используем template.GROUP_ID из API шаблонов
        project_id = variables.get('projectId')
        if project_id:
            # Обработка как объекта Camunda {value, type} или простого значения
            if isinstance(project_id, dict) and 'value' in project_id:
                project_id = project_id['value']
            
            try:
                return int(project_id)
            except (ValueError, TypeError):
                logger.warning(f"Не удалось преобразовать projectId в число: {project_id}")
        return None
    
    # ЗАКОММЕНТИРОВАНО: Используется API шаблонов задач
    # Дата: 2025-11-03
    # Возможно использование в будущем для fallback или других сценариев
    def _extract_started_by_id(self, variables: Dict[str, Any]) -> int:
        """
        Извлечение ID постановщика задачи (CREATED_BY) из переменных процесса startedBy
        # ЗАКОММЕНТИРОВАНО: Теперь используем template.CREATED_BY + fallback на originatorId
        
        Args:
            variables: Переменные процесса из Camunda
            
        Returns:
            ID пользователя Bitrix24 для поля CREATED_BY
            
        Raises:
            ValueError: Если startedBy не указан или некорректен
        """
        started_by = variables.get('startedBy')
        
        if not started_by:
            # Fallback - используем ID=1 по умолчанию с предупреждением
            logger.warning("startedBy не найден в переменных процесса, используется ID=1 по умолчанию")
            return 1
        
        try:
            # Обработка формата Camunda переменных: {"value": ID, "type": "Long"}
            if isinstance(started_by, dict) and 'value' in started_by:
                started_by_id = int(started_by['value'])
            else:
                # Прямое значение
                started_by_id = int(started_by)
            
            logger.debug(f"Используется startedBy={started_by} как created_by_id={started_by_id}")
            return started_by_id
        except (ValueError, TypeError) as e:
            logger.error(f"Некорректный startedBy={started_by}: {e}, используется ID=1 по умолчанию")
            return 1
    
    # ЗАКОММЕНТИРОВАНО: Используется API шаблонов задач
    # Дата: 2025-11-03
    # Возможно использование в будущем для fallback или других сценариев
    def _extract_originator_id(self, metadata: Dict[str, Any]) -> int:
        """
        Извлечение ID постановщика (originatorId) из свойств уровня процесса
        # ЗАКОММЕНТИРОВАНО: Используется для fallback CREATED_BY/RESPONSIBLE_ID в _build_task_data_from_template()
        
        Args:
            metadata: Метаданные сообщения из RabbitMQ
            
        Returns:
            ID пользователя Bitrix24 для поля CREATED_BY
            
        Raises:
            ValueError: Если originatorId не указан или некорректен
        """
        # Получаем processProperties из метаданных
        process_properties = metadata.get("processProperties", {})
        
        originator_id = process_properties.get("originatorId")
        
        if not originator_id:
            # Fallback - используем ID=1 по умолчанию с предупреждением
            logger.warning("originatorId не найден в processProperties, используется ID=1 по умолчанию")
            return 1
        
        try:
            originator_id_int = int(originator_id)
            logger.debug(f"Используется originatorId={originator_id} как created_by_id={originator_id_int}")
            return originator_id_int
        except (ValueError, TypeError) as e:
            logger.error(f"Некорректный originatorId={originator_id}: {e}, используется ID=1 по умолчанию")
            return 1
    
    # ЗАКОММЕНТИРОВАНО: Используется API шаблонов задач
    # Дата: 2025-11-03
    # Возможно использование в будущем для fallback или других сценариев
    def _extract_group_id(self, metadata: Dict[str, Any]) -> Optional[int]:
        """
        Извлечение ID группы (проекта) из свойств уровня процесса
        # ЗАКОММЕНТИРОВАНО: Теперь используем template.GROUP_ID из API шаблонов
        
        Args:
            metadata: Метаданные сообщения из RabbitMQ
            
        Returns:
            ID группы Bitrix24 для поля GROUP_ID или None если не указан
        """
        # Получаем processProperties из метаданных
        process_properties = metadata.get("processProperties", {})
        
        group_id = process_properties.get("groupId")
        
        if not group_id:
            logger.debug("groupId не найден в processProperties, GROUP_ID не будет установлен")
            return None
        
        try:
            group_id_int = int(group_id)
            logger.debug(f"Используется groupId={group_id} как GROUP_ID={group_id_int}")
            return group_id_int
        except (ValueError, TypeError) as e:
            logger.error(f"Некорректный groupId={group_id}: {e}, GROUP_ID не будет установлен")
            return None
    
    # ЗАКОММЕНТИРОВАНО: Используется API шаблонов задач
    # Дата: 2025-11-03
    # Возможно использование в будущем для fallback или других сценариев
    def _extract_created_by_id(self, variables: Dict[str, Any], metadata: Dict[str, Any] = None) -> int:
        """Извлечение ID постановщика задачи (CREATED_BY) из переменных процесса"""
        # ЗАКОММЕНТИРОВАНО: Теперь используем template.CREATED_BY + fallback на originatorId
        project_manager_id = variables.get('projectManagerId')
        if project_manager_id:
            try:
                return int(project_manager_id)
            except (ValueError, TypeError):
                logger.warning(f"Не удалось преобразовать projectManagerId в число: {project_manager_id}, используется assigneeId")
        
        # Fallback - используем assigneeId если projectManagerId не найден или некорректен
        assignee_id = self._extract_assignee_id(variables, metadata or {})
        return self._get_responsible_id_by_assignee(assignee_id)
    
    # ЗАКОММЕНТИРОВАНО: Используется API шаблонов задач
    # Дата: 2025-11-03
    # Возможно использование в будущем для fallback или других сценариев
    def _extract_additional_fields(self, variables: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Извлечение дополнительных полей для задачи"""
        # ЗАКОММЕНТИРОВАНО: Теперь все поля берутся из шаблона, дополнительные поля не используются
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
    
    # ЗАКОММЕНТИРОВАНО: Используется API шаблонов задач
    # Дата: 2025-11-03
    # Возможно использование в будущем для fallback или других сценариев
    def _extract_user_fields(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Извлечение пользовательских полей UF_ из метаданных
        # ЗАКОММЕНТИРОВАНО: Пользовательские поля берутся только из шаблона
        
        Args:
            metadata: Метаданные сообщения из RabbitMQ
            
        Returns:
            Словарь с пользовательскими полями для Bitrix24
        """
        user_fields = {}
        
        # Получаем extensionProperties из метаданных
        extension_properties = metadata.get("extensionProperties", {})
        
        # Список поддерживаемых пользовательских полей для задач
        supported_user_fields = [
            "UF_RESULT_EXPECTED",
            "UF_RESULT_QUESTION"
        ]
        
        # Извлекаем поддерживаемые пользовательские поля
        for field_name in supported_user_fields:
            if field_name in extension_properties:
                field_value = extension_properties[field_name]
                
                # Обработка различных типов значений
                if field_value is not None:
                    # Для поля UF_RESULT_EXPECTED преобразуем строку в булево значение
                    if field_name == "UF_RESULT_EXPECTED":
                        if isinstance(field_value, str):
                            # Битрикс ожидает 'Y' или 'N' для булевых полей
                            user_fields[field_name] = 'Y' if field_value.lower() in ['true', '1', 'да', 'yes'] else 'N'
                        elif isinstance(field_value, bool):
                            user_fields[field_name] = 'Y' if field_value else 'N'
                        else:
                            user_fields[field_name] = 'N'  # По умолчанию
                    
                    # Для текстовых полей передаем как есть
                    elif field_name == "UF_RESULT_QUESTION":
                        if isinstance(field_value, str) and field_value.strip():
                            user_fields[field_name] = field_value.strip()
                    
                    # Для других полей передаем строковое представление
                    else:
                        user_fields[field_name] = str(field_value)
                        
                    logger.debug(f"Извлечено пользовательское поле: {field_name}={user_fields.get(field_name)}")
        
        if user_fields:
            logger.info(f"Извлечено {len(user_fields)} пользовательских полей: {list(user_fields.keys())}")
        else:
            logger.debug("Пользовательские поля UF_ в метаданных не найдены")
        
        return user_fields
    
    # ЗАКОММЕНТИРОВАНО: Используется API шаблонов задач
    # Дата: 2025-11-03
    # Возможно использование в будущем для fallback или других сценариев
    def _extract_checklists(self, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Извлечение данных чек-листов из metadata.extensionProperties
        # ЗАКОММЕНТИРОВАНО: Теперь используем checklists из шаблона через _extract_checklists_from_template()
        
        Args:
            metadata: Метаданные сообщения из RabbitMQ
            
        Returns:
            Список чек-листов с их элементами
        """
        checklists = []
        
        try:
            # Получаем extensionProperties из метаданных
            extension_properties = metadata.get("extensionProperties", {})
            
            # Ищем поле checklists
            checklists_data = extension_properties.get("checklists")
            
            if not checklists_data:
                logger.debug("Данные чек-листов не найдены в extensionProperties")
                return checklists
            
            # Парсим JSON строку с чек-листами
            if isinstance(checklists_data, str):
                try:
                    parsed_checklists = json.loads(checklists_data)
                    if isinstance(parsed_checklists, list):
                        checklists = parsed_checklists
                        logger.info(f"Извлечено {len(checklists)} чек-листов из метаданных")
                        
                        # Логируем структуру для отладки
                        for i, checklist in enumerate(checklists):
                            name = checklist.get('name', f'Чек-лист {i+1}')
                            items = checklist.get('items', [])
                            logger.debug(f"Чек-лист '{name}': {len(items)} элементов")
                    else:
                        logger.warning(f"Неожиданная структура чек-листов: {type(parsed_checklists)}")
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка парсинга JSON чек-листов: {e}")
                    logger.error(f"Данные: {checklists_data[:200]}...")
            elif isinstance(checklists_data, list):
                # Если данные уже в виде списка
                checklists = checklists_data
                logger.info(f"Извлечено {len(checklists)} чек-листов из метаданных (прямой список)")
            else:
                logger.warning(f"Неожиданный тип данных чек-листов: {type(checklists_data)}")
            
        except Exception as e:
            logger.error(f"Ошибка извлечения чек-листов из метаданных: {e}")
        
        return checklists
    
    # ========== МЕТОДЫ ДЛЯ РАБОТЫ С ЧЕК-ЛИСТАМИ ЗАДАЧ ==========
    
    def _request_sync(self, method: str, api_method: str, params: Dict[str, Any]) -> Optional[Any]:
        """
        Синхронное выполнение HTTP запроса к API Bitrix24
        
        Args:
            method: HTTP метод (GET, POST)
            api_method: Метод API Bitrix24
            params: Параметры запроса
            
        Returns:
            Результат запроса или None в случае ошибки
        """
        try:
            url = f"{self.config.webhook_url}/{api_method}"
            
            if method.upper() == 'GET':
                response = requests.get(
                    url,
                    params=params,
                    timeout=self.config.request_timeout
                )
            else:
                response = requests.post(
                    url,
                    json=params,
                    headers={'Content-Type': 'application/json'},
                    timeout=self.config.request_timeout
                )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get('error'):
                logger.error(f"Ошибка API Bitrix24 ({api_method}): {result['error']}")
                logger.error(f"Описание ошибки: {result.get('error_description', 'Не указано')}")
                return None
            
            return result.get('result')
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса к API Bitrix24 ({api_method}): {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования ответа от API Bitrix24 ({api_method}): {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе к API Bitrix24 ({api_method}): {e}")
            return None

    def create_checklist_group_sync(self, task_id: int, title: str) -> Optional[int]:
        """
        Синхронно создает группу чек-листа с названием.
        
        :param task_id: ID задачи
        :param title: Название группы чек-листа
        :return: ID созданной группы или None
        """
        api_method = 'task.checklistitem.add'
        # Группа чек-листа создается с PARENT_ID = 0
        params = {
            'taskId': task_id,
            'fields': {
                'TITLE': title,
                'PARENT_ID': 0,  # 0 означает, что это группа (корневой элемент)
                'IS_COMPLETE': False,
                'SORT_INDEX': '10'
            }
        }
        
        logger.debug(f"Создание группы чек-листа '{title}' для задачи {task_id}...")
        result = self._request_sync('POST', api_method, params)
        if result:
            # result может быть числом или объектом
            if isinstance(result, (int, str)):
                group_id = int(result)
                logger.debug(f"Группа чек-листа '{title}' создана с ID {group_id}")
                return group_id
            elif isinstance(result, dict) and 'ID' in result:
                group_id = int(result['ID'])
                logger.debug(f"Группа чек-листа '{title}' создана с ID {group_id}")
                return group_id
            else:
                logger.warning(f"Неожиданный ответ при создании группы чек-листа: {result}")
                return None
        else:
            logger.warning(f"Не удалось создать группу чек-листа '{title}' для задачи {task_id}")
            return None

    def add_checklist_item_sync(self, task_id: int, title: str, is_complete: bool = False, 
                               parent_id: Optional[int] = None) -> Optional[int]:
        """
        Синхронно добавляет элемент в чек-лист задачи.
        
        :param task_id: ID задачи
        :param title: Текст элемента чек-листа
        :param is_complete: Выполнен ли элемент (по умолчанию False)
        :param parent_id: ID родительского элемента (для группы)
        :return: ID созданного элемента или None
        """
        api_method = 'task.checklistitem.add'
        # Правильная структура с полем TITLE
        params = {
            'taskId': task_id,
            'fields': {
                'TITLE': title,
                'IS_COMPLETE': is_complete
            }
        }
        
        if parent_id:
            params['fields']['PARENT_ID'] = parent_id
        
        logger.debug(f"Добавление элемента '{title}' в чек-лист задачи {task_id}...")
        result = self._request_sync('POST', api_method, params)
        if result:
            # result может быть числом или объектом
            if isinstance(result, (int, str)):
                item_id = int(result)
                logger.debug(f"Элемент чек-листа '{title}' создан с ID {item_id}")
                return item_id
            elif isinstance(result, dict) and 'ID' in result:
                item_id = int(result['ID'])
                logger.debug(f"Элемент чек-листа '{title}' создан с ID {item_id}")
                return item_id
            else:
                logger.warning(f"Неожиданный ответ при создании элемента чек-листа: {result}")
                return None
        else:
            logger.warning(f"Не удалось создать элемент чек-листа '{title}' для задачи {task_id}")
            return None

    def create_task_checklists_sync(self, task_id: int, checklists_data: List[Dict[str, Any]]) -> bool:
        """
        Синхронно создает чек-листы для задачи на основе данных из сообщения
        
        Args:
            task_id: ID задачи в Bitrix24
            checklists_data: Список чек-листов с их элементами
            
        Returns:
            True если все чек-листы созданы успешно, False иначе
        """
        if not checklists_data:
            logger.debug(f"Нет данных чек-листов для создания в задаче {task_id}")
            return True
        
        try:
            logger.info(f"Создание {len(checklists_data)} чек-листов для задачи {task_id}")
            
            total_groups = 0
            total_items = 0
            errors_count = 0
            
            for checklist in checklists_data:
                checklist_name = checklist.get('name', 'Без названия')
                checklist_items = checklist.get('items', [])
                
                if not checklist_items:
                    logger.warning(f"Пропущен пустой чек-лист '{checklist_name}'")
                    continue
                
                try:
                    # Создаем группу чек-листа
                    group_id = self.create_checklist_group_sync(task_id, checklist_name)
                    
                    if group_id:
                        total_groups += 1
                        logger.debug(f"✅ Создана группа '{checklist_name}' с ID {group_id}")
                        
                        # Создаем элементы чек-листа в группе
                        for item_text in checklist_items:
                            if isinstance(item_text, str) and item_text.strip():
                                item_id = self.add_checklist_item_sync(
                                    task_id=task_id,
                                    title=item_text.strip(),
                                    is_complete=False,
                                    parent_id=group_id
                                )
                                
                                if item_id:
                                    total_items += 1
                                    logger.debug(f"✅ Создан элемент '{item_text}' с ID {item_id}")
                                else:
                                    errors_count += 1
                                    logger.error(f"❌ Не удалось создать элемент '{item_text}' в группе {group_id}")
                            else:
                                logger.warning(f"Пропущен некорректный элемент чек-листа: {item_text}")
                    else:
                        errors_count += 1
                        logger.error(f"❌ Не удалось создать группу '{checklist_name}', пропускаем её элементы")
                        
                except Exception as e:
                    errors_count += 1
                    logger.error(f"❌ Ошибка создания чек-листа '{checklist_name}': {e}")
            
            # Логируем результаты
            if total_groups > 0 or total_items > 0:
                logger.info(f"✅ Создано чек-листов для задачи {task_id}: {total_groups} групп, {total_items} элементов")
            
            if errors_count > 0:
                logger.error(f"❌ Ошибки при создании чек-листов задачи {task_id}: {errors_count} ошибок")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Критическая ошибка при создании чек-листов задачи {task_id}: {e}")
            return False
    
    async def _request(self, method: str, api_method: str, params: Dict[str, Any]) -> Optional[Any]:
        """
        Выполнение HTTP запроса к API Bitrix24
        
        Args:
            method: HTTP метод (GET, POST)
            api_method: Метод API Bitrix24
            params: Параметры запроса
            
        Returns:
            Результат запроса или None в случае ошибки
        """
        try:
            url = f"{self.config.webhook_url}/{api_method}"
            
            if method.upper() == 'GET':
                response = requests.get(
                    url,
                    params=params,
                    timeout=self.config.request_timeout
                )
            else:
                response = requests.post(
                    url,
                    json=params,
                    headers={'Content-Type': 'application/json'},
                    timeout=self.config.request_timeout
                )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get('error'):
                logger.error(f"Ошибка API Bitrix24 ({api_method}): {result['error']}")
                logger.error(f"Описание ошибки: {result.get('error_description', 'Не указано')}")
                return None
            
            return result.get('result')
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса к API Bitrix24 ({api_method}): {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования ответа от API Bitrix24 ({api_method}): {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе к API Bitrix24 ({api_method}): {e}")
            return None

    async def create_checklist_group(self, task_id: int, title: str) -> Optional[int]:
        """
        Создает группу чек-листа с названием.
        
        :param task_id: ID задачи
        :param title: Название группы чек-листа
        :return: ID созданной группы или None
        """
        api_method = 'task.checklistitem.add'
        # Группа чек-листа создается с PARENT_ID = 0
        params = {
            'taskId': task_id,
            'fields': {
                'TITLE': title,
                'PARENT_ID': 0,  # 0 означает, что это группа (корневой элемент)
                'IS_COMPLETE': False,
                'SORT_INDEX': '10'
            }
        }
        
        logger.debug(f"Создание группы чек-листа '{title}' для задачи {task_id}...")
        result = await self._request('POST', api_method, params)
        if result:
            # result может быть числом или объектом
            if isinstance(result, (int, str)):
                group_id = int(result)
                logger.debug(f"Группа чек-листа '{title}' создана с ID {group_id}")
                return group_id
            elif isinstance(result, dict) and 'ID' in result:
                group_id = int(result['ID'])
                logger.debug(f"Группа чек-листа '{title}' создана с ID {group_id}")
                return group_id
            else:
                logger.warning(f"Неожиданный ответ при создании группы чек-листа: {result}")
                return None
        else:
            logger.warning(f"Не удалось создать группу чек-листа '{title}' для задачи {task_id}")
            return None

    async def add_checklist_item(self, task_id: int, title: str, is_complete: bool = False, 
                                parent_id: Optional[int] = None) -> Optional[int]:
        """
        Добавляет элемент в чек-лист задачи.
        
        :param task_id: ID задачи
        :param title: Текст элемента чек-листа
        :param is_complete: Выполнен ли элемент (по умолчанию False)
        :param parent_id: ID родительского элемента (для группы)
        :return: ID созданного элемента или None
        """
        api_method = 'task.checklistitem.add'  # Исправленный метод
        # Правильная структура с полем TITLE
        params = {
            'taskId': task_id,
            'fields': {
                'TITLE': title,
                'IS_COMPLETE': is_complete
            }
        }
        
        if parent_id:
            params['fields']['PARENT_ID'] = parent_id
        
        logger.debug(f"Добавление элемента '{title}' в чек-лист задачи {task_id}...")
        result = await self._request('POST', api_method, params)
        if result:
            # result может быть числом или объектом
            if isinstance(result, (int, str)):
                item_id = int(result)
                logger.debug(f"Элемент чек-листа '{title}' создан с ID {item_id}")
                return item_id
            elif isinstance(result, dict) and 'ID' in result:
                item_id = int(result['ID'])
                logger.debug(f"Элемент чек-листа '{title}' создан с ID {item_id}")
                return item_id
            else:
                logger.warning(f"Неожиданный ответ при создании элемента чек-листа: {result}")
                return None
        else:
            logger.warning(f"Не удалось создать элемент чек-листа '{title}' для задачи {task_id}")
            return None

    async def get_task_checklists(self, task_id: int) -> List[Dict[str, Any]]:
        """
        Получает чек-листы задачи.
        
        :param task_id: ID задачи
        :return: Список чек-листов задачи
        """
        api_method = 'task.checklistitem.getlist'  # Исправленный метод
        params = {'taskId': task_id}  # Исправленный параметр
        logger.debug(f"Запрос чек-листов для задачи {task_id}...")
        result = await self._request('GET', api_method, params)
        if result:
            if isinstance(result, list):
                logger.debug(f"Получено {len(result)} элементов чек-листов для задачи {task_id}")
                
                return result
            else:
                logger.warning(f"Неожиданный тип ответа для чек-листов задачи {task_id}: {type(result)}")
                return []
        return []

    async def delete_checklist_item(self, item_id: int, task_id: int) -> bool:
        """
        Удаляет элемент чек-листа.
        
        :param item_id: ID элемента чек-листа
        :param task_id: ID задачи
        :return: True в случае успеха, иначе False
        """
        api_method = 'tasks.task.checklist.delete'  # ← ИСПРАВЛЕННЫЙ РАБОЧИЙ МЕТОД
        params = {'taskId': task_id, 'checkListItemId': item_id}  # ← ИСПРАВЛЕННЫЕ ПАРАМЕТРЫ
        result = await self._request('POST', api_method, params)
        return bool(result)

    async def clear_task_checklists(self, task_id: int) -> bool:
        """
        Очищает все чек-листы задачи.
        
        :param task_id: ID задачи
        :return: True в случае успеха
        """
        try:
            # Получаем все элементы чек-листов
            items = await self.get_task_checklists(task_id)
            
            if not items:
                logger.debug(f"У задачи {task_id} нет чек-листов для очистки")
                return True
            
            logger.debug(f"Очистка {len(items)} элементов чек-листов задачи {task_id}...")
            
            # Удаляем все элементы
            deleted_count = 0
            errors_count = 0
            failed_items = []
            
            for item in items:
                item_id = item.get('ID') or item.get('id')
                item_title = item.get('TITLE', 'Без названия')
                parent_id = item.get('PARENT_ID') or item.get('parent_id')
                
                if item_id:
                    try:
                        # Используем существующий метод для консистентности
                        success = await self.delete_checklist_item(int(item_id), task_id)
                        if success:
                            deleted_count += 1
                            logger.debug(f"✅ Удален ID:{item_id} - '{item_title}'")
                        else:
                            errors_count += 1
                            logger.error(f"❌ НЕ УДАЛЕН ID:{item_id} - '{item_title}'")
                            failed_items.append({
                                'item_id': item_id,
                                'title': item_title,
                                'error': 'API вернул неуспешный результат'
                            })
                                
                    except Exception as e:
                        errors_count += 1
                        failed_items.append({
                            'item_id': item_id,
                            'title': item_title,
                            'error': str(e)
                        })
                        logger.error(f"❌ ОШИБКА ID:{item_id} '{item_title}': {e}")
                else:
                    logger.warning(f"⚠️ Элемент без ID пропущен: '{item_title}'")
            
            # Логируем результаты
            if deleted_count > 0:
                logger.info(f"✅ Успешно удалено {deleted_count} элементов чек-листов задачи {task_id}")
            
            if errors_count > 0:
                logger.error(f"❌ Не удалось удалить {errors_count} элементов чек-листов задачи {task_id}:")
                for failed_item in failed_items[:5]:  # Показываем первые 5 ошибок для краткости
                    logger.error(f"   • Элемент {failed_item['item_id']} '{failed_item['title']}': {failed_item['error']}")
                if len(failed_items) > 5:
                    logger.error(f"   ... и еще {len(failed_items) - 5} ошибок")
            
            # Возвращаем True только если все элементы удалены успешно
            if errors_count == 0:
                return True
            else:
                logger.error(f"❌ Очистка чек-листов задачи {task_id} завершена с ошибками: {errors_count}/{len(items)} элементов не удалось удалить")
                return False
            
        except Exception as e:
            logger.warning(f"Ошибка очистки чек-листов задачи {task_id}: {e}")
            return False

    async def create_task_checklists(self, task_id: int, checklists_data: List[Dict[str, Any]]) -> bool:
        """
        Создает чек-листы для задачи на основе данных из сообщения
        
        Args:
            task_id: ID задачи в Bitrix24
            checklists_data: Список чек-листов с их элементами
            
        Returns:
            True если все чек-листы созданы успешно, False иначе
        """
        if not checklists_data:
            logger.debug(f"Нет данных чек-листов для создания в задаче {task_id}")
            return True
        
        try:
            logger.info(f"Создание {len(checklists_data)} чек-листов для задачи {task_id}")
            
            total_groups = 0
            total_items = 0
            errors_count = 0
            
            for checklist in checklists_data:
                checklist_name = checklist.get('name', 'Без названия')
                checklist_items = checklist.get('items', [])
                
                if not checklist_items:
                    logger.warning(f"Пропущен пустой чек-лист '{checklist_name}'")
                    continue
                
                try:
                    # Создаем группу чек-листа
                    group_id = await self.create_checklist_group(task_id, checklist_name)
                    
                    if group_id:
                        total_groups += 1
                        logger.debug(f"✅ Создана группа '{checklist_name}' с ID {group_id}")
                        
                        # Создаем элементы чек-листа в группе
                        for item_text in checklist_items:
                            if isinstance(item_text, str) and item_text.strip():
                                item_id = await self.add_checklist_item(
                                    task_id=task_id,
                                    title=item_text.strip(),
                                    is_complete=False,
                                    parent_id=group_id
                                )
                                
                                if item_id:
                                    total_items += 1
                                    logger.debug(f"✅ Создан элемент '{item_text}' с ID {item_id}")
                                else:
                                    errors_count += 1
                                    logger.error(f"❌ Не удалось создать элемент '{item_text}' в группе {group_id}")
                            else:
                                logger.warning(f"Пропущен некорректный элемент чек-листа: {item_text}")
                    else:
                        errors_count += 1
                        logger.error(f"❌ Не удалось создать группу '{checklist_name}', пропускаем её элементы")
                        
                except Exception as e:
                    errors_count += 1
                    logger.error(f"❌ Ошибка создания чек-листа '{checklist_name}': {e}")
            
            # Логируем результаты
            if total_groups > 0 or total_items > 0:
                logger.info(f"✅ Создано чек-листов для задачи {task_id}: {total_groups} групп, {total_items} элементов")
            
            if errors_count > 0:
                logger.error(f"❌ Ошибки при создании чек-листов задачи {task_id}: {errors_count} ошибок")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Критическая ошибка при создании чек-листов задачи {task_id}: {e}")
            return False
    
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
    
    def _send_to_error_queue(self, message_data: Dict[str, Any], error_message: str) -> bool:
        """
        Отправка сообщения в очередь ошибок для ручного разбора
        
        Args:
            message_data: Исходное сообщение из RabbitMQ
            error_message: Описание ошибки
            
        Returns:
            True если сообщение успешно отправлено, False иначе
        """
        try:
            task_id = message_data.get('task_id', 'unknown')
            logger.critical(f"Отправка задачи {task_id} в очередь ошибок: {error_message}")
            
            # Подготавливаем данные для очереди ошибок
            error_data = {
                "timestamp": int(time.time() * 1000),
                "original_message": message_data,
                "error_type": "ASSIGNEE_ID_ERROR",
                "error_message": error_message,
                "system": "bitrix24",
                "requires_manual_intervention": True,
                "suggested_action": "Проверить соответствие assigneeId в BPMN и пользователей в Bitrix24"
            }
            
            # Отправляем в очередь ошибок
            error_queue = "errors.camunda_tasks.queue"
            message_json = json.dumps(error_data, ensure_ascii=False)
            
            # Подключаемся к RabbitMQ если нет соединения
            if not self.publisher.is_connected():
                if not self.publisher.connect():
                    logger.error("Не удалось подключиться к RabbitMQ для отправки в очередь ошибок")
                    return False
            
            # Создаем очередь ошибок (если не существует)
            self.publisher.channel.queue_declare(queue=error_queue, durable=True)
            
            # Отправляем сообщение
            self.publisher.channel.basic_publish(
                exchange='',
                routing_key=error_queue,
                body=message_json.encode('utf-8'),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Persistent message
                    content_type='application/json',
                    timestamp=int(time.time())
                )
            )
            
            logger.critical(f"Задача {task_id} отправлена в очередь ошибок: {error_queue}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки задачи в очередь ошибок: {e}")
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
                logger.debug(f"Bitrix24 Handler: Попытка {attempt + 1}/{max_attempts} отправки результата задачи {task_id}")
                
                if self._send_success_message(original_message, response_data, original_queue):
                    logger.info(f"Bitrix24 Handler: Результат задачи {task_id} успешно отправлен в очередь успешных сообщений (попытка {attempt + 1})")
                    return True
                
                # Если не последняя попытка - ждем перед повтором
                if attempt < max_attempts - 1:
                    wait_time = 2 ** attempt  # 1, 2, 4, 8, 16 секунд
                    logger.warning(f"Bitrix24 Handler: Попытка {attempt + 1} не удалась, повтор через {wait_time}s")
                    time.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Bitrix24 Handler: Ошибка попытки {attempt + 1} отправки результата задачи {task_id}: {e}")
                
                # Если не последняя попытка - ждем перед повтором
                if attempt < max_attempts - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Bitrix24 Handler: Ошибка попытки {attempt + 1}, повтор через {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Bitrix24 Handler: Все {max_attempts} попыток отправки результата задачи {task_id} провалились")
        
        return False
    
    def _send_sync_request(self, message_data: Dict[str, Any]) -> bool:
        """
        Отправка запроса синхронизации в Bitrix24 после успешного создания задачи
        
        Args:
            message_data: Данные сообщения с processInstanceId и processDefinitionKey
            
        Returns:
            True если синхронизация успешна, False иначе
        """
        try:
            logger.debug(f"Начало синхронизации, данные сообщения: {message_data}")
            # Извлекаем данные процесса
            process_instance_id = message_data.get('processInstanceId') or message_data.get('process_instance_id')
            process_definition_key = message_data.get('processDefinitionKey') or message_data.get('process_definition_key')
            
            logger.debug(f"Извлеченные данные: processInstanceId={process_instance_id}, processDefinitionKey={process_definition_key}")
            
            if not process_instance_id:
                logger.warning("processInstanceId/process_instance_id не найден в сообщении, пропускаем синхронизацию")
                logger.debug(f"Доступные поля в сообщении: {list(message_data.keys())}")
                return False
                
            if not process_definition_key:
                logger.error("processDefinitionKey/process_definition_key не найден в сообщении - КРИТИЧЕСКАЯ ОШИБКА!")
                logger.error(f"Доступные поля в сообщении: {list(message_data.keys())}")
                logger.error(f"Полное содержимое сообщения: {json.dumps(message_data, ensure_ascii=False, indent=2)}")
                
                # Попытка извлечь ключ из processDefinitionId
                process_definition_id = message_data.get('processDefinitionId') or message_data.get('process_definition_id')
                if process_definition_id:
                    try:
                        # processDefinitionId обычно имеет формат "key:version:id"
                        process_definition_key = process_definition_id.split(':')[0]
                        logger.debug(f"Извлечен processDefinitionKey из processDefinitionId: {process_definition_key}")
                    except Exception as e:
                        logger.error(f"Ошибка извлечения ключа из processDefinitionId {process_definition_id}: {e}")
                        # НЕ возвращаем False - продолжаем попытку синхронизации с fallback
                        logger.error("Продолжаем синхронизацию без processDefinitionKey (может привести к ошибкам)")
                else:
                    logger.error("processDefinitionId также не найден - синхронизация невозможна")
                    return False
            
            # URL для синхронизации
            sync_url = f"{self.config.webhook_url.rstrip('/')}/imena.camunda.sync"
            
            # Данные для отправки
            sync_data = {
                "processDefinitionKey": process_definition_key,
                "processInstanceId": process_instance_id
            }
            
            logger.debug(f"Отправка запроса синхронизации в Bitrix24: {sync_data}")
            
            # Отправка POST запроса
            response = requests.post(
                sync_url,
                json=sync_data,
                timeout=self.config.request_timeout,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('result', {}).get('success'):
                    logger.info(f"Синхронизация успешна: processInstanceId={process_instance_id}, processDefinitionKey={process_definition_key}")
                    self.stats["sync_requests_sent"] += 1
                    return True
                else:
                    error_msg = result.get('result', {}).get('error', 'Unknown error')
                    logger.error(f"Ошибка синхронизации: {error_msg}")
                    self.stats["sync_requests_failed"] += 1
                    return False
            else:
                logger.error(f"HTTP ошибка синхронизации: {response.status_code} - {response.text}")
                self.stats["sync_requests_failed"] += 1
                return False
                
        except Exception as e:
            logger.error(f"Ошибка отправки запроса синхронизации: {e}")
            self.stats["sync_requests_failed"] += 1
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики обработчика"""
        # Базовые статистики
        uptime = time.time() - self.stats["start_time"]
        
        base_stats = {
            "uptime_seconds": uptime,
            "total_messages": self.stats["total_messages"],
            "successful_tasks": self.stats["successful_tasks"],
            "failed_tasks": self.stats["failed_tasks"],
            "sent_to_success_queue": self.stats["sent_to_success_queue"],
            "failed_to_send_success": self.stats["failed_to_send_success"],
            "sync_requests_sent": self.stats["sync_requests_sent"],
            "sync_requests_failed": self.stats["sync_requests_failed"],
            "templates_requested": self.stats["templates_requested"],
            "templates_found": self.stats["templates_found"],
            "templates_not_found": self.stats["templates_not_found"],
            "templates_api_errors": self.stats["templates_api_errors"],
            "success_rate": (
                self.stats["successful_tasks"] / self.stats["total_messages"] * 100
                if self.stats["total_messages"] > 0 else 0
            ),
            "success_queue_rate": (
                self.stats["sent_to_success_queue"] / self.stats["successful_tasks"] * 100
                if self.stats["successful_tasks"] > 0 else 0
            ),
            "sync_success_rate": (
                self.stats["sync_requests_sent"] / (self.stats["sync_requests_sent"] + self.stats["sync_requests_failed"]) * 100
                if (self.stats["sync_requests_sent"] + self.stats["sync_requests_failed"]) > 0 else 0
            ),
            "template_success_rate": (
                self.stats["templates_found"] / self.stats["templates_requested"] * 100
                if self.stats["templates_requested"] > 0 else 0
            ),
            "questionnaires_found": self.stats["questionnaires_found"],
            "questionnaires_sent": self.stats["questionnaires_sent"],
            "questionnaires_failed": self.stats["questionnaires_failed"],
            "last_message_time": self.stats["last_message_time"],
            "publisher_stats": self.publisher.get_stats()
        }
        
        
        return base_stats
    
    def _extract_template_params(self, message_data: Dict[str, Any]) -> tuple:
        """
        Извлечение параметров для запроса к API шаблонов задач
        
        Args:
            message_data: Данные сообщения из RabbitMQ
            
        Returns:
            Кортеж (camunda_process_id, element_id, diagram_id) или (None, None, None) если не найдены
        """
        # Извлечение camunda_process_id (processDefinitionKey)
        camunda_process_id = (
            message_data.get('processDefinitionKey') or 
            message_data.get('process_definition_key')
        )
        
        # Извлечение element_id (activityId)
        # Приоритет: message_data['activity_id'] → metadata.activityInfo.id
        element_id = message_data.get('activity_id')
        
        if not element_id:
            metadata = message_data.get('metadata', {})
            activity_info = metadata.get('activityInfo', {})
            element_id = activity_info.get('id')

        # Попытка извлечь diagramId непосредственно из сообщения
        diagram_id = (
            message_data.get('diagramId') or
            message_data.get('diagram_id')
        )
        if not diagram_id:
            metadata = message_data.get('metadata', {})
            process_properties = metadata.get('processProperties', {})
            diagram_id = (
                process_properties.get('diagramId') or
                process_properties.get('diagram_id') or
                process_properties.get('diagramID')
            )
        if not diagram_id:
            metadata = message_data.get('metadata', {})
            diagram_meta = metadata.get('diagram', {})
            diagram_id = diagram_meta.get('id') or diagram_meta.get('ID')
        
        # Логирование при отсутствии параметров
        if not camunda_process_id:
            logger.warning("Не найден processDefinitionKey/process_definition_key в сообщении")
            logger.debug(f"Доступные поля в message_data: {list(message_data.keys())}")
        
        if not element_id:
            logger.warning("Не найден activity_id в сообщении (ни в корне, ни в metadata.activityInfo.id)")
            logger.debug(f"Доступные поля в metadata: {list(message_data.get('metadata', {}).keys())}")
        
        if not diagram_id:
            logger.debug("diagramId не найден в message_data/metadata при первичном извлечении")
        
        return (camunda_process_id, element_id, diagram_id)
    
    def _get_task_template(
        self,
        camunda_process_id: str,
        element_id: str,
        template_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Получение шаблона задачи из Bitrix24 через REST API
        
        Args:
            camunda_process_id: ID процесса Camunda (processDefinitionKey)
            element_id: ID элемента диаграммы (activityId)
            template_id: Необязательный TEMPLATE_ID из responsible API
            
        Returns:
            Словарь с данными шаблона (result.data) или None при ошибке
        """
        self.stats["templates_requested"] += 1
        
        try:
            api_url = f"{self.config.webhook_url.rstrip('/')}/imena.camunda.tasktemplate.get"
            params = {
                'camundaProcessId': camunda_process_id,
                'elementId': element_id
            }
            
            logger.debug(f"Запрос шаблона задачи: camundaProcessId={camunda_process_id}, elementId={element_id}")
            
            response = requests.get(
                api_url,
                params=params,
                timeout=self.config.request_timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            template_data = self._parse_task_template_response(result)
            if template_data:
                self.stats["templates_found"] += 1
                return template_data
            
            # Если не нашли, пробуем напрямую по TEMPLATE_ID
            if template_id:
                logger.warning(
                    f"Повторный запрос шаблона по TEMPLATE_ID={template_id} "
                    f"(camundaProcessId={camunda_process_id}, elementId={element_id})"
                )
                params = {'templateId': template_id}
                response = requests.get(
                    api_url,
                    params=params,
                    timeout=self.config.request_timeout
                )
                response.raise_for_status()
                result = response.json()
                template_data = self._parse_task_template_response(result)
                if template_data:
                    self.stats["templates_found"] += 1
                    return template_data
            
            self.stats["templates_not_found"] += 1
            return None
                
        except requests.exceptions.Timeout:
            self.stats["templates_api_errors"] += 1
            logger.error(f"Таймаут запроса к API шаблонов (timeout={self.config.request_timeout}s)")
            return None
        except requests.exceptions.RequestException as e:
            self.stats["templates_api_errors"] += 1
            logger.error(f"Ошибка запроса к API шаблонов: {e}")
            return None
        except json.JSONDecodeError as e:
            self.stats["templates_api_errors"] += 1
            logger.error(f"Ошибка декодирования JSON ответа от API шаблонов: {e}")
            return None
        except Exception as e:
            self.stats["templates_api_errors"] += 1
            logger.error(f"Неожиданная ошибка при запросе шаблона: {e}")
            return None
    
    def _parse_task_template_response(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Унифицированный парсер ответа imena.camunda.tasktemplate.get
        """
        if 'result' not in result:
            self.stats["templates_api_errors"] += 1
            logger.error("Неожиданный формат ответа API: отсутствует поле 'result'")
            logger.debug(f"Ответ API: {json.dumps(result, ensure_ascii=False, indent=2)}")
            return None
        
        api_result = result['result']
        if api_result.get('success'):
            template_data = api_result.get('data')
            if template_data:
                logger.info(f"Шаблон задачи найден: templateId={template_data.get('meta', {}).get('templateId', 'N/A')}")
                return template_data
            else:
                logger.warning("Шаблон не найден: success=True, но data отсутствует")
                return None
        else:
            error_msg = api_result.get('error', 'Unknown error')
            logger.warning(f"Шаблон не найден: {error_msg}")
            return None
    
    def _get_user_supervisor(self, user_id: int) -> Optional[int]:
        """
        Получение ID руководителя пользователя из Bitrix24 через REST API
        
        Args:
            user_id: ID пользователя Bitrix24
            
        Returns:
            ID руководителя (int) или None, если не найден или произошла ошибка
        """
        if not user_id or user_id <= 0:
            logger.warning(f"Некорректный user_id для запроса руководителя: {user_id}")
            return None
        
        try:
            api_url = f"{self.config.webhook_url.rstrip('/')}/imena.camunda.user.supervisor.get"
            params = {
                'userId': user_id
            }
            
            logger.debug(f"Запрос руководителя пользователя: userId={user_id}")
            
            response = requests.get(
                api_url,
                params=params,
                timeout=self.config.request_timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Bitrix24 API оборачивает ответ в поле 'result'
            if 'result' in result:
                api_result = result['result']
                
                if api_result.get('success'):
                    data = api_result.get('data', {})
                    supervisor_id = data.get('supervisorId')
                    
                    if supervisor_id is not None:
                        try:
                            supervisor_id_int = int(supervisor_id)
                            if supervisor_id_int > 0:
                                logger.debug(f"Руководитель найден для userId={user_id}: supervisorId={supervisor_id_int}")
                                return supervisor_id_int
                            else:
                                logger.debug(f"Руководитель не найден для userId={user_id}: supervisorId={supervisor_id}")
                                return None
                        except (ValueError, TypeError):
                            logger.warning(f"Некорректный supervisorId в ответе API: {supervisor_id}")
                            return None
                    else:
                        # Руководитель не найден - это нормальная ситуация, логируем только в debug
                        logger.debug(f"Руководитель не найден для userId={user_id}: supervisorId=null")
                        return None
                else:
                    error_msg = api_result.get('error', 'Unknown error')
                    logger.warning(f"Ошибка получения руководителя для userId={user_id}: {error_msg}")
                    logger.debug(f"Полный ответ API при ошибке: {json.dumps(api_result, ensure_ascii=False, indent=2)}")
                    return None
            else:
                logger.error(f"Неожиданный формат ответа API руководителя: отсутствует поле 'result'")
                logger.debug(f"Ответ API: {json.dumps(result, ensure_ascii=False, indent=2)}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Таймаут запроса к API руководителя для userId={user_id} (timeout={self.config.request_timeout}s)")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса к API руководителя для userId={user_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON ответа от API руководителя для userId={user_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе руководителя для userId={user_id}: {e}")
            return None
    
    def _check_required_user_field(self) -> None:
        """
        КРИТИЧЕСКАЯ ПРОВЕРКА: Проверяет существование всех обязательных пользовательских полей
        для объекта TASKS_TASK в Bitrix24.
        
        Обязательные поля:
        - UF_CAMUNDA_ID_EXTERNAL_TASK (string) - уникальный идентификатор External Task из Camunda
        - UF_RESULT_ANSWER (enumeration) - ответ пользователя на вопрос задачи
        - UF_RESULT_QUESTION (string) - вопрос для задачи, требующей ответа
        - UF_RESULT_EXPECTED (boolean) - флаг, требуется ли ответ от пользователя
        - UF_ELEMENT_ID (string) - ID элемента BPMN диаграммы
        - UF_PROCESS_INSTANCE_ID (string) - ID экземпляра процесса Camunda
        
        Если хотя бы одно поле отсутствует - останавливает сервис с фатальной ошибкой.
        Все поля должны быть созданы администратором вручную перед запуском сервиса.
        
        Raises:
            SystemExit: Если хотя бы одно поле не найдено - останавливает сервис
        """
        # Список обязательных полей с их ожидаемыми типами
        required_fields = {
            "UF_CAMUNDA_ID_EXTERNAL_TASK": {
                "type": "string",
                "description": "Уникальный идентификатор External Task из Camunda"
            },
            "UF_RESULT_ANSWER": {
                "type": "enumeration",
                "description": "Ответ пользователя на вопрос задачи"
            },
            "UF_RESULT_QUESTION": {
                "type": "string",
                "description": "Вопрос для задачи, требующей ответа"
            },
            "UF_RESULT_EXPECTED": {
                "type": "boolean",
                "description": "Флаг, требуется ли ответ от пользователя"
            },
            "UF_ELEMENT_ID": {
                "type": "string",
                "description": "ID элемента BPMN диаграммы (activityId)"
            },
            "UF_PROCESS_INSTANCE_ID": {
                "type": "string",
                "description": "ID экземпляра процесса Camunda (для связи задач одного экземпляра)"
            }
        }
        
        try:
            logger.info("Проверка существования обязательных пользовательских полей в Bitrix24...")
            logger.info(f"Ожидаемые поля: {', '.join(required_fields.keys())}")
            
            user_fields = None
            
            # Пробуем использовать API через webhook (как в userfield_sync.py)
            # Метод: imena.camunda.userfield.list
            try:
                api_url = f"{self.config.webhook_url}/imena.camunda.userfield.list"
                logger.debug(f"Попытка проверки через webhook API: {api_url}")
                
                response = requests.get(api_url, timeout=self.config.request_timeout)
                response.raise_for_status()
                result = response.json()
                
                # Проверяем наличие ошибок
                if 'error' in result:
                    logger.warning(f"Webhook API вернул ошибку: {result.get('error', {}).get('error_description', 'Unknown error')}")
                    raise requests.exceptions.RequestException("Webhook API error")
                
                # Извлекаем список полей
                api_data = result.get('result', {})
                user_fields = api_data.get('userFields', [])
                logger.debug(f"Получено {len(user_fields)} полей через webhook API")
                
            except (requests.exceptions.RequestException, KeyError) as e:
                logger.warning(f"Не удалось получить поля через webhook API: {e}")
                logger.info("Попытка использовать прямой API файл...")
                
                # Fallback: используем прямой API файл
                # Извлекаем базовый домен из webhook URL
                try:
                    from urllib.parse import urlparse
                    webhook_parsed = urlparse(self.config.webhook_url)
                    base_domain = f"{webhook_parsed.scheme}://{webhook_parsed.netloc}"
                    direct_api_url = f"{base_domain}/local/modules/imena.camunda/lib/UserFields/userfields_api.php?api=1&method=list"
                    
                    logger.debug(f"Попытка проверки через прямой API файл: {direct_api_url}")
                    
                    response = requests.get(direct_api_url, timeout=self.config.request_timeout, verify=False)
                    response.raise_for_status()
                    result = response.json()
                    
                    if result.get('status') == 'success':
                        api_data = result.get('data', {})
                        user_fields = api_data.get('userFields', [])
                        logger.debug(f"Получено {len(user_fields)} полей через прямой API файл")
                    else:
                        raise requests.exceptions.RequestException("Direct API returned error")
                        
                except Exception as e2:
                    logger.error(f"Не удалось получить поля через прямой API файл: {e2}")
                    raise
            
            if user_fields is None or len(user_fields) == 0:
                logger.error("=" * 80)
                logger.error("ФАТАЛЬНАЯ ОШИБКА: Не удалось получить список полей из Bitrix24!")
                logger.error("=" * 80)
                logger.error("")
                logger.error("ДЕЙСТВИЯ:")
                logger.error("1. Проверьте доступность Bitrix24 API")
                logger.error("2. Проверьте правильность BITRIX_WEBHOOK_URL в конфигурации")
                logger.error("3. Убедитесь, что модуль imena.camunda установлен и активен")
                logger.error("4. Перезапустите сервис после исправления")
                logger.error("")
                raise SystemExit(1)
            
            # Создаем словарь найденных полей для быстрого поиска
            found_fields = {}
            for field in user_fields:
                field_name = field.get('FIELD_NAME')
                if field_name:
                    found_fields[field_name] = {
                        'ID': field.get('ID', 'unknown'),
                        'USER_TYPE_ID': field.get('USER_TYPE_ID', 'unknown'),
                        'field_data': field
                    }
            
            # Проверяем каждое обязательное поле
            missing_fields = []
            incorrect_type_fields = []
            
            for field_name, field_info in required_fields.items():
                expected_type = field_info['type']
                description = field_info['description']
                
                if field_name not in found_fields:
                    missing_fields.append({
                        'name': field_name,
                        'type': expected_type,
                        'description': description
                    })
                else:
                    actual_type = found_fields[field_name]['USER_TYPE_ID']
                    field_id = found_fields[field_name]['ID']
                    
                    # Проверяем соответствие типа (с учетом возможных вариантов)
                    type_mapping = {
                        'string': ['string', 'text'],
                        'enumeration': ['enumeration', 'enum'],
                        'boolean': ['boolean', 'bool']
                    }
                    
                    expected_types = type_mapping.get(expected_type, [expected_type])
                    if actual_type.lower() not in [t.lower() for t in expected_types]:
                        incorrect_type_fields.append({
                            'name': field_name,
                            'expected': expected_type,
                            'actual': actual_type,
                            'id': field_id
                        })
                        logger.warning(f"⚠️  Поле {field_name} найдено, но имеет неверный тип: ожидается '{expected_type}', фактически '{actual_type}' (ID: {field_id})")
                    else:
                        logger.info(f"✅ Поле {field_name} найдено (ID: {field_id}, тип: {actual_type}) - {description}")
            
            # Если есть отсутствующие поля или поля с неверным типом - останавливаем сервис
            if missing_fields or incorrect_type_fields:
                logger.error("=" * 80)
                logger.error("ФАТАЛЬНАЯ ОШИБКА: Обязательные поля отсутствуют или имеют неверный тип!")
                logger.error("=" * 80)
                logger.error("")
                
                if missing_fields:
                    logger.error("ОТСУТСТВУЮЩИЕ ПОЛЯ:")
                    for field in missing_fields:
                        logger.error(f"  ❌ {field['name']} (тип: {field['type']})")
                        logger.error(f"     Описание: {field['description']}")
                    logger.error("")
                
                if incorrect_type_fields:
                    logger.error("ПОЛЯ С НЕВЕРНЫМ ТИПОМ:")
                    for field in incorrect_type_fields:
                        logger.error(f"  ⚠️  {field['name']} (ID: {field['id']})")
                        logger.error(f"     Ожидается: {field['expected']}, фактически: {field['actual']}")
                    logger.error("")
                
                logger.error("ДЕЙСТВИЯ:")
                logger.error("1. Создайте отсутствующие пользовательские поля в Bitrix24:")
                logger.error("   Объект: Задачи (TASKS_TASK)")
                logger.error("")
                
                for field in missing_fields:
                    logger.error(f"   - {field['name']}:")
                    logger.error(f"     * Тип: {field['type']}")
                    logger.error(f"     * Описание: {field['description']}")
                    if field['name'] == 'UF_CAMUNDA_ID_EXTERNAL_TASK':
                        logger.error("     * Обязательное: Нет (но должно быть уникальным)")
                    logger.error("")
                
                if incorrect_type_fields:
                    logger.error("2. Исправьте типы полей с неверным типом:")
                    for field in incorrect_type_fields:
                        logger.error(f"   - {field['name']}: измените тип с '{field['actual']}' на '{field['expected']}'")
                    logger.error("")
                
                logger.error("3. Перезапустите сервис после создания/исправления полей")
                logger.error("4. Только после этого сервис сможет корректно работать")
                logger.error("")
                logger.error("БЕЗ ВСЕХ ОБЯЗАТЕЛЬНЫХ ПОЛЕЙ СЕРВИС НЕ МОЖЕТ РАБОТАТЬ КОРРЕКТНО!")
                logger.error("=" * 80)
                raise SystemExit(1)
            
            logger.info("✅ Все обязательные пользовательские поля найдены и имеют корректные типы")
                
        except requests.exceptions.RequestException as e:
            logger.error("=" * 80)
            logger.error("ФАТАЛЬНАЯ ОШИБКА: Не удалось подключиться к Bitrix24 API!")
            logger.error("=" * 80)
            logger.error("")
            logger.error(f"Ошибка подключения: {e}")
            logger.error("")
            logger.error("ДЕЙСТВИЯ:")
            logger.error("1. Проверьте доступность Bitrix24")
            logger.error("2. Проверьте правильность BITRIX_WEBHOOK_URL в конфигурации")
            logger.error("3. Убедитесь, что API метод imena.camunda.userfield.list доступен")
            logger.error("4. Перезапустите сервис после исправления")
            logger.error("")
            raise SystemExit(1)
        except SystemExit:
            # Пробрасываем SystemExit дальше
            raise
        except Exception as e:
            logger.error("=" * 80)
            logger.error("ФАТАЛЬНАЯ ОШИБКА: Неожиданная ошибка при проверке обязательных полей!")
            logger.error("=" * 80)
            logger.error("")
            logger.error(f"Ошибка: {e}")
            logger.error("")
            logger.error("ДЕЙСТВИЯ:")
            logger.error("1. Проверьте логи для деталей")
            logger.error("2. Убедитесь, что все обязательные поля созданы в Bitrix24:")
            logger.error("   - UF_CAMUNDA_ID_EXTERNAL_TASK (string)")
            logger.error("   - UF_RESULT_ANSWER (enumeration)")
            logger.error("   - UF_RESULT_QUESTION (string)")
            logger.error("   - UF_RESULT_EXPECTED (boolean)")
            logger.error("   - UF_ELEMENT_ID (string)")
            logger.error("   - UF_PROCESS_INSTANCE_ID (string)")
            logger.error("3. Перезапустите сервис после исправления")
            logger.error("")
            raise SystemExit(1)
    
    def _find_task_by_external_id(self, external_task_id: str) -> Optional[Dict[str, Any]]:
        """
        Поиск задачи в Bitrix24 по External Task ID
        
        Args:
            external_task_id: External Task ID из Camunda
            
        Returns:
            Данные задачи если найдена, None если не найдена
        """
        try:
            # Используем tasks.task.list с фильтром по пользовательскому полю
            url = f"{self.config.webhook_url}/tasks.task.list.json"
            params = {
                "filter": {
                    "UF_CAMUNDA_ID_EXTERNAL_TASK": external_task_id
                },
                "select": ["*", "UF_*"]  # Выбираем все поля включая пользовательские
            }
            
            response = requests.post(url, json=params, timeout=self.config.request_timeout)
            
            if response.status_code == 200:
                result = response.json()
                tasks = result.get('result', {}).get('tasks', [])
                
                if tasks:
                    # Задача найдена
                    logger.debug(f"Найдена существующая задача в Bitrix24: ID={tasks[0]['id']}, External Task ID={external_task_id}")
                    return tasks[0]
            
            logger.debug(f"Задача с External Task ID {external_task_id} не найдена в Bitrix24")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка поиска задачи по External Task ID {external_task_id}: {e}")
            # При ошибке поиска возвращаем None - лучше создать дубль, чем не создать задачу
            return None
    
    def cleanup(self):
        """Очистка ресурсов при завершении работы"""
        try:
            if hasattr(self, 'publisher') and self.publisher:
                self.publisher.disconnect()
                logger.info("Publisher отключен при очистке ресурсов BitrixTaskHandler")
        except Exception as e:
            logger.error(f"Ошибка при очистке ресурсов BitrixTaskHandler: {e}") 