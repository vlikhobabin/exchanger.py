"""
Сервис для работы с предшественниками задач Bitrix24

Модуль содержит класс PredecessorService для управления зависимостями:
получение предшественников, создание зависимостей, получение результатов.
"""
import json
from typing import Any, Dict, List, Optional, Tuple

import requests
from loguru import logger


class PredecessorService:
    """
    Сервис для работы с предшественниками задач Bitrix24

    Предоставляет методы для получения ID предшественников,
    создания зависимостей между задачами, получения результатов
    предшествующих задач.
    """

    def __init__(
        self,
        config: Any,
        stats: Dict[str, int],
        user_service: Any,
        element_predecessors_cache: Dict[Tuple[Optional[str], Optional[str], str], List[str]],
        element_task_cache: Dict[Tuple[Optional[str], Optional[str]], Dict[str, Any]]
    ):
        """
        Инициализация сервиса предшественников

        Args:
            config: Конфигурация (webhook_url, request_timeout)
            stats: Словарь статистики для обновления счётчиков
            user_service: Сервис пользователей (для get_responsible_info)
            element_predecessors_cache: Кэш предшественников элементов
            element_task_cache: Кэш задач по element_id и process_instance_id
        """
        self.config = config
        self.stats = stats
        self.user_service = user_service
        self.element_predecessors_cache = element_predecessors_cache
        self.element_task_cache = element_task_cache

    def get_element_predecessor_ids(
        self,
        camunda_process_id: Optional[str],
        diagram_id: Optional[str],
        element_id: Optional[str],
        responsible_info: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Получение списка ID элементов-предшественников для указанного элемента диаграммы.

        Args:
            camunda_process_id: ID процесса Camunda (processDefinitionKey)
            diagram_id: ID диаграммы Storm
            element_id: ID элемента BPMN
            responsible_info: Информация об ответственном элементе (опционально)

        Returns:
            Список ID элементов-предшественников
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
            responsible_info = self.user_service.get_responsible_info(camunda_process_id, diagram_id, element_id)

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

    def apply_dependencies(
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
            process_instance_id: ID экземпляра процесса

        Returns:
            Список ID задач-предшественников в Bitrix24
        """
        if not element_id:
            logger.debug("Пропуск добавления предшественников: отсутствует elementId")
            return []

        predecessor_elements = self.get_element_predecessor_ids(
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
            existing_task = self.find_task_by_element_and_instance(predecessor_element_id, process_instance_id)
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

    def create_dependencies(self, task_id: int, predecessor_ids: List[int]) -> None:
        """
        Создание зависимостей задач через кастомный REST API Bitrix24.

        Args:
            task_id: ID созданной задачи
            predecessor_ids: Список ID задач-предшественников
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
                    logger.info(f"Добавлена зависимость: задача {task_id} зависит от {predecessor_id}")
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

    def get_task_results(self, task_id: int) -> List[Dict[str, Any]]:
        """
        Получение результатов задачи через API tasks.task.result.list
        и дополнительных данных о файлах через task.commentitem.get.

        Args:
            task_id: ID задачи в Bitrix24

        Returns:
            Список результатов с текстом и информацией о файлах
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

    def get_predecessor_results(
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
            results = self.get_task_results(task_id)
            if results:
                predecessor_results[task_id] = results
                logger.info(f"Получено {len(results)} результатов от задачи-предшественника {task_id}")

        return predecessor_results

    def build_results_block(
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

        lines = ["[B]Результаты предшествующих задач:[/B]"]
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
                        lines.append(f"  {text}")

                # Если есть файлы, указываем их
                files = result.get('files', [])
                if files:
                    file_names = [f.get('name', 'файл') for f in files]
                    lines.append(f"     Файлы: {', '.join(file_names)}")

            lines.append("")

        return "\n".join(lines)

    def find_task_by_element_and_instance(
        self,
        element_id: Optional[str],
        process_instance_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Поиск задачи в Bitrix24 по значениям пользовательских полей UF_ELEMENT_ID и UF_PROCESS_INSTANCE_ID.

        Args:
            element_id: ID элемента BPMN (activityId)
            process_instance_id: ID экземпляра процесса Camunda

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
