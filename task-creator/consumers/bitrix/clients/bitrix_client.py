"""
Клиент для работы с REST API Bitrix24

Модуль содержит класс BitrixAPIClient для выполнения HTTP запросов
к API Bitrix24 и основные операции с задачами.
"""
import json
from typing import Any, Dict, Optional

import requests
from loguru import logger


class BitrixAPIClient:
    """
    Клиент для работы с REST API Bitrix24

    Предоставляет низкоуровневые методы для выполнения запросов
    к API Bitrix24 через webhook.
    """

    def __init__(self, webhook_url: str, request_timeout: int = 30):
        """
        Инициализация клиента Bitrix24 API

        Args:
            webhook_url: URL вебхука Bitrix24
            request_timeout: Таймаут запросов в секундах
        """
        self.webhook_url = webhook_url.rstrip('/')
        self.request_timeout = request_timeout
        self.task_add_url = f"{self.webhook_url}/tasks.task.add.json"

    def request_sync(self, method: str, api_method: str, params: Dict[str, Any]) -> Optional[Any]:
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
            url = f"{self.webhook_url}/{api_method}"

            if method.upper() == 'GET':
                response = requests.get(
                    url,
                    params=params,
                    timeout=self.request_timeout
                )
            else:
                response = requests.post(
                    url,
                    json=params,
                    headers={'Content-Type': 'application/json'},
                    timeout=self.request_timeout
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

    async def request_async(self, method: str, api_method: str, params: Dict[str, Any]) -> Optional[Any]:
        """
        Асинхронное выполнение HTTP запроса к API Bitrix24

        Примечание: В текущей реализации использует синхронный requests.
        Для полной асинхронности рекомендуется использовать aiohttp.

        Args:
            method: HTTP метод (GET, POST)
            api_method: Метод API Bitrix24
            params: Параметры запроса

        Returns:
            Результат запроса или None в случае ошибки
        """
        # Используем синхронную реализацию (как было в оригинале)
        return self.request_sync(method, api_method, params)

    def send_task(self, task_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
                timeout=self.request_timeout
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

    def find_task_by_external_id(self, external_task_id: str) -> Optional[Dict[str, Any]]:
        """
        Поиск задачи в Bitrix24 по External Task ID

        Args:
            external_task_id: External Task ID из Camunda

        Returns:
            Данные задачи если найдена, None если не найдена
        """
        try:
            # Используем tasks.task.list с фильтром по пользовательскому полю
            url = f"{self.webhook_url}/tasks.task.list.json"
            params = {
                "filter": {
                    "UF_CAMUNDA_ID_EXTERNAL_TASK": external_task_id
                },
                "select": ["*", "UF_*"]  # Выбираем все поля включая пользовательские
            }

            response = requests.post(url, json=params, timeout=self.request_timeout)

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

    def get_list_element_name(self, iblock_id: int, element_id: int) -> Optional[str]:
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
            api_url = f"{self.webhook_url}/lists.element.get"
            params = {
                'IBLOCK_TYPE_ID': 'lists',
                'IBLOCK_ID': iblock_id,
                'ELEMENT_ID': element_id
            }

            response = requests.get(api_url, params=params, timeout=self.request_timeout)
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
