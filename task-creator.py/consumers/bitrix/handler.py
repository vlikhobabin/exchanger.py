#!/usr/bin/env python3
"""
Обработчик сообщений для создания задач в Bitrix24
"""
import os
import json
import time
import yaml
from pathlib import Path
from typing import Dict, Optional, Any
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
            description = self._create_description(message_data)
            
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