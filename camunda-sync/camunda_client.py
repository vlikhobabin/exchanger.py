#!/usr/bin/env python3
"""
Клиент для работы с Camunda REST API
"""
import json
import time
import os
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import camunda_config


class CamundaAPIError(Exception):
    """Базовая ошибка API Camunda"""
    pass


class CamundaAuthError(CamundaAPIError):
    """Ошибка аутентификации"""
    pass


class CamundaDeployError(CamundaAPIError):
    """Ошибка деплоя процесса"""
    pass


class CamundaValidationError(CamundaAPIError):
    """Ошибка валидации BPMN"""
    pass


class CamundaClient:
    """
    Клиент для работы с Camunda REST API
    
    Обеспечивает:
    - Деплой BPMN схем в Camunda
    - Получение информации о деплоях
    - Управление определениями процессов
    - Обработку ошибок и retry механизм
    """
    
    def __init__(self):
        """Инициализация клиента"""
        self.base_url = camunda_config.base_url
        self.session = requests.Session()
        
        # Настройка таймаута
        self.session.timeout = camunda_config.timeout
        
        # Базовые заголовки
        self.session.headers.update({
            "User-Agent": "Camunda-StormBPMN-Sync/1.0.0",
            "Accept": "application/json"
        })
        
        # Настройка аутентификации
        if camunda_config.auth_credentials:
            self.session.auth = camunda_config.auth_credentials
            logger.info(f"Аутентификация настроена для пользователя: {camunda_config.auth_username}")
        
        logger.info(f"Camunda Client инициализирован для {self.base_url}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException,)),
        reraise=True
    )
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Выполнить HTTP запрос к Camunda REST API
        
        Args:
            method: HTTP метод (GET, POST, etc.)
            endpoint: Конечная точка API
            **kwargs: Дополнительные параметры для requests
            
        Returns:
            Ответ API в виде словаря
            
        Raises:
            CamundaAuthError: Ошибка аутентификации
            CamundaAPIError: Общая ошибка API
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        logger.debug(f"Запрос: {method} {url}")
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                **kwargs
            )
            
            # Логирование запроса
            logger.debug(f"Ответ: {response.status_code} {response.reason}")
            
            # Обработка ошибок HTTP
            if response.status_code == 401:
                raise CamundaAuthError("Неверные учетные данные")
            elif response.status_code == 403:
                raise CamundaAuthError("Недостаточно прав доступа")
            elif response.status_code == 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', 'Неверный запрос')
                    error_type = error_data.get('type', '')
                    
                    # Логируем полную ошибку для отладки
                    logger.error(f"HTTP 400 детали: {error_data}")
                    
                    if 'validation' in error_msg.lower() or 'validation' in error_type.lower():
                        raise CamundaValidationError(f"Ошибка валидации: {error_msg}")
                    else:
                        raise CamundaDeployError(f"Ошибка деплоя: {error_msg}")
                except json.JSONDecodeError:
                    error_text = response.text[:500]  # Больше текста для анализа
                    logger.error(f"HTTP 400 (не JSON): {error_text}")
                    raise CamundaAPIError(f"HTTP 400: {error_text}")
            elif response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', f'HTTP {response.status_code}')
                    error_type = error_data.get('type', '')
                    
                    # Логируем полную ошибку для отладки
                    logger.error(f"HTTP {response.status_code} детали: {error_data}")
                    
                    if response.status_code == 500:
                        raise CamundaAPIError(f"Внутренняя ошибка сервера: {error_msg}")
                    else:
                        raise CamundaAPIError(f"Ошибка API: {error_msg}")
                except json.JSONDecodeError:
                    error_text = response.text[:500]  # Больше текста для анализа
                    logger.error(f"HTTP {response.status_code} (не JSON): {error_text}")
                    raise CamundaAPIError(f"HTTP {response.status_code}: {error_text}")
            
            # Парсинг JSON ответа
            try:
                return response.json()
            except json.JSONDecodeError as e:
                # Некоторые endpoint могут не возвращать JSON
                if response.status_code == 204:  # No Content
                    return {}
                logger.error(f"Ошибка парсинга JSON: {e}")
                raise CamundaAPIError(f"Ошибка парсинга ответа: {e}")
                
        except requests.RequestException as e:
            logger.error(f"Ошибка запроса: {e}")
            raise CamundaAPIError(f"Ошибка сетевого запроса: {e}")
    
    def _deploy_request(self, files, data):
        """
        Выполнить запрос деплоя без retry механизма
        (чтобы избежать повторных попыток при валидационных ошибках)
        """
        url = f"{self.base_url}/deployment/create"
        
        logger.debug(f"Запрос деплоя: POST {url}")
        
        try:
            response = self.session.request(
                method='POST',
                url=url,
                files=files,
                data=data
            )
            
            logger.debug(f"Ответ деплоя: {response.status_code} {response.reason}")
            
            # Обработка ошибок HTTP
            if response.status_code == 401:
                raise CamundaAuthError("Неверные учетные данные")
            elif response.status_code == 403:
                raise CamundaAuthError("Недостаточно прав доступа")
            elif response.status_code == 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', 'Неверный запрос')
                    error_type = error_data.get('type', '')
                    
                    # Логируем полную ошибку для отладки
                    logger.error(f"HTTP 400 детали деплоя: {error_data}")
                    
                    if 'validation' in error_msg.lower() or 'validation' in error_type.lower():
                        raise CamundaValidationError(f"Ошибка валидации BPMN: {error_msg}")
                    else:
                        raise CamundaDeployError(f"Ошибка деплоя: {error_msg}")
                except json.JSONDecodeError:
                    error_text = response.text[:1000]  # Больше текста для анализа
                    logger.error(f"HTTP 400 деплоя (не JSON): {error_text}")
                    raise CamundaDeployError(f"Ошибка деплоя (400): {error_text}")
            elif response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get('message', f'HTTP {response.status_code}')
                    
                    # Логируем полную ошибку для отладки
                    logger.error(f"HTTP {response.status_code} детали деплоя: {error_data}")
                    
                    if response.status_code == 500:
                        raise CamundaAPIError(f"Внутренняя ошибка сервера при деплое: {error_msg}")
                    else:
                        raise CamundaAPIError(f"Ошибка API при деплое: {error_msg}")
                except json.JSONDecodeError:
                    error_text = response.text[:1000]
                    logger.error(f"HTTP {response.status_code} деплоя (не JSON): {error_text}")
                    raise CamundaAPIError(f"Ошибка деплоя ({response.status_code}): {error_text}")
            
            # Парсинг JSON ответа
            try:
                return response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Ошибка парсинга JSON ответа деплоя: {e}")
                if response.status_code == 204:  # No Content
                    return {}
                raise CamundaAPIError(f"Ошибка парсинга ответа деплоя: {e}")
                
        except requests.RequestException as e:
            logger.error(f"Ошибка сетевого запроса при деплое: {e}")
            raise CamundaAPIError(f"Ошибка сетевого запроса при деплое: {e}")
    
    def deploy_diagram(
        self,
        bpmn_file_path: str,
        deployment_name: Optional[str] = None,
        enable_duplicate_filtering: bool = False,
        deployment_source: str = "camunda-sync"
    ) -> Dict[str, Any]:
        """
        Развернуть BPMN диаграмму в Camunda
        
        Args:
            bpmn_file_path: Путь к BPMN файлу
            deployment_name: Имя деплоя (по умолчанию - имя файла)
            enable_duplicate_filtering: Включить фильтрацию дубликатов
            deployment_source: Источник деплоя
            
        Returns:
            Словарь с информацией о деплое
            
        Example:
            {
                "id": "deployment-id",
                "name": "My Process",
                "deploymentTime": "2024-01-01T12:00:00.000+0000",
                "source": "camunda-sync",
                "deployedProcessDefinitions": {
                    "process-id": {
                        "id": "process-id:1:definition-id",
                        "key": "process-id",
                        "version": 1,
                        ...
                    }
                }
            }
        """
        # Проверка существования файла
        file_path = Path(bpmn_file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"BPMN файл не найден: {bpmn_file_path}")
        
        if not file_path.suffix.lower() == '.bpmn':
            logger.warning(f"Файл не имеет расширения .bpmn: {bpmn_file_path}")
        
        # Определение имени деплоя
        if deployment_name is None:
            deployment_name = file_path.stem
        
        logger.info(f"Начинаем деплой: {deployment_name}")
        logger.info(f"Файл: {bpmn_file_path}")
        logger.info(f"Размер файла: {file_path.stat().st_size} байт")
        
        try:
            # Читаем файл целиком для проверки
            with open(file_path, 'r', encoding='utf-8') as f:
                bpmn_content = f.read()
            
            # Проверяем, что это действительно XML
            if not bpmn_content.strip().startswith('<?xml'):
                logger.warning("Файл не начинается с XML декларации")
            
            if 'bpmn:definitions' not in bpmn_content:
                raise CamundaValidationError("Файл не содержит BPMN definitions")
            
            logger.debug(f"BPMN файл содержит {len(bpmn_content)} символов")
            
            # Подготовка multipart данных
            with open(file_path, 'rb') as f:
                files = {
                    # Имя поля будет использовано как имя ресурса в деплое
                    file_path.name: (file_path.name, f, 'application/xml')
                }
                
                # Дополнительные параметры деплоя
                data = {
                    'deployment-name': deployment_name,
                    'deployment-source': deployment_source
                }
                
                if enable_duplicate_filtering:
                    data['enable-duplicate-filtering'] = 'true'
                
                logger.debug(f"Параметры деплоя: {data}")
                logger.debug(f"Файл для деплоя: {file_path.name} ({file_path.stat().st_size} байт)")
                
                # Выполнение деплоя (без retry для избежания повторов при валидационных ошибках)
                result = self._deploy_request(
                    files=files,
                    data=data
                )
            
            # Анализ результата деплоя
            deployment_id = result.get('id')
            deployed_processes = result.get('deployedProcessDefinitions', {})
            
            logger.info(f"✅ Деплой успешен!")
            logger.info(f"   ID деплоя: {deployment_id}")
            logger.info(f"   Дата деплоя: {result.get('deploymentTime')}")
            logger.info(f"   Развернуто процессов: {len(deployed_processes)}")
            
            # Детали о процессах
            for process_key, process_def in deployed_processes.items():
                process_id = process_def.get('id')
                process_version = process_def.get('version')
                process_name = process_def.get('name', 'Без названия')
                
                logger.info(f"   📋 Процесс: {process_name}")
                logger.info(f"      Key: {process_key}")
                logger.info(f"      ID: {process_id}")
                logger.info(f"      Версия: {process_version}")
            
            return result
            
        except CamundaValidationError as e:
            logger.error(f"❌ Ошибка валидации BPMN: {e}")
            raise
        except CamundaDeployError as e:
            logger.error(f"❌ Ошибка деплоя: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при деплое: {e}")
            raise CamundaAPIError(f"Ошибка деплоя: {e}")
    
    def get_deployments(self, name: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получить список деплоев
        
        Args:
            name: Фильтр по имени деплоя
            limit: Максимальное количество результатов
            
        Returns:
            Список деплоев
        """
        params = {
            'maxResults': limit,
            'sortBy': 'deploymentTime',
            'sortOrder': 'desc'
        }
        
        if name:
            params['name'] = name
        
        logger.debug(f"Запрос списка деплоев: {params}")
        
        try:
            result = self._make_request('GET', '/deployment', params=params)
            
            logger.info(f"Получено {len(result)} деплоев")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка деплоев: {e}")
            raise
    
    def get_deployment_by_id(self, deployment_id: str) -> Dict[str, Any]:
        """
        Получить информацию о деплое по ID
        
        Args:
            deployment_id: ID деплоя
            
        Returns:
            Информация о деплое
        """
        if not deployment_id:
            raise ValueError("deployment_id не может быть пустым")
        
        logger.debug(f"Запрос деплоя: {deployment_id}")
        
        try:
            result = self._make_request('GET', f'/deployment/{deployment_id}')
            
            logger.info(f"Получен деплой: {result.get('name', 'Без названия')}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении деплоя {deployment_id}: {e}")
            raise
    
    def get_process_definitions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Получить список определений процессов
        
        Args:
            limit: Максимальное количество результатов
            
        Returns:
            Список определений процессов
        """
        params = {
            'maxResults': limit,
            'sortBy': 'version',
            'sortOrder': 'desc'
        }
        
        logger.debug(f"Запрос определений процессов: {params}")
        
        try:
            result = self._make_request('GET', '/process-definition', params=params)
            
            logger.info(f"Получено {len(result)} определений процессов")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при получении определений процессов: {e}")
            raise
    
    def test_connection(self) -> bool:
        """
        Проверить соединение с Camunda REST API
        
        Returns:
            True если соединение работает, False в противном случае
        """
        try:
            logger.info("Тестирование соединения с Camunda REST API...")
            
            # Пробуем получить версию Camunda
            result = self._make_request('GET', '/version')
            
            if 'version' in result:
                version = result['version']
                logger.info(f"✓ Соединение с Camunda работает (версия: {version})")
                return True
            else:
                logger.warning("⚠ Неожиданный формат ответа API")
                return False
                
        except CamundaAuthError as e:
            logger.error(f"✗ Ошибка аутентификации: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Ошибка соединения: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получить статистику работы клиента
        
        Returns:
            Словарь со статистикой
        """
        return {
            "base_url": self.base_url,
            "timeout": camunda_config.timeout,
            "auth_enabled": camunda_config.auth_enabled,
            "auth_username": camunda_config.auth_username,
            "session_active": bool(self.session)
        }
    
    def close(self):
        """Закрыть сессию"""
        if self.session:
            self.session.close()
            logger.debug("Camunda Client сессия закрыта") 