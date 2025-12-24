#!/usr/bin/env python3
"""
Сервис для работы с диаграммами Camunda и параметрами процессов
"""
import json
import requests
from typing import Dict, List, Optional, Any
from loguru import logger
from ..utils import format_process_variable_value


class DiagramService:
    """
    Сервис для работы с диаграммами Camunda BPM

    Функции:
    - Получение параметров диаграммы через Bitrix24 REST API
    - Определение ID диаграммы Storm по различным источникам
    - Формирование блока переменных процесса для описания задачи

    Использует кэширование для оптимизации повторных запросов.
    """

    def __init__(self, config: Any):
        """
        Инициализация сервиса

        Args:
            config: Конфигурация Bitrix24 (webhook_url, request_timeout)
        """
        self.config = config

        # Кэш параметров диаграмм Camunda -> Bitrix24
        self.properties_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.details_cache: Dict[str, Dict[str, Any]] = {}

    def build_process_variables_block(
        self,
        message_data: Dict[str, Any],
        camunda_process_id: str,
        task_id: str
    ) -> Optional[str]:
        """
        Формирование текстового блока значений переменных процесса для описания задачи

        Получает список параметров диаграммы через API, извлекает значения из
        переменных процесса и форматирует их в читаемый текстовый блок.

        Args:
            message_data: Данные сообщения из RabbitMQ
            camunda_process_id: ID процесса Camunda
            task_id: ID задачи (для логирования)

        Returns:
            Отформатированный текстовый блок с переменными или None
        """
        if not camunda_process_id:
            logger.debug(f"Пропуск построения блока переменных: отсутствует camundaProcessId для задачи {task_id}")
            return None

        properties = self.get_properties(camunda_process_id)
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
            formatted_value = format_process_variable_value(property_type, value_entry)
            lines.append(f"{name}: {formatted_value};")

        if not lines:
            logger.debug(f"Не удалось сформировать строки значений переменных процесса для задачи {task_id}")
            return None

        return "\n".join(lines)

    def get_properties(self, camunda_process_id: str) -> List[Dict[str, Any]]:
        """
        Получение списка параметров диаграммы процесса через Bitrix24 REST API

        Использует кэширование для оптимизации повторных запросов.
        При успешном запросе также сохраняет информацию о диаграмме в details_cache.

        Args:
            camunda_process_id: ID процесса Camunda

        Returns:
            Список параметров диаграммы или пустой список
        """
        if not camunda_process_id:
            return []

        if camunda_process_id in self.properties_cache:
            return self.properties_cache[camunda_process_id]

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
                self.properties_cache[camunda_process_id] = []
                self.details_cache[camunda_process_id] = {}
                return []

            properties_data = result.get('data', {})
            diagram_info = properties_data.get('diagram') or {}
            self.details_cache[camunda_process_id] = diagram_info
            properties = properties_data.get('properties', [])
            if isinstance(properties, list):
                self.properties_cache[camunda_process_id] = properties
                logger.debug(f"Получено {len(properties)} параметров диаграммы для процесса {camunda_process_id}")
                return properties

            logger.warning(f"Неожиданный формат списка параметров для процесса {camunda_process_id}")
            self.properties_cache[camunda_process_id] = []
            if camunda_process_id not in self.details_cache:
                self.details_cache[camunda_process_id] = {}
            return []

        except requests.exceptions.Timeout:
            logger.error(f"Таймаут запроса параметров диаграммы (timeout={self.config.request_timeout}s) для процесса {camunda_process_id}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса параметров диаграммы для процесса {camunda_process_id}: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка декодирования JSON ответа параметров диаграммы: {e}")
        except Exception as e:
            logger.error(f"Неожиданная ошибка при запросе параметров диаграммы {camunda_process_id}: {e}")

        self.properties_cache[camunda_process_id] = []
        self.details_cache[camunda_process_id] = {}
        return []

    def resolve_id(
        self,
        diagram_id: Optional[str],
        camunda_process_id: Optional[str],
        metadata: Optional[Dict[str, Any]],
        template_data: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Попытка определить ID диаграммы Storm различными способами

        Приоритет источников:
        1. Явно переданный diagram_id
        2. processProperties в metadata
        3. metadata.diagram
        4. template.meta
        5. Кэш параметров диаграммы (по camunda_process_id)

        Args:
            diagram_id: Явно переданный ID диаграммы
            camunda_process_id: ID процесса Camunda
            metadata: Метаданные сообщения
            template_data: Данные шаблона задачи

        Returns:
            ID диаграммы Storm или None
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
            self.get_properties(camunda_process_id)
            cached_info = self.details_cache.get(camunda_process_id) or {}
            value = cached_info.get('ID') or cached_info.get('id')
            if value:
                resolved = str(value)
                logger.debug(f"diagramId получен из кэша параметров диаграммы: {resolved}")
                return resolved

        logger.debug("diagramId не удалось определить по доступным данным")
        return None
