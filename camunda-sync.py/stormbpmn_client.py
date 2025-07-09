#!/usr/bin/env python3
"""
Клиент для работы с API StormBPMN
"""
import json
import time
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode
import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import stormbpmn_config


class StormBPMNAPIError(Exception):
    """Базовая ошибка API StormBPMN"""
    pass


class StormBPMNAuthError(StormBPMNAPIError):
    """Ошибка аутентификации"""
    pass


class StormBPMNNotFoundError(StormBPMNAPIError):
    """Ресурс не найден"""
    pass


class StormBPMNClient:
    """
    Клиент для работы с API StormBPMN
    
    Обеспечивает:
    - Получение списка диаграмм с фильтрацией и пагинацией
    - Получение данных конкретной диаграммы по GUID
    - Получение списка ответственных по диаграмме
    - Обработку ошибок и retry механизм
    """
    
    def __init__(self):
        """Инициализация клиента"""
        self.base_url = stormbpmn_config.api_base_url
        self.session = requests.Session()
        
        # Настройка таймаута
        self.session.timeout = stormbpmn_config.timeout
        
        # Базовые заголовки
        self.session.headers.update({
            "User-Agent": "Camunda-StormBPMN-Sync/1.0.0",
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate"
        })
        
        logger.info(f"StormBPMN Client инициализирован для {self.base_url}")
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Получить заголовки аутентификации"""
        try:
            return stormbpmn_config.auth_headers
        except ValueError as e:
            logger.error(f"Ошибка аутентификации: {e}")
            raise StormBPMNAuthError(f"Ошибка аутентификации: {e}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, StormBPMNAPIError))
    )
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Выполнить HTTP запрос к API StormBPMN
        
        Args:
            method: HTTP метод (GET, POST, etc.)
            endpoint: Конечная точка API
            **kwargs: Дополнительные параметры для requests
            
        Returns:
            Ответ API в виде словаря
            
        Raises:
            StormBPMNAuthError: Ошибка аутентификации
            StormBPMNNotFoundError: Ресурс не найден
            StormBPMNAPIError: Общая ошибка API
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Добавляем заголовки аутентификации
        headers = kwargs.pop('headers', {})
        headers.update(self._get_auth_headers())
        
        logger.debug(f"Запрос: {method} {url}")
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                **kwargs
            )
            
            # Логирование запроса
            logger.debug(f"Ответ: {response.status_code} {response.reason}")
            
            # Обработка ошибок HTTP
            if response.status_code == 401:
                raise StormBPMNAuthError("Неверный токен авторизации")
            elif response.status_code == 403:
                raise StormBPMNAuthError("Недостаточно прав доступа")
            elif response.status_code == 404:
                raise StormBPMNNotFoundError("Ресурс не найден")
            elif response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', f'HTTP {response.status_code}')
                except:
                    error_msg = f'HTTP {response.status_code}: {response.text[:200]}'
                raise StormBPMNAPIError(f"Ошибка API: {error_msg}")
            
            # Парсинг JSON ответа
            try:
                return response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON: {e}")
                raise StormBPMNAPIError(f"Ошибка парсинга ответа: {e}")
                
        except requests.RequestException as e:
            logger.error(f"Ошибка запроса: {e}")
            raise StormBPMNAPIError(f"Ошибка сетевого запроса: {e}")
    
    def get_diagrams_list(
        self,
        size: int = None,
        page: int = 0,
        quality: str = "0,ge",
        shared_by_user: bool = False,
        shared_with_user: bool = False,
        view: str = None,
        sort: str = None,
        **additional_filters
    ) -> Dict[str, Any]:
        """
        Получить список диаграмм с фильтрацией и пагинацией
        
        Args:
            size: Количество диаграмм на страницу (по умолчанию из конфига)
            page: Номер страницы (начиная с 0)
            quality: Фильтр по качеству ("0,ge" = больше или равно 0)
            shared_by_user: Диаграммы, поделенные пользователем
            shared_with_user: Диаграммы, поделенные с пользователем
            view: Тип представления (по умолчанию из конфига)
            sort: Сортировка (по умолчанию из конфига)
            **additional_filters: Дополнительные фильтры
            
        Returns:
            Словарь с данными диаграмм и информацией о пагинации
            
        Example:
            {
                "content": [...],  # Список диаграмм
                "totalElements": 197,
                "totalPages": 10,
                "size": 20,
                "number": 0,
                ...
            }
        """
        # Параметры по умолчанию из конфигурации
        if size is None:
            size = stormbpmn_config.default_page_size
        if view is None:
            view = stormbpmn_config.default_view
        if sort is None:
            sort = stormbpmn_config.default_sort
        
        # Формирование параметров запроса
        params = {
            'quality': quality,
            'sharedByUser': str(shared_by_user).lower(),
            'sharedWithUser': str(shared_with_user).lower(),
            'view': view,
            'size': size,
            'page': page,
            'sort': sort
        }
        
        # Добавление дополнительных фильтров
        params.update(additional_filters)
        
        # Удаление пустых параметров
        params = {k: v for k, v in params.items() if v is not None}
        
        logger.info(f"Запрос списка диаграмм: страница {page}, размер {size}")
        logger.debug(f"Параметры фильтрации: {params}")
        
        try:
            result = self._make_request('GET', '/diagram/filter', params=params)
            
            # Логирование результата
            content = result.get('content', [])
            total = result.get('totalElements', 0)
            logger.info(f"Получено {len(content)} диаграмм из {total} всего")
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка диаграмм: {e}")
            raise
    
    def get_diagram_by_id(self, diagram_id: str) -> Dict[str, Any]:
        """
        Получить данные диаграммы по GUID
        
        Args:
            diagram_id: GUID диаграммы
            
        Returns:
            Словарь с полными данными диаграммы, включая BPMN XML
            
        Example:
            {
                "permission": "EDIT",
                "diagram": {
                    "id": "...",
                    "name": "...",
                    "body": "<?xml version=\"1.0\"...>",  # BPMN XML
                    ...
                }
            }
        """
        if not diagram_id:
            raise ValueError("diagram_id не может быть пустым")
        
        logger.info(f"Запрос диаграммы: {diagram_id}")
        
        try:
            result = self._make_request('GET', f'/diagram/{diagram_id}')
            
            # Логирование результата
            diagram = result.get('diagram', {})
            name = diagram.get('name', 'Без названия')
            has_body = bool(diagram.get('body'))
            
            logger.info(f"Получена диаграмма: '{name}' (BPMN XML: {'есть' if has_body else 'нет'})")
            
            return result
            
        except StormBPMNNotFoundError:
            logger.error(f"Диаграмма {diagram_id} не найдена")
            raise
        except Exception as e:
            logger.error(f"Ошибка при получении диаграммы {diagram_id}: {e}")
            raise
    
    def get_diagram_assignees(self, diagram_id: str) -> List[Dict[str, Any]]:
        """
        Получить список ответственных по диаграмме
        
        Args:
            diagram_id: GUID диаграммы
            
        Returns:
            Список словарей с информацией об ответственных
            
        Example:
            [
                {
                    "assigneeEdgeId": 15700296,
                    "assigneeName": "Рук.отд. арх.сопр. и анализа проектов",
                    "assigneeId": 15298311,
                    "elementId": "Activity_1597r5e",
                    "elementName": "Поставить задачу",
                    "assigneeType": "HUMAN",
                    "duration": 900,
                    "color": "#d7b3f2",
                    ...
                }
            ]
        """
        if not diagram_id:
            raise ValueError("diagram_id не может быть пустым")
        
        logger.info(f"Запрос ответственных для диаграммы: {diagram_id}")
        
        try:
            result = self._make_request('GET', f'/assignee/assigneeedges/{diagram_id}')
            
            # API возвращает список напрямую
            if not isinstance(result, list):
                logger.warning(f"Неожиданный формат ответа для ответственных: {type(result)}")
                return []
            
            # Логирование результата
            logger.info(f"Получено {len(result)} ответственных")
            
            # Группировка по типам для статистики
            human_count = sum(1 for item in result if item.get('assigneeType') == 'HUMAN')
            system_count = len(result) - human_count
            
            if human_count > 0:
                logger.debug(f"Ответственных людей: {human_count}")
            if system_count > 0:
                logger.debug(f"Системных ответственных: {system_count}")
            
            return result
            
        except StormBPMNNotFoundError:
            logger.warning(f"Ответственные для диаграммы {diagram_id} не найдены")
            return []
        except Exception as e:
            logger.error(f"Ошибка при получении ответственных для {diagram_id}: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получить статистику работы клиента
        
        Returns:
            Словарь со статистикой
        """
        return {
            "base_url": self.base_url,
            "timeout": stormbpmn_config.timeout,
            "retry_attempts": stormbpmn_config.retry_attempts,
            "session_active": bool(self.session)
        }
    
    def test_connection(self) -> bool:
        """
        Проверить соединение с API StormBPMN
        
        Returns:
            True если соединение работает, False в противном случае
        """
        try:
            logger.info("Тестирование соединения с StormBPMN API...")
            
            # Пробуем получить первую страницу диаграмм с минимальным размером
            result = self.get_diagrams_list(size=1, page=0)
            
            if 'content' in result:
                logger.info("✓ Соединение с StormBPMN API работает")
                return True
            else:
                logger.warning("⚠ Неожиданный формат ответа API")
                return False
                
        except StormBPMNAuthError as e:
            logger.error(f"✗ Ошибка аутентификации: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Ошибка соединения: {e}")
            return False
    
    def close(self):
        """Закрыть сессию"""
        if self.session:
            self.session.close()
            logger.debug("StormBPMN Client сессия закрыта") 