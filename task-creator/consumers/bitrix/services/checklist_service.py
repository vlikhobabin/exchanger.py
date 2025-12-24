"""
Сервис для работы с чек-листами задач Bitrix24

Модуль содержит класс ChecklistService для управления чек-листами:
создание, удаление, очистка и извлечение из шаблонов.
"""
from typing import Any, Dict, List, Optional

from loguru import logger

from ..clients import BitrixAPIClient


class ChecklistService:
    """
    Сервис для работы с чек-листами задач Bitrix24

    Предоставляет методы для создания, удаления и управления
    чек-листами задач через API Bitrix24.
    """

    def __init__(self, bitrix_client: BitrixAPIClient):
        """
        Инициализация сервиса чек-листов

        Args:
            bitrix_client: Клиент API Bitrix24
        """
        self.bitrix_client = bitrix_client

    def extract_from_template(self, template_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Извлечение чек-листов из шаблона и преобразование в формат для create_checklists_sync()

        Args:
            template_data: Данные шаблона из API (result.data)

        Returns:
            Список чек-листов в формате [{"name": "...", "items": ["...", "..."]}, ...]
        """
        checklists = template_data.get('checklists', {})
        items = checklists.get('items', [])

        if not items:
            logger.debug("Нет элементов чек-листов в шаблоне")
            return []

        # Группируем элементы по родительским элементам (уровень 0)
        checklist_groups = {}

        # Первый проход: определяем корневые элементы (группы чек-листов)
        for item_data in items:
            item = item_data.get('item', {})
            tree = item_data.get('tree', {})

            title = item.get('TITLE', '')
            if not title:
                continue

            # Приводим ID к строке для консистентности
            item_id = str(item.get('ID'))
            parent_id = tree.get('parent_id')
            # Приводим parent_id к строке, если он не None
            parent_id_str = str(parent_id) if parent_id is not None else None
            level = tree.get('level', 0)

            # Если это корневой элемент (level == 0)
            # В древовидной структуре parent_id корневого элемента равен самому item_id
            if level == 0:
                # Это группа чек-листа
                checklist_groups[item_id] = {
                    'name': title,
                    'items': []
                }
                logger.debug(f"Найдена группа чек-листа: ID={item_id}, name='{title}'")

        # Второй проход: собираем дочерние элементы для каждой группы
        for item_data in items:
            item = item_data.get('item', {})
            tree = item_data.get('tree', {})

            title = item.get('TITLE', '')
            if not title:
                continue

            item_id = str(item.get('ID'))
            parent_id = tree.get('parent_id')
            parent_id_str = str(parent_id) if parent_id is not None else None
            level = tree.get('level', 0)

            # Если это дочерний элемент (level > 0)
            if level > 0 and parent_id_str and parent_id_str in checklist_groups:
                # Добавляем элемент в соответствующую группу
                checklist_groups[parent_id_str]['items'].append(title)
                logger.debug(f"Добавлен элемент '{title}' в группу {parent_id_str}")

        # Преобразуем в список
        result = list(checklist_groups.values())

        # Логируем детальную информацию о каждом чек-листе
        logger.info(f"Извлечено {len(result)} чек-листов из шаблона:")
        for i, checklist in enumerate(result, 1):
            logger.info(f"  Чек-лист {i}: name='{checklist.get('name')}', items={len(checklist.get('items', []))} шт.")
            for j, item in enumerate(checklist.get('items', []), 1):
                logger.debug(f"    - {j}. {item}")

        return result

    # ========== СИНХРОННЫЕ МЕТОДЫ ==========

    def create_group_sync(self, task_id: int, title: str) -> Optional[int]:
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
        result = self.bitrix_client.request_sync('POST', api_method, params)
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

    def add_item_sync(self, task_id: int, title: str, is_complete: bool = False,
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
        result = self.bitrix_client.request_sync('POST', api_method, params)
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

    def create_checklists_sync(self, task_id: int, checklists_data: List[Dict[str, Any]]) -> bool:
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
                    group_id = self.create_group_sync(task_id, checklist_name)

                    if group_id:
                        total_groups += 1
                        logger.debug(f"Создана группа '{checklist_name}' с ID {group_id}")

                        # Создаем элементы чек-листа в группе
                        for item_text in checklist_items:
                            if isinstance(item_text, str) and item_text.strip():
                                item_id = self.add_item_sync(
                                    task_id=task_id,
                                    title=item_text.strip(),
                                    is_complete=False,
                                    parent_id=group_id
                                )

                                if item_id:
                                    total_items += 1
                                    logger.debug(f"Создан элемент '{item_text}' с ID {item_id}")
                                else:
                                    errors_count += 1
                                    logger.error(f"Не удалось создать элемент '{item_text}' в группе {group_id}")
                            else:
                                logger.warning(f"Пропущен некорректный элемент чек-листа: {item_text}")
                    else:
                        errors_count += 1
                        logger.error(f"Не удалось создать группу '{checklist_name}', пропускаем её элементы")

                except Exception as e:
                    errors_count += 1
                    logger.error(f"Ошибка создания чек-листа '{checklist_name}': {e}")

            # Логируем результаты
            if total_groups > 0 or total_items > 0:
                logger.info(f"Создано чек-листов для задачи {task_id}: {total_groups} групп, {total_items} элементов")

            if errors_count > 0:
                logger.error(f"Ошибки при создании чек-листов задачи {task_id}: {errors_count} ошибок")
                return False

            return True

        except Exception as e:
            logger.error(f"Критическая ошибка при создании чек-листов задачи {task_id}: {e}")
            return False

    # ========== АСИНХРОННЫЕ МЕТОДЫ ==========

    async def create_group_async(self, task_id: int, title: str) -> Optional[int]:
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
        result = await self.bitrix_client.request_async('POST', api_method, params)
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

    async def add_item_async(self, task_id: int, title: str, is_complete: bool = False,
                             parent_id: Optional[int] = None) -> Optional[int]:
        """
        Добавляет элемент в чек-лист задачи.

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
        result = await self.bitrix_client.request_async('POST', api_method, params)
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

    async def get_checklists_async(self, task_id: int) -> List[Dict[str, Any]]:
        """
        Получает чек-листы задачи.

        :param task_id: ID задачи
        :return: Список чек-листов задачи
        """
        api_method = 'task.checklistitem.getlist'
        params = {'taskId': task_id}
        logger.debug(f"Запрос чек-листов для задачи {task_id}...")
        result = await self.bitrix_client.request_async('GET', api_method, params)
        if result:
            if isinstance(result, list):
                logger.debug(f"Получено {len(result)} элементов чек-листов для задачи {task_id}")

                return result
            else:
                logger.warning(f"Неожиданный тип ответа для чек-листов задачи {task_id}: {type(result)}")
                return []
        return []

    async def delete_item_async(self, item_id: int, task_id: int) -> bool:
        """
        Удаляет элемент чек-листа.

        :param item_id: ID элемента чек-листа
        :param task_id: ID задачи
        :return: True в случае успеха, иначе False
        """
        api_method = 'tasks.task.checklist.delete'
        params = {'taskId': task_id, 'checkListItemId': item_id}
        result = await self.bitrix_client.request_async('POST', api_method, params)
        return bool(result)

    async def clear_checklists_async(self, task_id: int) -> bool:
        """
        Очищает все чек-листы задачи.

        :param task_id: ID задачи
        :return: True в случае успеха
        """
        try:
            # Получаем все элементы чек-листов
            items = await self.get_checklists_async(task_id)

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
                        success = await self.delete_item_async(int(item_id), task_id)
                        if success:
                            deleted_count += 1
                            logger.debug(f"Удален ID:{item_id} - '{item_title}'")
                        else:
                            errors_count += 1
                            logger.error(f"НЕ УДАЛЕН ID:{item_id} - '{item_title}'")
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
                        logger.error(f"ОШИБКА ID:{item_id} '{item_title}': {e}")
                else:
                    logger.warning(f"Элемент без ID пропущен: '{item_title}'")

            # Логируем результаты
            if deleted_count > 0:
                logger.info(f"Успешно удалено {deleted_count} элементов чек-листов задачи {task_id}")

            if errors_count > 0:
                logger.error(f"Не удалось удалить {errors_count} элементов чек-листов задачи {task_id}:")
                for failed_item in failed_items[:5]:  # Показываем первые 5 ошибок для краткости
                    logger.error(f"   Элемент {failed_item['item_id']} '{failed_item['title']}': {failed_item['error']}")
                if len(failed_items) > 5:
                    logger.error(f"   ... и еще {len(failed_items) - 5} ошибок")

            # Возвращаем True только если все элементы удалены успешно
            if errors_count == 0:
                return True
            else:
                logger.error(f"Очистка чек-листов задачи {task_id} завершена с ошибками: {errors_count}/{len(items)} элементов не удалось удалить")
                return False

        except Exception as e:
            logger.warning(f"Ошибка очистки чек-листов задачи {task_id}: {e}")
            return False

    async def create_checklists_async(self, task_id: int, checklists_data: List[Dict[str, Any]]) -> bool:
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
                    group_id = await self.create_group_async(task_id, checklist_name)

                    if group_id:
                        total_groups += 1
                        logger.debug(f"Создана группа '{checklist_name}' с ID {group_id}")

                        # Создаем элементы чек-листа в группе
                        for item_text in checklist_items:
                            if isinstance(item_text, str) and item_text.strip():
                                item_id = await self.add_item_async(
                                    task_id=task_id,
                                    title=item_text.strip(),
                                    is_complete=False,
                                    parent_id=group_id
                                )

                                if item_id:
                                    total_items += 1
                                    logger.debug(f"Создан элемент '{item_text}' с ID {item_id}")
                                else:
                                    errors_count += 1
                                    logger.error(f"Не удалось создать элемент '{item_text}' в группе {group_id}")
                            else:
                                logger.warning(f"Пропущен некорректный элемент чек-листа: {item_text}")
                    else:
                        errors_count += 1
                        logger.error(f"Не удалось создать группу '{checklist_name}', пропускаем её элементы")

                except Exception as e:
                    errors_count += 1
                    logger.error(f"Ошибка создания чек-листа '{checklist_name}': {e}")

            # Логируем результаты
            if total_groups > 0 or total_items > 0:
                logger.info(f"Создано чек-листов для задачи {task_id}: {total_groups} групп, {total_items} элементов")

            if errors_count > 0:
                logger.error(f"Ошибки при создании чек-листов задачи {task_id}: {errors_count} ошибок")
                return False

            return True

        except Exception as e:
            logger.error(f"Критическая ошибка при создании чек-листов задачи {task_id}: {e}")
            return False
