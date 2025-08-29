#!/usr/bin/env python3
"""
Обработчик сообщений для создания задач в Bitrix24
"""
import os
import json
import time
import yaml
from pathlib import Path
from typing import Dict, Optional, Any, List
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
        self.task_add_url = f"{self.config.webhook_url}/tasks.task.add.json"
        
        # RabbitMQ Publisher для отправки успешных сообщений
        self.publisher = RabbitMQPublisher()
        
        # Кеш соответствий ролей и пользователей
        self._roles_cache = {}  # {assignee_id: responsible_id}
        self._cache_timestamp = None
        self._roles_mapping_file = Path(__file__).parent / 'roles_mapping.yaml'
        
        # Статистика
        self.stats = {
            "total_messages": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "start_time": time.time(),
            "last_message_time": None,
            "sent_to_success_queue": 0,
            "failed_to_send_success": 0
        }
    
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
                
                # Отправка успешного результата в очередь bitrix24.sent.queue
                success_sent = self._send_success_message(message_data, result, "bitrix24.queue")
                if success_sent:
                    self.stats["sent_to_success_queue"] += 1
                else:
                    self.stats["failed_to_send_success"] += 1
                    logger.warning("Не удалось отправить результат в очередь успешных сообщений")
                
                return True
            else:
                self.stats["failed_tasks"] += 1
                error_msg = result.get('error_description', 'Unknown error') if result else 'No response'
                logger.error(f"Ошибка создания задачи в Bitrix24: {error_msg}")
                return False
                
        except Exception as e:
            self.stats["failed_tasks"] += 1
            logger.error(f"Критическая ошибка при обработке сообщения: {e}")
            return False
    
    def _create_bitrix_task(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Создание задачи в Bitrix24 на основе данных сообщения
        
        Args:
            message_data: Данные сообщения из RabbitMQ
            
        Returns:
            Ответ от API Bitrix24
        """
        try:
            # Извлечение данных из сообщения
            task_id = message_data.get('task_id', 'unknown')
            topic = message_data.get('topic', 'unknown')
            variables = message_data.get('variables', {})
            metadata = message_data.get('metadata', {})
            
            # Формирование заголовка задачи
            title = self._extract_title(variables, metadata, topic)
            
            # Формирование описания (в первой версии - все данные сообщения)
            # description = self._create_description(message_data)
            # Теперь в описание дублируем title
            description = title
            
            # Извлечение дополнительных параметров
            assignee_id = self._extract_assignee_id(variables, metadata)
            responsible_id = self._get_responsible_id_by_assignee(assignee_id)
            # priority = self._extract_priority(variables, metadata)  # Закомментировано до реализации функциональности приоритетов
            priority = 1  # Явное значение для обычных задач (не важные)
            deadline = self._extract_deadline(variables, metadata)
            
            # Извлечение данных проекта и постановщика из переменных процесса
            project_id = self._extract_project_id(variables)
            created_by_id = self._extract_created_by_id(variables)
            
            # Подготовка данных задачи для Bitrix24
            task_data = {
                'TITLE': title,
                'DESCRIPTION': description,
                'RESPONSIBLE_ID': responsible_id,
                'PRIORITY': priority,
                'CREATED_BY': created_by_id,
            }
            
            # Добавление GROUP_ID если указан projectId
            if project_id:
                task_data['GROUP_ID'] = project_id
            
            # Добавление дедлайна если указан
            if deadline:
                task_data['DEADLINE'] = deadline
            
            # Добавление дополнительных полей из метаданных
            additional_fields = self._extract_additional_fields(variables, metadata)
            task_data.update(additional_fields)

            # Добавление пользовательских полей UF_ из метаданных
            user_fields = self._extract_user_fields(metadata)
            task_data.update(user_fields)
            
            # Подготовка данных для отправки
            payload = {'fields': task_data}
            
            logger.debug(f"Отправка задачи в Bitrix24: {json.dumps(payload, ensure_ascii=False, indent=2)}")
            
            # Отправка POST запроса
            response = requests.post(
                self.task_add_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=self.config.request_timeout
            )
            
            # Проверка статуса ответа
            response.raise_for_status()
            
            # Возврат результата
            result = response.json()
            
            if result.get('error'):
                logger.error(f"Ошибка API Bitrix24: {result['error']}")
                logger.error(f"Описание ошибки: {result.get('error_description', 'Не указано')}")
                return result
            
            # Если задача создана успешно, создаем чек-листы
            if result.get('result') and result['result'].get('task'):
                created_task_id = result['result']['task'].get('id')
                if created_task_id:
                    # Извлекаем данные чек-листов
                    checklists_data = self._extract_checklists(metadata)
                    
                    if checklists_data:
                        logger.info(f"Создание чек-листов для задачи {created_task_id}")
                        # Создаем чек-листы синхронно
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
    
    def _extract_title(self, variables: Dict[str, Any], metadata: Dict[str, Any], topic: str) -> str:
        """Извлечение заголовка задачи из данных сообщения"""
        
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
    
    def _create_description(self, message_data: Dict[str, Any]) -> str:
        """Создание описания задачи (для отладки - все данные сообщения)"""
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
    
    def _extract_assignee_id(self, variables: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        """Извлечение ID роли (assigneeId) из extensionProperties"""
        # Проверяем наличие extensionProperties с assigneeId
        extension_properties = metadata.get("extensionProperties", {})
        if "assigneeId" in extension_properties:
            assignee_id = extension_properties["assigneeId"]
            if assignee_id:
                return str(assignee_id)
        
        # Fallback - возвращаем None если роль не найдена
        return None
    
    def _get_responsible_id_by_assignee(self, assignee_id: str) -> int:
        """
        Получение ID пользователя Bitrix24 по ID роли из Camunda
        Использует только JSON файл с соответствиями ролей
        
        Args:
            assignee_id: ID роли из Camunda
            
        Returns:
            ID пользователя Bitrix24
        """
        if not assignee_id:
            logger.warning("assignee_id не указан, используется default_responsible_id")
            return self.config.default_responsible_id
        
        # Проверяем кеш
        if not self._is_cache_valid():
            logger.info("Кеш соответствий ролей устарел или пуст, загружаем из файла...")
            if not self._load_roles_from_file():
                logger.error("Не удалось загрузить соответствия ролей из файла, используется default_responsible_id")
                return self.config.default_responsible_id
        
        # Ищем соответствие в кеше
        responsible_id = self._roles_cache.get(assignee_id)
        if responsible_id:
            logger.debug(f"Найдено соответствие: assignee_id={assignee_id} -> responsible_id={responsible_id}")
            return int(responsible_id)
        
        # Если соответствие не найдено
        logger.warning(f"Соответствие для assignee_id={assignee_id} не найдено, используется default_responsible_id")
        return self.config.default_responsible_id
    
    def _load_roles_from_file(self) -> bool:
        """
        Загрузка соответствий ролей из YAML файла
        
        Returns:
            True если загрузка успешна, False иначе
        """
        try:
            if self._roles_mapping_file.exists():
                with open(self._roles_mapping_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    
                    if not data or 'mappings' not in data:
                        logger.error(f"Неверный формат файла соответствий ролей: отсутствует секция 'mappings'")
                        return False
                    
                    # Извлекаем маппинги и создаем простой словарь для кеша
                    mappings = data['mappings']
                    roles_mapping = {}
                    
                    for assignee_id, role_info in mappings.items():
                        if isinstance(role_info, dict):
                            bitrix_id = role_info.get('bitrix_responsible_id')
                            
                            # Пропускаем записи без ID или с null
                            if bitrix_id is not None and bitrix_id != 'null':
                                roles_mapping[str(assignee_id)] = str(bitrix_id)
                                
                                assignee_name = role_info.get('assignee_name', 'Unknown')
                                logger.debug(f"Загружена роль: {assignee_name} ({assignee_id}) → {bitrix_id}")
                            else:
                                assignee_name = role_info.get('assignee_name', 'Unknown')
                                logger.warning(f"Пропущена роль без ID: {assignee_name} ({assignee_id})")
                    
                    # Обновляем кеш
                    self._roles_cache = roles_mapping
                    self._cache_timestamp = datetime.now()
                    
                    # Логирование результатов загрузки
                    diagram_info = data.get('diagram', {})
                    diagram_name = diagram_info.get('name', 'Unknown')
                    diagram_id = diagram_info.get('id', 'Unknown')
                    
                    logger.info(f"Загружено {len(roles_mapping)} соответствий ролей из файла {self._roles_mapping_file}")
                    logger.info(f"Диаграмма: {diagram_name} ({diagram_id})")
                    
                    if roles_mapping:
                        logger.debug(f"Активные соответствия: {roles_mapping}")
                    else:
                        logger.warning("Нет активных соответствий ролей - все записи имеют null в bitrix_responsible_id")
                    
                    return True
            else:
                logger.error(f"Файл соответствий ролей {self._roles_mapping_file} не найден")
                return False
                
        except yaml.YAMLError as e:
            logger.error(f"Ошибка парсинга YAML файла соответствий: {e}")
            return False
        except Exception as e:
            logger.error(f"Ошибка загрузки соответствий из файла: {e}")
            return False
    

    

    

    
    def _is_cache_valid(self) -> bool:
        """
        Проверка валидности кеша соответствий ролей
        
        Returns:
            True если кеш валиден, False иначе
        """
        if not self._cache_timestamp or not self._roles_cache:
            return False
        
        # Проверяем время жизни кеша
        cache_age = datetime.now() - self._cache_timestamp
        ttl_seconds = timedelta(seconds=self.config.roles_cache_ttl)
        
        return cache_age < ttl_seconds
    
    def refresh_roles_cache(self) -> bool:
        """
        Принудительное обновление кеша соответствий ролей
        Метод для диагностики и ручного обновления
        
        Returns:
            True если кеш успешно обновлен, False иначе
        """
        logger.info("Принудительное обновление кеша соответствий ролей из файла")
        return self._load_roles_from_file()
    
    def _extract_priority(self, variables: Dict[str, Any], metadata: Dict[str, Any]) -> int:
        """Извлечение приоритета задачи"""
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
    
    def _extract_deadline(self, variables: Dict[str, Any], metadata: Dict[str, Any]) -> Optional[str]:
        """Извлечение дедлайна задачи"""
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
    
    def _extract_project_id(self, variables: Dict[str, Any]) -> Optional[int]:
        """Извлечение ID проекта (GROUP_ID) из переменных процесса"""
        project_id = variables.get('projectId')
        if project_id:
            try:
                return int(project_id)
            except (ValueError, TypeError):
                logger.warning(f"Не удалось преобразовать projectId в число: {project_id}")
        return None
    
    def _extract_created_by_id(self, variables: Dict[str, Any]) -> int:
        """Извлечение ID постановщика задачи (CREATED_BY) из переменных процесса"""
        project_manager_id = variables.get('projectManagerId')
        if project_manager_id:
            try:
                return int(project_manager_id)
            except (ValueError, TypeError):
                logger.warning(f"Не удалось преобразовать projectManagerId в число: {project_manager_id}, используется responsible_id")
        
        # Fallback - используем responsible_id если projectManagerId не найден или некорректен
        assignee_id = self._extract_assignee_id(variables, {})
        return self._get_responsible_id_by_assignee(assignee_id)
    
    def _extract_additional_fields(self, variables: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Извлечение дополнительных полей для задачи"""
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
    
    def _extract_user_fields(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Извлечение пользовательских полей UF_ из метаданных
        
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
    
    def _extract_checklists(self, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Извлечение данных чек-листов из metadata.extensionProperties
        
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
            "success_rate": (
                self.stats["successful_tasks"] / self.stats["total_messages"] * 100
                if self.stats["total_messages"] > 0 else 0
            ),
            "success_queue_rate": (
                self.stats["sent_to_success_queue"] / self.stats["successful_tasks"] * 100
                if self.stats["successful_tasks"] > 0 else 0
            ),
            "last_message_time": self.stats["last_message_time"],
            "publisher_stats": self.publisher.get_stats()
        }
        
        # Определяем источник данных (теперь всегда файл)
        data_source = "unknown"
        if self._cache_timestamp:
            if self._roles_cache:
                data_source = "file"
            else:
                data_source = "empty"
        elif self._roles_mapping_file.exists():
            data_source = "file_not_loaded"
        
        base_stats['roles_cache'] = {
            'roles_cache_size': len(self._roles_cache),
            'cache_valid': self._is_cache_valid(),
            'cache_timestamp': self._cache_timestamp.isoformat() if self._cache_timestamp else None,
            'cache_ttl_seconds': bitrix_config.roles_cache_ttl,
            'data_source': data_source,
            'mapping_file': str(self._roles_mapping_file),
            'mapping_format': 'yaml',
            'file_exists': self._roles_mapping_file.exists()
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