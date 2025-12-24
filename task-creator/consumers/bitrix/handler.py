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
from .utils import format_process_variable_value, get_camunda_int, get_camunda_datetime
from .clients import BitrixAPIClient
from .services import ChecklistService, DiagramService, FileService, PredecessorService, QuestionnaireService, SyncService, TemplateService, UserService
from .validators import FieldValidator
from rabbitmq_publisher import RabbitMQPublisher


class BitrixTaskHandler:
    """Обработчик для создания задач в Bitrix24"""
    
    def __init__(self):
        self.config = bitrix_config
        self.worker_config = worker_config

        # Клиент для работы с API Bitrix24
        self.bitrix_client = BitrixAPIClient(
            webhook_url=self.config.webhook_url,
            request_timeout=self.config.request_timeout
        )

        # Сервис для работы с чек-листами
        self.checklist_service = ChecklistService(self.bitrix_client)

        # Сервис для работы с диаграммами
        self.diagram_service = DiagramService(config=self.config)

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

        # Сервис для работы с анкетами (инициализируется после stats)
        self.questionnaire_service = QuestionnaireService(
            bitrix_client=self.bitrix_client,
            config=self.config,
            stats=self.stats
        )

        # Сервис для работы с файлами
        self.file_service = FileService(
            config=self.config,
            stats=self.stats
        )

        # Кэш предшественников и задач
        self.element_predecessors_cache: Dict[Tuple[Optional[str], Optional[str], str], List[str]] = {}
        self.responsible_cache: Dict[Tuple[Optional[str], Optional[str], str], Optional[Dict[str, Any]]] = {}
        # Кэш задач по element_id и process_instance_id: ключ = (element_id, process_instance_id)
        self.element_task_cache: Dict[Tuple[Optional[str], Optional[str]], Dict[str, Any]] = {}

        # Сервис для работы с пользователями (инициализируется после responsible_cache)
        self.user_service = UserService(
            config=self.config,
            responsible_cache=self.responsible_cache
        )

        # Сервис для синхронизации и отправки сообщений в RabbitMQ
        self.sync_service = SyncService(
            config=self.config,
            stats=self.stats,
            publisher=self.publisher
        )

        # Сервис для работы с предшественниками (инициализируется после user_service и кэшей)
        self.predecessor_service = PredecessorService(
            config=self.config,
            stats=self.stats,
            user_service=self.user_service,
            element_predecessors_cache=self.element_predecessors_cache,
            element_task_cache=self.element_task_cache
        )

        # Сервис для работы с шаблонами задач
        self.template_service = TemplateService(
            config=self.config,
            stats=self.stats,
            user_service=self.user_service
        )

        # Валидатор полей
        self.field_validator = FieldValidator(config=self.config)

        # КРИТИЧЕСКАЯ ПРОВЕРКА: Проверяем существование обязательного поля UF_CAMUNDA_ID_EXTERNAL_TASK
        self.field_validator.check_required_fields()
    
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
                success_sent = self.sync_service.send_success_message_with_retry(message_data, result, "bitrix24.queue")
                if success_sent:
                    self.stats["sent_to_success_queue"] += 1
                else:
                    self.stats["failed_to_send_success"] += 1
                    logger.warning("Не удалось отправить результат в очередь успешных сообщений")
                
                # ОБЯЗАТЕЛЬНАЯ синхронизация (критически важно для корректной работы)
                logger.debug(f"Попытка синхронизации для задачи {task_id}, данные сообщения: {message_data}")
                sync_success = self.sync_service.send_sync_request(message_data)
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
                    self.sync_service.send_to_error_queue(message_data, error_msg)
                    # ВАЖНО: Возвращаем True чтобы сообщение было ACK'нуто и не обрабатывалось повторно
                    return True
                
                logger.error(f"Ошибка создания задачи в Bitrix24: {error_msg}")
                return False
                
        except ValueError as e:
            # Критическая ошибка с assigneeId - отправляем в очередь ошибок
            self.stats["failed_tasks"] += 1
            logger.critical(f"КРИТИЧЕСКАЯ ОШИБКА assigneeId: {e}")
            
            # Отправляем в очередь ошибок для ручного разбора
            self.sync_service.send_to_error_queue(message_data, str(e))
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
            existing_task = self.bitrix_client.find_task_by_external_id(task_id)
            
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
            camunda_process_id, element_id, diagram_id = self.template_service.extract_template_params(message_data)
            
            if not camunda_process_id or not element_id:
                logger.warning(f"Не удалось извлечь параметры для запроса шаблона (camundaProcessId={camunda_process_id}, elementId={element_id})")
                logger.warning("Переход к fallback: создание задачи с минимальными данными")
                return self._create_task_fallback(message_data)
            
            responsible_info = self.user_service.get_responsible_info(camunda_process_id, diagram_id, element_id)
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
            
            template_data = self.template_service.get_template(
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

            questionnaires_data: List[Dict[str, Any]] = self.questionnaire_service.extract_from_template(template_data)

            diagram_id = self.diagram_service.resolve_id(
                diagram_id,
                camunda_process_id,
                metadata,
                template_data
            )
            if not diagram_id and diagram_id_from_responsible:
                diagram_id = diagram_id_from_responsible
            
            # Шаг 3: Формирование task_data из шаблона
            task_data, template_files = self.template_service.build_task_data(
                template_data,
                message_data,
                task_id,
                element_id,
                user_fields_extractor=self.field_validator.extract_user_fields
            )
            if template_files:
                self.stats["template_files_found"] += len(template_files)
                logger.debug(f"Найдено {len(template_files)} файлов в шаблоне для дальнейшего прикрепления (task_id={task_id})")

            # Шаг 3.1: Обогащение описания (анкеты, переменные, результаты предшественников)
            predecessor_task_ids, predecessor_results = self._enrich_task_description(
                task_data=task_data,
                message_data=message_data,
                template_data=template_data,
                camunda_process_id=camunda_process_id,
                diagram_id=diagram_id,
                element_id=element_id,
                task_id=task_id,
                responsible_info=responsible_info
            )
            
            # Шаг 4: Создание задачи в Bitrix24
            result = self.bitrix_client.send_task(task_data)
            
            if result and result.get('error'):
                logger.error(f"Ошибка API Bitrix24 при создании задачи: {result['error']}")
                return result
            
            # Шаг 5: Пост-обработка созданной задачи
            if result and result.get('result') and result['result'].get('task'):
                created_task_id = result['result']['task'].get('id')
                if created_task_id:
                    self._post_process_created_task(
                        created_task_id=int(created_task_id),
                        template_data=template_data,
                        template_files=template_files,
                        predecessor_task_ids=predecessor_task_ids,
                        predecessor_results=predecessor_results,
                        questionnaires_data=questionnaires_data
                    )
            
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

    def _enrich_task_description(
        self,
        task_data: Dict[str, Any],
        message_data: Dict[str, Any],
        template_data: Dict[str, Any],
        camunda_process_id: str,
        diagram_id: Optional[str],
        element_id: str,
        task_id: str,
        responsible_info: Optional[Dict[str, Any]]
    ) -> Tuple[List[int], Dict[int, List[Dict[str, Any]]]]:
        """
        Обогащение описания задачи дополнительными блоками

        Добавляет в описание:
        - Блок анкет (questionnairesInDescription)
        - Блок переменных процесса
        - Блок результатов предшественников

        Args:
            task_data: Данные задачи (модифицируется in-place)
            message_data: Исходные данные сообщения
            template_data: Данные шаблона
            camunda_process_id: ID процесса Camunda
            diagram_id: ID диаграммы Storm
            element_id: ID элемента BPMN
            task_id: ID внешней задачи
            responsible_info: Информация об ответственном

        Returns:
            Tuple[predecessor_task_ids, predecessor_results]
        """
        metadata = message_data.get('metadata', {})

        # Блок анкет (questionnairesInDescription)
        qid_data = self.questionnaire_service.extract_for_description(template_data)
        if qid_data:
            process_variables = self._extract_process_variables(message_data)
            questionnaires_block = self.questionnaire_service.build_description_block(
                qid_data,
                process_variables,
                element_id
            )
            if questionnaires_block:
                self._append_description_block(task_data, questionnaires_block)
                logger.debug(f"Добавлен блок анкет (questionnairesInDescription) в описание задачи {task_id}")

        # Блок переменных процесса
        variables_block = self.diagram_service.build_process_variables_block(message_data, camunda_process_id, task_id)
        if variables_block:
            self._append_description_block(task_data, variables_block)
            logger.debug(f"Добавлен блок переменных процесса в описание задачи {task_id}")

        # Предшественники и их результаты
        process_instance_id = message_data.get('processInstanceId') or message_data.get('process_instance_id')
        predecessor_task_ids = self.predecessor_service.apply_dependencies(
            task_data,
            camunda_process_id,
            diagram_id,
            element_id,
            responsible_info=responsible_info,
            process_instance_id=process_instance_id
        )

        predecessor_results: Dict[int, List[Dict[str, Any]]] = {}
        if predecessor_task_ids:
            predecessor_results = self.predecessor_service.get_predecessor_results(predecessor_task_ids)
            if predecessor_results:
                results_block = self.predecessor_service.build_results_block(predecessor_results)
                if results_block:
                    self._append_description_block(task_data, results_block)
                    logger.debug(f"Добавлен блок результатов предшественников в описание задачи {task_id}")

        return predecessor_task_ids, predecessor_results

    def _extract_process_variables(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Извлечение переменных процесса из message_data"""
        metadata = message_data.get('metadata') or {}
        if isinstance(metadata, dict):
            pv_from_metadata = metadata.get('processVariables')
            if isinstance(pv_from_metadata, dict):
                return pv_from_metadata
        pv_direct = message_data.get('process_variables')
        if isinstance(pv_direct, dict):
            return pv_direct
        return {}

    def _append_description_block(self, task_data: Dict[str, Any], block: str) -> None:
        """Добавление блока текста в описание задачи"""
        current_description = task_data.get('DESCRIPTION', '') or ''
        if current_description:
            task_data['DESCRIPTION'] = f"{current_description.rstrip()}\n\n---\n{block}"
        else:
            task_data['DESCRIPTION'] = block

    def _post_process_created_task(
        self,
        created_task_id: int,
        template_data: Dict[str, Any],
        template_files: List[Dict[str, Any]],
        predecessor_task_ids: List[int],
        predecessor_results: Dict[int, List[Dict[str, Any]]],
        questionnaires_data: List[Dict[str, Any]]
    ) -> None:
        """
        Пост-обработка после создания задачи в Bitrix24

        Выполняет:
        - Прикрепление файлов из шаблона
        - Создание зависимостей между задачами
        - Прикрепление файлов предшественников
        - Добавление анкет к задаче
        - Создание чек-листов

        Args:
            created_task_id: ID созданной задачи в Bitrix24
            template_data: Данные шаблона
            template_files: Файлы из шаблона
            predecessor_task_ids: ID задач-предшественников
            predecessor_results: Результаты предшественников
            questionnaires_data: Данные анкет
        """
        # Прикрепление файлов из шаблона
        if template_files:
            try:
                self.file_service.attach_template_files(created_task_id, template_files)
            except Exception as e:
                logger.error(f"Ошибка прикрепления файлов шаблона к задаче {created_task_id}: {e}")

        # Создание зависимостей через кастомный REST API
        try:
            self.predecessor_service.create_dependencies(created_task_id, predecessor_task_ids)
        except Exception as e:
            logger.error(f"Ошибка создания зависимостей для задачи {created_task_id}: {e}")

        # Прикрепление файлов из результатов предшествующих задач
        if predecessor_results:
            try:
                self.file_service.attach_predecessor_files(created_task_id, predecessor_results)
            except Exception as e:
                logger.error(f"Ошибка прикрепления файлов предшественников к задаче {created_task_id}: {e}")

        # Добавление анкет
        if questionnaires_data:
            try:
                logger.info(f"Добавление {len(questionnaires_data)} анкет в задачу {created_task_id}")
                success = self.questionnaire_service.add_to_task(created_task_id, questionnaires_data)
                if success:
                    logger.info(f"Анкеты успешно добавлены к задаче {created_task_id}")
                else:
                    logger.warning(f"Анкеты не были добавлены к задаче {created_task_id}")
            except Exception as e:
                logger.error(f"Ошибка добавления анкет к задаче {created_task_id}: {e}")

        # Создание чек-листов
        checklists_data = self.checklist_service.extract_from_template(template_data)
        if checklists_data:
            logger.info(f"Создание чек-листов для задачи {created_task_id}")
            try:
                success = self.checklist_service.create_checklists_sync(created_task_id, checklists_data)
                if success:
                    logger.info(f"Чек-листы успешно созданы для задачи {created_task_id}")
                else:
                    logger.warning(f"Не все чек-листы созданы для задачи {created_task_id}")
            except Exception as e:
                logger.error(f"Ошибка создания чек-листов для задачи {created_task_id}: {e}")
        else:
            logger.debug(f"Нет данных чек-листов для задачи {created_task_id}")

    def _build_fallback_task_data(
        self,
        message_data: Dict[str, Any],
        task_id: str,
        element_id: Optional[str],
        camunda_process_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        Построение данных задачи для fallback режима (без шаблона)

        Args:
            message_data: Данные сообщения из RabbitMQ
            task_id: ID внешней задачи Camunda
            element_id: ID элемента BPMN
            camunda_process_id: ID процесса Camunda

        Returns:
            Словарь с данными задачи для Bitrix24 API
        """
        metadata = message_data.get('metadata', {})
        activity_info = metadata.get('activityInfo', {})
        variables = message_data.get('variables') or {}

        # TITLE
        title = activity_info.get('name')
        if not title:
            topic = message_data.get('topic', 'unknown')
            title = f'Задача из Camunda процесса ({topic})'

        # DESCRIPTION с блоком переменных
        description = title
        variables_block = self.diagram_service.build_process_variables_block(message_data, camunda_process_id, task_id)
        if variables_block:
            description = f"{description.rstrip()}\n\n---\n{variables_block}" if description else variables_block

        # CREATED_BY и RESPONSIBLE_ID
        created_by, responsible_id = self._resolve_fallback_user_ids(variables)

        task_data = {
            'TITLE': title,
            'DESCRIPTION': description,
            'RESPONSIBLE_ID': responsible_id,
            'PRIORITY': self.config.default_priority,
            'CREATED_BY': created_by,
            'UF_CAMUNDA_ID_EXTERNAL_TASK': task_id
        }

        # Опциональные поля
        self._apply_fallback_optional_fields(task_data, message_data, variables, metadata, element_id)

        return task_data

    def _resolve_fallback_user_ids(self, variables: Dict[str, Any]) -> Tuple[int, int]:
        """Определение CREATED_BY и RESPONSIBLE_ID для fallback режима"""
        created_by = 1
        responsible_id = 1
        started_by = variables.get('startedBy')

        if started_by:
            try:
                if isinstance(started_by, dict) and 'value' in started_by:
                    initiator_id_int = int(started_by['value'])
                else:
                    initiator_id_int = int(started_by)
                created_by = initiator_id_int
                responsible_id = initiator_id_int
                logger.debug(f"Fallback: используем startedBy как CREATED_BY и RESPONSIBLE_ID: {initiator_id_int}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Некорректный startedBy: {started_by}, используем значение по умолчанию 1: {e}")

        return created_by, responsible_id

    def _apply_fallback_optional_fields(
        self,
        task_data: Dict[str, Any],
        message_data: Dict[str, Any],
        variables: Dict[str, Any],
        metadata: Dict[str, Any],
        element_id: Optional[str]
    ) -> None:
        """Применение опциональных полей к task_data в fallback режиме"""
        task_id = task_data.get('UF_CAMUNDA_ID_EXTERNAL_TASK', 'unknown')

        # GROUP_ID
        group_id = get_camunda_int(variables, 'groupId')
        if group_id:
            task_data['GROUP_ID'] = group_id
            logger.debug(f"Fallback: GROUP_ID={group_id}")

        # PARENT_ID (подзадача)
        parent_task_id = get_camunda_int(variables, 'parentTaskId')
        if parent_task_id:
            task_data['PARENT_ID'] = parent_task_id
            task_data['SUBORDINATE'] = 'Y'
            logger.debug(f"Fallback: подзадача родителя {parent_task_id}")

        # DEADLINE
        process_deadline = get_camunda_datetime(variables, 'deadline')
        if process_deadline:
            task_data['DEADLINE'] = process_deadline.strftime('%Y-%m-%d %H:%M:%S')
            logger.debug(f"Fallback: DEADLINE={task_data['DEADLINE']}")

        # Пользовательские поля из метаданных
        user_fields = self.field_validator.extract_user_fields(metadata)
        if user_fields:
            task_data.update(user_fields)
            logger.debug(f"Fallback: добавлены UF поля: {list(user_fields.keys())}")

        # UF_ELEMENT_ID
        if element_id:
            task_data['UF_ELEMENT_ID'] = element_id

        # UF_PROCESS_INSTANCE_ID
        process_instance_id = message_data.get('processInstanceId') or message_data.get('process_instance_id')
        if process_instance_id:
            task_data['UF_PROCESS_INSTANCE_ID'] = str(process_instance_id)
        else:
            logger.warning(f"Fallback: processInstanceId не найден для задачи {task_id}")

        # AUDITORS
        diagram_owner_id = get_camunda_int(variables, 'diagramOwner')
        if diagram_owner_id:
            task_data['AUDITORS'] = [diagram_owner_id]
            logger.debug(f"Fallback: AUDITORS=[{diagram_owner_id}]")

    def _resolve_fallback_diagram_id(
        self,
        diagram_id: Optional[str],
        camunda_process_id: Optional[str],
        metadata: Dict[str, Any],
        responsible_info: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """Определение diagram_id для fallback режима"""
        diagram_id_from_responsible = None
        if responsible_info:
            diagram_id_from_responsible = (
                responsible_info.get('DIAGRAM_ID') or
                responsible_info.get('diagramId')
            )

        resolved_id = self.diagram_service.resolve_id(diagram_id, camunda_process_id, metadata, None)
        if not resolved_id and diagram_id_from_responsible:
            resolved_id = diagram_id_from_responsible

        return resolved_id

    def _process_fallback_predecessors(
        self,
        task_data: Dict[str, Any],
        camunda_process_id: Optional[str],
        diagram_id: Optional[str],
        element_id: Optional[str],
        responsible_info: Optional[Dict[str, Any]],
        process_instance_id: Optional[str]
    ) -> Tuple[List[int], Dict[int, List[Dict[str, Any]]]]:
        """Обработка предшественников для fallback режима"""
        predecessor_task_ids = self.predecessor_service.apply_dependencies(
            task_data,
            camunda_process_id,
            diagram_id,
            element_id,
            responsible_info=responsible_info,
            process_instance_id=process_instance_id
        )

        predecessor_results: Dict[int, List[Dict[str, Any]]] = {}
        if predecessor_task_ids:
            predecessor_results = self.predecessor_service.get_predecessor_results(predecessor_task_ids)
            if predecessor_results:
                results_block = self.predecessor_service.build_results_block(predecessor_results)
                if results_block:
                    self._append_description_block(task_data, results_block)
                    logger.debug("Fallback: Добавлен блок результатов предшественников")

        return predecessor_task_ids, predecessor_results

    def _post_process_fallback_task(
        self,
        created_task_id: int,
        predecessor_task_ids: List[int],
        predecessor_results: Dict[int, List[Dict[str, Any]]]
    ) -> None:
        """Пост-обработка созданной задачи в fallback режиме"""
        # Создание зависимостей
        try:
            self.predecessor_service.create_dependencies(created_task_id, predecessor_task_ids)
        except Exception as e:
            logger.error(f"Ошибка создания зависимостей (fallback) для задачи {created_task_id}: {e}")

        # Прикрепление файлов предшественников
        if predecessor_results:
            try:
                self.file_service.attach_predecessor_files(created_task_id, predecessor_results)
            except Exception as e:
                logger.error(f"Ошибка прикрепления файлов предшественников (fallback) к задаче {created_task_id}: {e}")

    def _create_task_fallback(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Создание задачи с минимальными данными (fallback при отсутствии шаблона)

        Args:
            message_data: Данные сообщения из RabbitMQ

        Returns:
            Ответ от API Bitrix24
        """
        try:
            # Извлечение контекста
            task_id = message_data.get('task_id', 'unknown')
            metadata = message_data.get('metadata', {})
            camunda_process_id, element_id, diagram_id = self.template_service.extract_template_params(message_data)

            # Определение diagram_id
            responsible_info = self.user_service.get_responsible_info(camunda_process_id, diagram_id, element_id)
            diagram_id = self._resolve_fallback_diagram_id(diagram_id, camunda_process_id, metadata, responsible_info)

            # Построение task_data
            task_data = self._build_fallback_task_data(message_data, task_id, element_id, camunda_process_id)

            logger.warning(f"Создание задачи в fallback режиме: TITLE={task_data.get('TITLE')}, "
                          f"RESPONSIBLE_ID={task_data.get('RESPONSIBLE_ID')}, CREATED_BY={task_data.get('CREATED_BY')}")

            # Обработка предшественников
            process_instance_id = message_data.get('processInstanceId') or message_data.get('process_instance_id')
            predecessor_task_ids, predecessor_results = self._process_fallback_predecessors(
                task_data, camunda_process_id, diagram_id, element_id, responsible_info, process_instance_id
            )

            # Создание задачи
            result = self.bitrix_client.send_task(task_data)

            # Пост-обработка
            if result and result.get('result') and result['result'].get('task'):
                created_task_id = result['result']['task'].get('id')
                if created_task_id:
                    self._post_process_fallback_task(int(created_task_id), predecessor_task_ids, predecessor_results)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка создания задачи в fallback режиме: {e}")
            return {
                'error': 'FALLBACK_ERROR',
                'error_description': f'Ошибка создания задачи в fallback режиме: {str(e)}'
            }

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

    def cleanup(self):
        """Очистка ресурсов при завершении работы"""
        try:
            if hasattr(self, 'publisher') and self.publisher:
                self.publisher.disconnect()
                logger.info("Publisher отключен при очистке ресурсов BitrixTaskHandler")
        except Exception as e:
            logger.error(f"Ошибка при очистке ресурсов BitrixTaskHandler: {e}") 