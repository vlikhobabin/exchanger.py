"""
Сервис для работы с пользователями Bitrix24

Модуль содержит класс UserService для работы с пользователями:
получение информации об ответственных, руководителях и т.д.
"""
import json
from typing import Any, Dict, Optional, Tuple

import requests
from loguru import logger


class UserService:
    """
    Сервис для работы с пользователями Bitrix24

    Предоставляет методы для получения информации об ответственных
    за элементы диаграммы, руководителях пользователей и т.д.
    """

    def __init__(
        self,
        config: Any,
        responsible_cache: Dict[Tuple[Optional[str], Optional[str], str], Optional[Dict[str, Any]]]
    ):
        """
        Инициализация сервиса пользователей

        Args:
            config: Конфигурация (webhook_url, request_timeout)
            responsible_cache: Кэш ответственных (передаётся из handler для сохранения состояния)
        """
        self.config = config
        self.responsible_cache = responsible_cache

    def get_responsible_info(
        self,
        camunda_process_id: Optional[str],
        diagram_id: Optional[str],
        element_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Получение полной записи ответственного элемента диаграммы

        Args:
            camunda_process_id: ID процесса Camunda
            diagram_id: ID диаграммы
            element_id: ID элемента диаграммы

        Returns:
            Словарь с информацией об ответственном или None
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

    def get_responsible_id_by_assignee(self, assignee_id: str) -> int:
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

    def get_supervisor(self, user_id: int) -> Optional[int]:
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
