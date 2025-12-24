"""
Сервис для работы с шаблонами задач Bitrix24

Модуль содержит класс TemplateService для управления шаблонами:
получение шаблона, извлечение параметров, формирование task_data.
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
from loguru import logger

from ..utils import get_camunda_int, get_camunda_datetime


class TemplateService:
    """
    Сервис для работы с шаблонами задач Bitrix24

    Предоставляет методы для получения шаблонов задач,
    извлечения параметров и формирования task_data.
    """

    def __init__(
        self,
        config: Any,
        stats: Dict[str, int],
        user_service: Any
    ):
        """
        Инициализация сервиса шаблонов

        Args:
            config: Конфигурация (webhook_url, request_timeout, default_priority)
            stats: Словарь статистики для обновления счётчиков
            user_service: Сервис пользователей (для get_supervisor)
        """
        self.config = config
        self.stats = stats
        self.user_service = user_service

    def extract_template_params(self, message_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Извлечение параметров для запроса к API шаблонов задач

        Args:
            message_data: Данные сообщения из RabbitMQ

        Returns:
            Кортеж (camunda_process_id, element_id, diagram_id)
        """
        # Извлечение camunda_process_id (processDefinitionKey)
        camunda_process_id = (
            message_data.get('processDefinitionKey') or
            message_data.get('process_definition_key')
        )

        # Извлечение element_id (activityId)
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

    def get_template(
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

            template_data = self._parse_template_response(result)
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
                template_data = self._parse_template_response(result)
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

    def _parse_template_response(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Унифицированный парсер ответа imena.camunda.tasktemplate.get

        Args:
            result: Ответ от API

        Returns:
            Данные шаблона или None
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

    def build_task_data(
        self,
        template_data: Dict[str, Any],
        message_data: Dict[str, Any],
        task_id: str,
        element_id: Optional[str] = None,
        user_fields_extractor: Any = None
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Формирование task_data из шаблона задачи

        Args:
            template_data: Данные шаблона из API (result.data)
            message_data: Исходные данные сообщения
            task_id: External Task ID
            element_id: BPMN elementId, используется для UF_ELEMENT_ID
            user_fields_extractor: Функция для извлечения пользовательских полей

        Returns:
            Кортеж (task_data, template_files)
        """
        template = template_data.get('template', {})
        template_files = template_data.get('files') or []
        members = template_data.get('members', {})
        tags = template_data.get('tags', [])
        metadata = message_data.get('metadata', {})
        variables = message_data.get('variables') or {}
        parent_task_id = get_camunda_int(variables, 'parentTaskId')
        diagram_owner_id = get_camunda_int(variables, 'diagramOwner')
        group_id_from_variables = get_camunda_int(variables, 'groupId')

        # Определение инициатора процесса
        initiator_id = self._extract_initiator_id(variables)

        # Отладочная информация
        logger.debug(f"Данные для формирования task_data:")
        logger.debug(f"  template.RESPONSIBLE_ID: {template.get('RESPONSIBLE_ID')}")
        logger.debug(f"  template.CREATED_BY: {template.get('CREATED_BY')}")
        logger.debug(f"  members.by_type.R: {members.get('by_type', {}).get('R', [])}")
        logger.debug(f"  initiator_id (используется): {initiator_id}")

        task_data: Dict[str, Any] = {}

        # Основные поля из шаблона
        if template.get('TITLE'):
            task_data['TITLE'] = template['TITLE']

        if template.get('DESCRIPTION'):
            task_data['DESCRIPTION'] = template['DESCRIPTION']

        # PRIORITY
        priority = template.get('PRIORITY')
        if priority:
            try:
                task_data['PRIORITY'] = int(priority)
            except (ValueError, TypeError):
                task_data['PRIORITY'] = self.config.default_priority
        else:
            task_data['PRIORITY'] = self.config.default_priority

        # GROUP_ID
        group_id = template.get('GROUP_ID')
        if group_id:
            try:
                task_data['GROUP_ID'] = int(group_id)
            except (ValueError, TypeError):
                logger.warning(f"Некорректный GROUP_ID в шаблоне: {group_id}")

        if not task_data.get('GROUP_ID') and group_id_from_variables:
            task_data['GROUP_ID'] = group_id_from_variables
            logger.debug(f"GROUP_ID получен из переменной процесса groupId: {group_id_from_variables}")

        # CREATED_BY
        self._set_created_by(task_data, template, initiator_id)

        # DEADLINE
        self._set_deadline(task_data, template, variables)

        # RESPONSIBLE_ID
        members_by_type = members.get('by_type', {})
        self._set_responsible_id(task_data, template, members_by_type, initiator_id)

        # ACCOMPLICES
        self._set_accomplices(task_data, template, members_by_type, initiator_id)

        # AUDITORS
        self._set_auditors(task_data, template, members_by_type, initiator_id, diagram_owner_id)

        # Теги
        if tags:
            try:
                tag_names = [tag.get('NAME') for tag in tags if tag.get('NAME')]
                if tag_names:
                    task_data['TAGS'] = ', '.join(tag_names)
                    logger.debug(f"TAGS из шаблона: {task_data['TAGS']}")
            except (TypeError, KeyError, AttributeError) as e:
                logger.warning(f"Ошибка обработки тегов из шаблона: {e}")

        # UF_CAMUNDA_ID_EXTERNAL_TASK
        task_data['UF_CAMUNDA_ID_EXTERNAL_TASK'] = task_id

        # Пользовательские поля из метаданных
        if user_fields_extractor:
            user_fields = user_fields_extractor(metadata)
            if user_fields:
                task_data.update(user_fields)
                logger.debug(f"Добавлены пользовательские поля из метаданных: {list(user_fields.keys())}")

        # Родительская задача
        if parent_task_id:
            task_data['PARENT_ID'] = parent_task_id
            task_data['SUBORDINATE'] = 'Y'
            logger.debug(f"Установлены родительская задача {parent_task_id} и признак подзадачи")

        # UF_ELEMENT_ID
        if element_id:
            task_data['UF_ELEMENT_ID'] = element_id
            logger.debug(f"Добавлено пользовательское поле UF_ELEMENT_ID={element_id} для задачи {task_id}")

        # UF_PROCESS_INSTANCE_ID
        process_instance_id = message_data.get('processInstanceId') or message_data.get('process_instance_id')
        if process_instance_id:
            task_data['UF_PROCESS_INSTANCE_ID'] = str(process_instance_id)
            logger.debug(f"Добавлено пользовательское поле UF_PROCESS_INSTANCE_ID={process_instance_id}")
        else:
            logger.warning(f"processInstanceId не найден для задачи {task_id}")

        # Логирование финальных значений
        self._log_task_data(task_data, template_data)

        return task_data, template_files

    def _extract_initiator_id(self, variables: Dict[str, Any]) -> Optional[str]:
        """Извлечение ID инициатора процесса из переменных"""
        started_by = variables.get('startedBy')

        if started_by:
            try:
                if isinstance(started_by, dict) and 'value' in started_by:
                    initiator_id = str(int(started_by['value']))
                else:
                    initiator_id = str(int(started_by))
                logger.debug(f"Используется startedBy={started_by} как инициатор процесса: {initiator_id}")
                return initiator_id
            except (ValueError, TypeError) as e:
                logger.warning(f"Некорректный startedBy={started_by}: {e}")
                return None
        else:
            logger.warning("startedBy отсутствует в переменных процесса")
            return None

    def _set_created_by(
        self,
        task_data: Dict[str, Any],
        template: Dict[str, Any],
        initiator_id: Optional[str]
    ) -> None:
        """Установка CREATED_BY с учётом флага USE_SUPERVISOR"""
        created_by = template.get('CREATED_BY')
        created_by_use_supervisor = template.get('CREATED_BY_USE_SUPERVISOR', 'N')

        try:
            created_by_int = int(created_by) if created_by is not None else 0
            is_valid_created_by = created_by_int > 0
        except (ValueError, TypeError):
            is_valid_created_by = False

        if is_valid_created_by:
            task_data['CREATED_BY'] = int(created_by)
            logger.debug(f"CREATED_BY из шаблона: {task_data['CREATED_BY']}")
        else:
            self._set_with_supervisor_fallback(
                task_data, 'CREATED_BY', created_by_use_supervisor, initiator_id
            )

    def _set_deadline(
        self,
        task_data: Dict[str, Any],
        template: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> None:
        """Установка DEADLINE: приоритет min(deadline процесса, deadline шаблона)"""
        process_deadline = get_camunda_datetime(variables, 'deadline')
        template_deadline: Optional[datetime] = None

        deadline_after = template.get('DEADLINE_AFTER')
        if deadline_after:
            try:
                deadline_after_seconds = int(deadline_after)
                if deadline_after_seconds > 0:
                    template_deadline = datetime.now() + timedelta(seconds=deadline_after_seconds)
                    logger.debug(f"Вычислен deadline из шаблона: {template_deadline}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Некорректный DEADLINE_AFTER в шаблоне: {deadline_after}, ошибка: {e}")

        final_deadline: Optional[datetime] = None
        if process_deadline and template_deadline:
            final_deadline = min(process_deadline, template_deadline)
            logger.debug(f"DEADLINE: min(процесс={process_deadline}, шаблон={template_deadline}) = {final_deadline}")
        elif process_deadline:
            final_deadline = process_deadline
            logger.debug(f"DEADLINE из переменной процесса: {final_deadline}")
        elif template_deadline:
            final_deadline = template_deadline
            logger.debug(f"DEADLINE из шаблона: {final_deadline}")

        if final_deadline:
            task_data['DEADLINE'] = final_deadline.strftime('%Y-%m-%d %H:%M:%S')

    def _set_responsible_id(
        self,
        task_data: Dict[str, Any],
        template: Dict[str, Any],
        members_by_type: Dict[str, List],
        initiator_id: Optional[str]
    ) -> None:
        """Установка RESPONSIBLE_ID с приоритетами"""
        responsible_use_supervisor = template.get('RESPONSIBLE_USE_SUPERVISOR', 'N')
        responsibles = members_by_type.get('R', [])

        if responsibles:
            try:
                responsible_user_id = int(responsibles[0].get('USER_ID', 0))
                if responsible_user_id > 0:
                    task_data['RESPONSIBLE_ID'] = responsible_user_id
                    logger.debug(f"RESPONSIBLE_ID из шаблона (members.R): {responsible_user_id}")
                    return
            except (ValueError, TypeError, IndexError, KeyError) as e:
                logger.warning(f"Ошибка обработки RESPONSIBLES из шаблона: {e}")

        # Fallback на template.RESPONSIBLE_ID
        responsible_id = template.get('RESPONSIBLE_ID')
        try:
            responsible_id_int = int(responsible_id) if responsible_id is not None else 0
            is_valid = responsible_id_int > 0
        except (ValueError, TypeError):
            is_valid = False

        if is_valid:
            task_data['RESPONSIBLE_ID'] = int(responsible_id)
            logger.debug(f"RESPONSIBLE_ID из шаблона (template.RESPONSIBLE_ID): {task_data['RESPONSIBLE_ID']}")
        else:
            self._set_with_supervisor_fallback(
                task_data, 'RESPONSIBLE_ID', responsible_use_supervisor, initiator_id
            )

    def _set_accomplices(
        self,
        task_data: Dict[str, Any],
        template: Dict[str, Any],
        members_by_type: Dict[str, List],
        initiator_id: Optional[str]
    ) -> None:
        """Установка ACCOMPLICES (соисполнителей)"""
        accomplices = members_by_type.get('A', [])

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
            self._add_supervisor_to_list(task_data, 'ACCOMPLICES', initiator_id)

    def _set_auditors(
        self,
        task_data: Dict[str, Any],
        template: Dict[str, Any],
        members_by_type: Dict[str, List],
        initiator_id: Optional[str],
        diagram_owner_id: Optional[int]
    ) -> None:
        """Установка AUDITORS (наблюдателей)"""
        auditors = members_by_type.get('U', [])

        if auditors:
            try:
                auditor_ids = [int(m.get('USER_ID')) for m in auditors if m.get('USER_ID')]
                if auditor_ids:
                    task_data['AUDITORS'] = auditor_ids
                    logger.debug(f"AUDITORS из шаблона: {auditor_ids}")
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Ошибка обработки AUDITORS из шаблона: {e}")

        # Проверяем флаг AUDITORS_USE_SUPERVISOR
        auditors_use_supervisor = template.get('AUDITORS_USE_SUPERVISOR', 'N')
        if auditors_use_supervisor == 'Y' and initiator_id:
            self._add_supervisor_to_list(task_data, 'AUDITORS', initiator_id)

        # Fallback на diagramOwner
        existing_auditors = task_data.get('AUDITORS')
        has_auditors = bool(existing_auditors)
        if isinstance(existing_auditors, list):
            has_auditors = len(existing_auditors) > 0

        if diagram_owner_id and not has_auditors:
            task_data['AUDITORS'] = [diagram_owner_id]
            logger.debug(f"AUDITORS получены из переменной процесса diagramOwner: {diagram_owner_id}")

    def _set_with_supervisor_fallback(
        self,
        task_data: Dict[str, Any],
        field_name: str,
        use_supervisor: str,
        initiator_id: Optional[str]
    ) -> None:
        """Установка поля с fallback на руководителя или инициатора"""
        if use_supervisor == 'Y' and initiator_id:
            try:
                initiator_id_int = int(initiator_id)
                supervisor_id = self.user_service.get_supervisor(initiator_id_int)
                if supervisor_id:
                    task_data[field_name] = supervisor_id
                    logger.debug(f"{field_name} из руководителя инициатора: supervisorId={supervisor_id}")
                else:
                    task_data[field_name] = initiator_id_int
                    logger.debug(f"{field_name} из initiatorId (руководитель не найден): {initiator_id_int}")
            except (ValueError, TypeError):
                task_data[field_name] = 1
                logger.warning(f"Некорректный initiatorId: {initiator_id}, используем значение по умолчанию 1")
        elif initiator_id:
            try:
                task_data[field_name] = int(initiator_id)
                logger.debug(f"{field_name} из initiatorId: {task_data[field_name]}")
            except (ValueError, TypeError):
                task_data[field_name] = 1
                logger.warning(f"Некорректный initiatorId: {initiator_id}, используем значение по умолчанию 1")
        else:
            task_data[field_name] = 1
            logger.warning(f"{field_name} не указан и initiatorId отсутствует, используем значение по умолчанию 1")

    def _add_supervisor_to_list(
        self,
        task_data: Dict[str, Any],
        field_name: str,
        initiator_id: str
    ) -> None:
        """Добавление руководителя в список (ACCOMPLICES или AUDITORS)"""
        try:
            initiator_id_int = int(initiator_id)
            supervisor_id = self.user_service.get_supervisor(initiator_id_int)
            if supervisor_id:
                if field_name not in task_data:
                    task_data[field_name] = []
                elif not isinstance(task_data[field_name], list):
                    task_data[field_name] = [task_data[field_name]] if task_data[field_name] else []

                if supervisor_id not in task_data[field_name]:
                    task_data[field_name].append(supervisor_id)
                    logger.debug(f"Добавлен руководитель к {field_name}: supervisorId={supervisor_id}")
        except (ValueError, TypeError) as e:
            logger.warning(f"Ошибка при добавлении руководителя в {field_name}: {e}")

    def _log_task_data(self, task_data: Dict[str, Any], template_data: Dict[str, Any]) -> None:
        """Логирование финальных значений task_data"""
        template_id = template_data.get('meta', {}).get('templateId', 'N/A')
        logger.debug(f"Формирование task_data из шаблона (templateId={template_id}):")
        logger.debug(f"  TITLE: {task_data.get('TITLE', 'N/A')}")
        logger.debug(f"  RESPONSIBLE_ID: {task_data.get('RESPONSIBLE_ID', 'НЕ УСТАНОВЛЕН')}")
        logger.debug(f"  CREATED_BY: {task_data.get('CREATED_BY', 'НЕ УСТАНОВЛЕН')}")
        logger.debug(f"  GROUP_ID: {task_data.get('GROUP_ID', 'НЕ УСТАНОВЛЕН')}")
        logger.debug(f"  PRIORITY: {task_data.get('PRIORITY', 'N/A')}")
        logger.debug(f"  DEADLINE: {task_data.get('DEADLINE', 'НЕ УСТАНОВЛЕН')}")
        logger.debug(f"  ACCOMPLICES: {task_data.get('ACCOMPLICES', [])}")
        logger.debug(f"  AUDITORS: {task_data.get('AUDITORS', [])}")
