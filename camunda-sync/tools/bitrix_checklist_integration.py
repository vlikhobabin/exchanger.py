#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔗 Интеграция чек-листов с Bitrix24 Task Handler

НАЗНАЧЕНИЕ:
    Расширение для BitrixTaskHandler из task-creator.py для автоматического
    создания чек-листов в задачах на основе данных из checklist_parser.py

ИСПОЛЬЗОВАНИЕ:
    from bitrix_checklist_integration import BitrixChecklistIntegration
    
    integration = BitrixChecklistIntegration()
    success = integration.add_checklists_to_task(task_id, checklists_data)

ИНТЕГРАЦИЯ С СУЩЕСТВУЮЩИМИ МОДУЛЯМИ:
    - Использует конфигурацию из task-creator.py/consumers/bitrix/config.py
    - Совместим с BitrixTaskHandler 
    - Использует те же паттерны для API запросов

ТРЕБОВАНИЯ:
    - checklist_parser.py в той же директории
    - task-creator.py/consumers/bitrix/config.py (опционально)
    - Python 3.6+, requests
"""

import sys
import os
import json
import requests
from typing import List, Dict, Any, Optional
from pathlib import Path

# Импорт ChecklistParser из того же каталога
try:
    from checklist_parser import ChecklistParser
except ImportError:
    print("❌ Ошибка: checklist_parser.py не найден в той же директории", file=sys.stderr)
    sys.exit(1)

# Импорт конфигурации Bitrix24
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'task-creator.py'))
    from consumers.bitrix.config import bitrix_config
    BITRIX_CONFIG_AVAILABLE = True
    print(f"✅ Используется конфигурация Bitrix24 из task-creator.py", file=sys.stderr)
except ImportError:
    BITRIX_CONFIG_AVAILABLE = False
    print(f"⚠️ Конфигурация task-creator.py недоступна, используются переменные окружения", file=sys.stderr)


class BitrixChecklistIntegration:
    """Интеграция для создания чек-листов в задачах Bitrix24"""
    
    def __init__(self):
        # Настройки API
        if BITRIX_CONFIG_AVAILABLE:
            self.webhook_url = bitrix_config.webhook_url
            self.timeout = bitrix_config.request_timeout
        else:
            self.webhook_url = os.getenv('BITRIX_WEBHOOK_URL', '')
            self.timeout = int(os.getenv('BITRIX_REQUEST_TIMEOUT', '30'))
        
        if not self.webhook_url:
            raise ValueError("BITRIX_WEBHOOK_URL не настроен")
        
        # Парсер чек-листов
        self.parser = ChecklistParser()
    
    def add_checklists_to_task(self, task_id: int, checklists_data: List[Dict[str, Any]]) -> bool:
        """
        Добавление чек-листов к существующей задаче Bitrix24
        
        Args:
            task_id: ID задачи в Bitrix24
            checklists_data: Список чек-листов в формате из checklist_parser
            
        Returns:
            True если все чек-листы добавлены успешно, False иначе
        """
        if not checklists_data:
            print(f"⚠️ Нет чек-листов для добавления в задачу {task_id}", file=sys.stderr)
            return True
        
        success_count = 0
        total_items = 0
        
        try:
            for checklist in checklists_data:
                checklist_name = checklist.get('name', 'Чек-лист')
                items = checklist.get('items', [])
                
                if not items:
                    continue
                
                print(f"📋 Добавляем чек-лист '{checklist_name}' с {len(items)} пунктами в задачу {task_id}", file=sys.stderr)
                
                # Добавляем каждый пункт чек-листа
                for item_text in items:
                    if self._add_checklist_item(task_id, item_text):
                        success_count += 1
                    total_items += 1
            
            if success_count == total_items:
                print(f"✅ Все чек-листы добавлены в задачу {task_id}: {success_count}/{total_items}", file=sys.stderr)
                return True
            else:
                print(f"⚠️ Частично добавлены чек-листы в задачу {task_id}: {success_count}/{total_items}", file=sys.stderr)
                return False
        
        except Exception as e:
            print(f"❌ Ошибка при добавлении чек-листов в задачу {task_id}: {e}", file=sys.stderr)
            return False
    
    def _add_checklist_item(self, task_id: int, item_text: str) -> bool:
        """Добавление одного пункта чек-листа к задаче"""
        try:
            # Используем правильный API метод для добавления пункта чек-листа
            method = 'tasks.task.checklist.add'
            params = {
                'taskId': task_id,
                'fields': {
                    'TITLE': item_text,
                    'IS_COMPLETE': 'N'
                }
            }
            
            result = self._bitrix_api_request(method, params, http_method='POST')
            
            if result:
                print(f"  ✅ Добавлен пункт: {item_text}", file=sys.stderr)
                return True
            else:
                print(f"  ❌ Ошибка добавления пункта: {item_text}", file=sys.stderr)
                return False
        
        except Exception as e:
            print(f"  ❌ Исключение при добавлении пункта '{item_text}': {e}", file=sys.stderr)
            return False
    
    def _bitrix_api_request(self, method: str, params: Dict[str, Any], http_method: str = 'GET') -> Optional[Any]:
        """Выполнение запроса к Bitrix24 API (аналогично checklist_parser)"""
        try:
            url = f"{self.webhook_url.rstrip('/')}/{method}.json"
            
            if http_method.upper() == 'GET':
                response = requests.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                    headers={'Content-Type': 'application/json'}
                )
            else:
                response = requests.post(
                    url,
                    json=params,
                    timeout=self.timeout,
                    headers={'Content-Type': 'application/json'}
                )
            
            response.raise_for_status()
            data = response.json()
            
            if 'result' in data:
                return data['result']
            elif 'error' in data:
                error_msg = data.get('error_description', data.get('error', 'Unknown error'))
                print(f"❌ Bitrix24 API ошибка ({method}): {error_msg}", file=sys.stderr)
                return None
            else:
                return data
                
        except requests.exceptions.RequestException as e:
            print(f"🌐 Ошибка сети при запросе к Bitrix24 API ({method}): {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"❌ Ошибка при запросе к Bitrix24 API ({method}): {e}", file=sys.stderr)
            return None
    
    def parse_and_add_checklists(self, task_id: int, assignees_json_file: str, element_id: str = None) -> bool:
        """
        Полная интеграция: парсинг чек-листов из файла и добавление к задаче
        
        Args:
            task_id: ID задачи в Bitrix24
            assignees_json_file: Путь к файлу с ответственными (и чек-листами)
            element_id: Конкретный element_id для фильтрации (опционально)
            
        Returns:
            True если успешно, False иначе
        """
        try:
            # Парсим чек-листы из файла
            parsed_data = self.parser.parse_assignees_file(assignees_json_file)
            
            if not parsed_data:
                print(f"⚠️ Чек-листы не найдены в файле {assignees_json_file}", file=sys.stderr)
                return True  # Не ошибка, просто нет чек-листов
            
            # Фильтруем по element_id если указан
            if element_id:
                filtered_data = [item for item in parsed_data if item.get('elementId') == element_id]
                if not filtered_data:
                    print(f"⚠️ Чек-листы для элемента {element_id} не найдены", file=sys.stderr)
                    return True
                parsed_data = filtered_data
            
            # Добавляем все чек-листы к задаче
            total_success = True
            for element_data in parsed_data:
                checklists = element_data.get('checklists', [])
                if checklists:
                    element_name = element_data.get('elementName', 'Неизвестный элемент')
                    print(f"🔄 Обрабатываем чек-листы для элемента: {element_name}", file=sys.stderr)
                    
                    success = self.add_checklists_to_task(task_id, checklists)
                    if not success:
                        total_success = False
            
            return total_success
        
        except Exception as e:
            print(f"❌ Ошибка при парсинге и добавлении чек-листов: {e}", file=sys.stderr)
            return False


# Функция для простого использования
def add_checklists_from_file(task_id: int, assignees_json_file: str, element_id: str = None) -> bool:
    """
    Простая функция для добавления чек-листов к задаче Bitrix24
    
    Args:
        task_id: ID задачи в Bitrix24
        assignees_json_file: Путь к файлу с ответственными 
        element_id: Конкретный element_id для фильтрации (опционально)
        
    Returns:
        True если успешно, False иначе
    """
    try:
        integration = BitrixChecklistIntegration()
        return integration.parse_and_add_checklists(task_id, assignees_json_file, element_id)
    except Exception as e:
        print(f"❌ Ошибка интеграции чек-листов: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    # Простой CLI интерфейс для тестирования
    if len(sys.argv) < 3:
        print("Использование: python bitrix_checklist_integration.py <task_id> <assignees_json_file> [element_id]")
        print("Пример: python bitrix_checklist_integration.py 1566 assignees.json Activity_123")
        sys.exit(1)
    
    task_id = int(sys.argv[1])
    assignees_file = sys.argv[2]
    element_id = sys.argv[3] if len(sys.argv) > 3 else None
    
    print(f"🚀 Добавление чек-листов к задаче {task_id} из файла {assignees_file}")
    if element_id:
        print(f"   Фильтр по element_id: {element_id}")
    
    success = add_checklists_from_file(task_id, assignees_file, element_id)
    
    if success:
        print(f"✅ Чек-листы успешно добавлены к задаче {task_id}")
        sys.exit(0)
    else:
        print(f"❌ Ошибка при добавлении чек-листов к задаче {task_id}")
        sys.exit(1)
