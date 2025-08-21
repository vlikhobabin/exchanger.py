#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📋 Checklist Parser - Парсер чек-листов для Bitrix24

НАЗНАЧЕНИЕ:
    Извлекает чек-листы из описаний StormBPMN Activities и подготавливает их 
    для создания в Bitrix24. Поддерживает различные форматы ввода и предлагает
    оптимальный формат для пользователей.

ИСПОЛЬЗОВАНИЕ:
    python checklist_parser.py <assignees_json_file>

ПРИМЕРЫ:
    # Парсинг чек-листов из файла ответственных
    python checklist_parser.py "Процессы УУ. Модель для автоматизации_assignees.json"
    
    # Сохранение результата для интеграции с Bitrix24
    python checklist_parser.py assignees.json > bitrix_checklists.json

РЕЗУЛЬТАТ:
    Структурированные данные чек-листов в формате для Bitrix24:
    {
      "elementId": "Activity_123",
      "elementName": "Название задачи", 
      "checklists": [
        {
          "name": "Название чек-листа",
          "items": ["Пункт 1", "Пункт 2", ...]
        }
      ]
    }

ПОДДЕРЖИВАЕМЫЕ ФОРМАТЫ ВВОДА:
    1. ЧЕКЛИСТ: Название • Пункт 1 • Пункт 2 (РЕКОМЕНДУЕМЫЙ)
    2. <p>ЧЕКЛИСТ: Название</p><ul><li>Пункт</li></ul> (HTML)
    3. <p>ЧЕКЛИСТ: <a href="https://bx.eg-holding.ru/tasks/task/view/1566/">ссылка</a></p> (Bitrix24)
    4. ** Название <ul><li>Пункт</li></ul> (HTML - старый формат)
    5. @ Название [параграфы] (старый формат)
    6. # Название [списки] (старый формат)
    7. – Название [элементы] (старый формат)

НОВАЯ ФУНКЦИЯ - ЗАГРУЗКА ИЗ BITRIX24:
    - Если после "ЧЕКЛИСТ:" указана ссылка на задачу Bitrix24, то чек-листы загружаются из этой задачи
    - Поддерживаются ссылки вида: https://bx.eg-holding.ru/.../tasks/task/view/{id}/
    - Автоматическое использование конфигурации из task-creator.py/consumers/bitrix/config.py
    - Использует правильные API методы: tasks.task.get (GET) и task.checklistitem.getlist (GET)
    - Улучшенная обработка ошибок на основе существующих модулей

СТРОГИЕ ПРАВИЛА ПАРСИНГА:
    - Пункты должны идти СРАЗУ после заголовка чек-листа
    - Чек-листы без пунктов игнорируются
    - Пункты без заголовка "ЧЕКЛИСТ:" игнорируются
    - Между заголовком и пунктами не должно быть посторонего текста

ТРЕБОВАНИЯ:
    - Python 3.6+
    - requests (для загрузки из Bitrix24)
    - Конфигурация Bitrix24 (автоматически используется из task-creator.py при наличии)
    - Альтернативно: BITRIX_WEBHOOK_URL и BITRIX_REQUEST_TIMEOUT из переменных окружения
"""

import json
import re
import html
import sys
import os
import requests
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Импорт конфигурации Bitrix24 из существующего модуля
try:
    # Попытка импорта из task-creator.py модуля
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'task-creator.py'))
    from consumers.bitrix.config import bitrix_config
    BITRIX_CONFIG_AVAILABLE = True
    print(f"✅ Используется конфигурация Bitrix24 из task-creator.py", file=sys.stderr)
except ImportError:
    BITRIX_CONFIG_AVAILABLE = False
    print(f"⚠️ Конфигурация task-creator.py недоступна, используются переменные окружения", file=sys.stderr)

class ChecklistParser:
    """Парсер чек-листов для Bitrix24"""
    
    def __init__(self):
        # Поддерживаемые маркеры заголовков чек-листов
        self.header_patterns = [
            # Новый формат с ссылками на Bitrix24
            (r'<p>ЧЕКЛИСТ:\s*<a[^>]+href=["\']([^"\']*bx\.eg-holding\.ru[^"\']*)["\'][^>]*>.*?</a></p>', 'bitrix_link'),
            (r'<p>CHECKLIST:\s*<a[^>]+href=["\']([^"\']*bx\.eg-holding\.ru[^"\']*)["\'][^>]*>.*?</a></p>', 'bitrix_link'),
            
            # Рекомендуемый формат (HTML версия)
            (r'<p>ЧЕКЛИСТ:\s*([^<]+)</p>', 'optimal_html'),
            (r'<p>CHECKLIST:\s*([^<]+)</p>', 'optimal_html'),
            # Рекомендуемый формат (простой текст)
            (r'ЧЕКЛИСТ:\s*([^\n•]+)', 'optimal_text'),
            (r'CHECKLIST:\s*([^\n•]+)', 'optimal_text'),
            
            # Существующие форматы (для обратной совместимости)
            (r'\*\*\s*([^<\n]+)', 'double_asterisk'),
            (r'@\s*([^<\n]+)', 'at_symbol'),
            (r'#\s*([^<\n]+)', 'hash'),
            (r'–\s*([^<\n]+)', 'dash'),
        ]
        
        # Настройки Bitrix24 API - используем существующую конфигурацию
        if BITRIX_CONFIG_AVAILABLE:
            self.bitrix_webhook_url = bitrix_config.webhook_url
            self.bitrix_timeout = bitrix_config.request_timeout
            print(f"🔗 Bitrix24 URL: {self.bitrix_webhook_url[:50]}...", file=sys.stderr)
        else:
            self.bitrix_webhook_url = os.getenv('BITRIX_WEBHOOK_URL', '')
            self.bitrix_timeout = int(os.getenv('BITRIX_REQUEST_TIMEOUT', '30'))
        
        # Паттерны для пунктов списков
        self.item_patterns = [
            # Оптимальный формат с буллетами
            (r'•\s*([^\n•]+)', 'bullet'),
            
            # HTML списки
            (r'<li[^>]*>(.*?)</li>', 'html_li'),
            
            # Простые строки (для форматов @ и –)
            (r'<p>([^<]+)</p>', 'paragraph'),
        ]
    
    def clean_text(self, text: str) -> str:
        """Очистка текста от HTML тегов и лишних пробелов"""
        if not text:
            return ""
        
        # Декодируем HTML entities
        text = html.unescape(text)
        
        # Убираем HTML теги
        text = re.sub(r'<[^>]+>', '', text)
        
        # Убираем лишние пробелы и переносы
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def extract_checklists_from_description(self, description: str) -> List[Dict[str, Any]]:
        """Извлечение всех чек-листов из описания"""
        if not description:
            return []
        
        checklists = []
        clean_description = html.unescape(description)
        
        # Ищем заголовки чек-листов
        for header_pattern, format_type in self.header_patterns:
            header_matches = list(re.finditer(header_pattern, clean_description, re.IGNORECASE | re.MULTILINE))
            
            for match in header_matches:
                # Специальная обработка для ссылок на Bitrix24
                if format_type == 'bitrix_link':
                    task_url = match.group(1) if match.lastindex >= 1 else ''
                    
                    if task_url:
                        # Получаем чек-листы из Bitrix24 задачи (Task ID будет извлечен автоматически)
                        bitrix_checklists = self._get_checklists_from_bitrix_task(task_url)
                        checklists.extend(bitrix_checklists)
                    continue
                
                checklist_name = self.clean_text(match.group(1))
                if not checklist_name:
                    continue
                
                start_pos = match.end()
                
                # Определяем область поиска пунктов (до следующего заголовка или конца)
                end_pos = len(clean_description)
                for next_pattern, _ in self.header_patterns:
                    next_match = re.search(next_pattern, clean_description[start_pos:], re.IGNORECASE)
                    if next_match:
                        end_pos = min(end_pos, start_pos + next_match.start())
                
                search_area = clean_description[start_pos:end_pos]
                
                # СТРОГАЯ ПРОВЕРКА: пункты должны идти СРАЗУ после заголовка
                items = self._extract_items_strict(search_area, format_type)
                
                if items:  # Добавляем только если есть пункты
                    checklists.append({
                        'name': checklist_name,
                        'items': items,
                        'format_type': format_type,
                        'items_count': len(items)
                    })
        
        # Удаляем дубликаты (по названию)
        unique_checklists = []
        seen_names = set()
        for checklist in checklists:
            if checklist['name'] not in seen_names:
                unique_checklists.append(checklist)
                seen_names.add(checklist['name'])
        
        return unique_checklists
    
    def _extract_items_from_area(self, area: str, format_type: str) -> List[str]:
        """Извлечение пунктов из области текста"""
        items = []
        
        if format_type == 'optimal_html':
            # Для HTML формата оптимального чек-листа ищем HTML списки
            items = self._extract_html_list_items(area)
            if not items:
                items = self._extract_bullet_items(area)
            
        elif format_type == 'optimal_text':
            # Для текстового формата оптимального чек-листа ищем пункты с буллетами
            items = self._extract_bullet_items(area)
            
        elif format_type in ['double_asterisk', 'hash']:
            # Для HTML форматов сначала пробуем HTML списки, потом буллеты
            items = self._extract_html_list_items(area)
            if not items:
                items = self._extract_bullet_items(area)
                
        elif format_type in ['at_symbol', 'dash']:
            # Для @ и – форматов ищем параграфы и буллеты
            items = self._extract_paragraph_items(area)
            if not items:
                items = self._extract_bullet_items(area)
        
        # Очищаем и фильтруем пункты
        clean_items = []
        for item in items:
            clean_item = self.clean_text(item)
            if clean_item and len(clean_item) > 1:  # Минимальная длина
                clean_items.append(clean_item)
        
        return clean_items[:20]  # Ограничиваем количество пунктов
    
    def _extract_items_strict(self, area: str, format_type: str) -> List[str]:
        """СТРОГОЕ извлечение пунктов - только если они идут СРАЗУ после заголовка"""
        items = []
        
        if format_type == 'optimal_html':
            # Для HTML: после заголовка должен СРАЗУ идти <ul> список
            items = self._extract_html_items_strict(area)
            
        elif format_type == 'optimal_text':
            # Для текста: после заголовка должны СРАЗУ идти строки с буллетами  
            items = self._extract_text_items_strict(area)
            
        elif format_type in ['double_asterisk', 'hash']:
            # Для старых HTML форматов тоже строгая проверка
            items = self._extract_html_items_strict(area)
                
        elif format_type in ['at_symbol', 'dash']:
            # Для старых текстовых форматов строгая проверка
            items = self._extract_text_items_strict(area)
        
        return items
    
    def _extract_html_items_strict(self, area: str) -> List[str]:
        """СТРОГОЕ извлечение из HTML - <ul> должен идти сразу после заголовка"""
        items = []
        
        # Убираем пробельные символы в начале
        area_stripped = area.lstrip()
        
        # Убираем пустые параграфы и пробельные символы в начале
        # Разрешаем только пустые <p>&nbsp;</p> и <p></p> перед списком
        area_cleaned = re.sub(r'^(<p>(&nbsp;|\s*)</p>\s*)*', '', area_stripped, flags=re.IGNORECASE)
        
        # Проверяем, начинается ли область сразу с <ul> после очистки
        ul_match = re.match(r'^<ul[^>]*>(.*?)</ul>', area_cleaned, re.DOTALL | re.IGNORECASE)
        if ul_match:
            # Извлекаем пункты из найденного <ul>
            list_content = ul_match.group(1)
            li_matches = re.findall(r'<li[^>]*>(.*?)</li>', list_content, re.DOTALL)
            for li_content in li_matches:
                clean_item = self.clean_text(li_content)
                if clean_item and len(clean_item) > 1:
                    items.append(clean_item)
        
        return items[:20]  # Ограничиваем количество
    
    def _extract_text_items_strict(self, area: str) -> List[str]:
        """СТРОГОЕ извлечение из текста - буллеты должны идти сразу после заголовка"""
        items = []
        
        # Разбиваем на строки
        lines = area.strip().split('\n')
        
        # Проверяем строки последовательно
        for line in lines:
            line_stripped = line.strip()
            
            # Если строка пустая - пропускаем
            if not line_stripped:
                continue
            
            # Проверяем, является ли строка пунктом списка
            bullet_match = re.match(r'^[•\-*]\s*(.+)$', line_stripped)
            if bullet_match:
                item_text = bullet_match.group(1).strip()
                if item_text:
                    items.append(item_text)
            else:
                # Если встретили не пункт списка - прерываем (чек-лист закончился)
                break
        
        return items[:20]  # Ограничиваем количество
    
    def _extract_task_id_from_url(self, url: str) -> Optional[str]:
        """Извлечение Task ID из URL Bitrix24"""
        # Поддерживаем разные форматы URL
        patterns = [
            r'tasks/task/view/(\d+)',
            r'task/view/(\d+)',
            r'/(\d+)/?$'  # ID в конце URL
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _get_checklists_from_bitrix_task(self, task_url: str, task_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получение чек-листов из задачи Bitrix24 по API
        Улучшенная версия на основе существующих паттернов и вашего примера
        """
        # Извлекаем Task ID из URL если не передан
        if not task_id:
            task_id = self._extract_task_id_from_url(task_url)
        
        if not task_id:
            print(f"❌ Не удалось извлечь Task ID из URL: {task_url}", file=sys.stderr)
            return []
        
        if not self.bitrix_webhook_url:
            print(f"⚠️ BITRIX_WEBHOOK_URL не настроен, пропускаем загрузку из задачи {task_id}", file=sys.stderr)
            return []
        
        try:
            print(f"🔗 Загружаем чек-листы из задачи Bitrix24: {task_id}", file=sys.stderr)
            
            # Получаем информацию о задаче (как в tracker.py)
            task_response = self._bitrix_api_request(
                'tasks.task.get', 
                {'taskId': int(task_id)},  # Преобразуем в int как в tracker.py
                http_method='GET'
            )
            
            if not task_response or not task_response.get('task'):
                print(f"❌ Задача {task_id} не найдена в Bitrix24", file=sys.stderr)
                return []
            
            task_data = task_response['task']
            task_title = task_data.get('title', f'Задача {task_id}')
            
            # Получаем чек-листы задачи (улучшенная версия на основе вашего примера)
            print(f"📋 Запрос чек-листов для задачи {task_id}...", file=sys.stderr)
            checklist_response = self._bitrix_api_request(
                'task.checklistitem.getlist',  # Исправленный метод из вашего примера
                {'taskId': int(task_id)},       # Исправленный параметр из вашего примера
                http_method='GET'
            )
            
            if not checklist_response:
                print(f"⚠️ Чек-листы не найдены в задаче {task_id}", file=sys.stderr)
                return []
            
            # Проверяем тип ответа как в вашем примере
            if isinstance(checklist_response, list):
                print(f"📝 Получено {len(checklist_response)} элементов чек-листов для задачи {task_id}", file=sys.stderr)
                checklist_items = checklist_response
            else:
                print(f"⚠️ Неожиданный тип ответа для чек-листов задачи {task_id}: {type(checklist_response)}", file=sys.stderr)
                return []
            
            # Правильная логика для Bitrix24: PARENT_ID определяет иерархию
            # PARENT_ID = 0 → заголовок чек-листа
            # PARENT_ID = число → элемент чек-листа с этим родителем
            
            # Сначала находим все заголовки чек-листов (PARENT_ID = 0)
            checklists_headers = {}
            for item in checklist_items:
                if str(item.get('PARENT_ID', '0')) == '0' and item.get('TITLE'):
                    item_id = item['ID']
                    title = item['TITLE'].strip()
                    checklists_headers[item_id] = title
            
            # Затем собираем элементы для каждого чек-листа
            checklists_data = {}
            for header_id, header_title in checklists_headers.items():
                checklists_data[header_title] = []
            
            # Обрабатываем все элементы чек-листов (PARENT_ID != 0)
            for item in checklist_items:
                parent_id = str(item.get('PARENT_ID', '0'))
                if parent_id != '0' and parent_id in checklists_headers:
                    # Это элемент чек-листа
                    parent_title = checklists_headers[parent_id]
                    item_text = item.get('TITLE', '').strip()
                    
                    if item_text:
                        checklists_data[parent_title].append(item_text)
            
            # Преобразуем в нужный формат
            result_checklists = []
            for title, items in checklists_data.items():
                if items:  # Только непустые чек-листы
                    result_checklists.append({
                        'name': title,
                        'items': items,
                        'format_type': 'bitrix_api',
                        'items_count': len(items),
                        'source_task_id': task_id,
                        'source_url': task_url
                    })
            
            print(f"✅ Загружено {len(result_checklists)} чек-листов из задачи {task_id}", file=sys.stderr)
            return result_checklists
            
        except Exception as e:
            print(f"❌ Ошибка при загрузке чек-листов из Bitrix24 задачи {task_id}: {e}", file=sys.stderr)
            return []
    
    def _bitrix_api_request(self, method: str, params: Dict[str, Any], http_method: str = 'GET') -> Optional[Any]:
        """
        Улучшенное выполнение запроса к Bitrix24 API 
        На основе существующих паттернов из task-creator.py
        """
        try:
            url = f"{self.bitrix_webhook_url.rstrip('/')}/{method}.json"
            
            # Выбираем метод HTTP запроса как в существующих модулях
            if http_method.upper() == 'GET':
                response = requests.get(
                    url,
                    params=params,
                    timeout=self.bitrix_timeout,
                    headers={'Content-Type': 'application/json'}
                )
            else:
                response = requests.post(
                    url,
                    json=params,
                    timeout=self.bitrix_timeout,
                    headers={'Content-Type': 'application/json'}
                )
            
            response.raise_for_status()
            data = response.json()
            
            # Обработка ответа как в tracker.py
            if 'result' in data:
                return data['result']
            elif 'error' in data:
                error_msg = data.get('error_description', data.get('error', 'Unknown error'))
                print(f"❌ Bitrix24 API ошибка ({method}): {error_msg}", file=sys.stderr)
                return None
            else:
                print(f"⚠️ Неожиданный формат ответа от Bitrix24 API: {method}", file=sys.stderr)
                return data
                
        except requests.exceptions.Timeout:
            print(f"⏱️ Таймаут при запросе к Bitrix24 API: {method}", file=sys.stderr)
            return None
        except requests.exceptions.RequestException as e:
            print(f"🌐 Ошибка сети при запросе к Bitrix24 API ({method}): {e}", file=sys.stderr)
            return None
        except json.JSONDecodeError as e:
            print(f"📄 Ошибка декодирования JSON от Bitrix24 API ({method}): {e}", file=sys.stderr)
            return None
        except Exception as e:
            print(f"❌ Неожиданная ошибка при запросе к Bitrix24 API ({method}): {e}", file=sys.stderr)
            return None
    
    def _extract_bullet_items(self, area: str) -> List[str]:
        """Извлечение пунктов с буллетами (• или -)"""
        items = []
        # Ищем строки начинающиеся с буллетами
        bullet_matches = re.findall(r'[•\-*]\s*([^\n•\-*]+)', area)
        items.extend(bullet_matches)
        return items
    
    def _extract_html_list_items(self, area: str) -> List[str]:
        """Извлечение пунктов из HTML списков"""
        items = []
        
        # Ищем <ul> и <ol> списки
        list_matches = re.findall(r'<[uo]l[^>]*>(.*?)</[uo]l>', area, re.DOTALL)
        for list_content in list_matches:
            li_matches = re.findall(r'<li[^>]*>(.*?)</li>', list_content, re.DOTALL)
            items.extend(li_matches)
        
        return items
    
    def _extract_paragraph_items(self, area: str) -> List[str]:
        """Извлечение пунктов из параграфов"""
        items = []
        
        # Ищем короткие параграфы (вероятно пункты списка)
        paragraph_matches = re.findall(r'<p>([^<]{1,200})</p>', area)
        for p in paragraph_matches:
            clean_p = self.clean_text(p)
            # Пропускаем пустые строки и заголовки
            if clean_p and not any(marker in clean_p.lower() for marker in ['чек-лист', 'checklist']):
                items.append(clean_p)
                if len(items) >= 10:  # Ограничение для параграфов
                    break
        
        return items
    
    def parse_assignees_file(self, filepath: str) -> List[Dict[str, Any]]:
        """Парсинг файла с ответственными и извлечение чек-листов"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            raise ValueError(f'Ошибка чтения файла: {e}')
        
        results = []
        
        for item in data:
            description = item.get('description', '')
            element_id = item.get('elementId', '')
            element_name = item.get('elementName', '')
            
            if not description or not element_id:
                continue
            
            checklists = self.extract_checklists_from_description(description)
            
            if checklists:
                results.append({
                    'elementId': element_id,
                    'elementName': element_name,
                    'checklists': checklists,
                    'total_checklists': len(checklists),
                    'total_items': sum(c['items_count'] for c in checklists)
                })
        
        return results
    
    def generate_bitrix_format(self, parsed_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Генерация данных в формате для Bitrix24"""
        bitrix_data = {
            'version': '1.0',
            'created_by': 'StormBPMN Checklist Parser',
            'elements': []
        }
        
        for element_data in parsed_data:
            element_entry = {
                'element_id': element_data['elementId'],
                'element_name': element_data['elementName'],
                'checklists': []
            }
            
            for checklist in element_data['checklists']:
                checklist_entry = {
                    'title': checklist['name'],
                    'items': [
                        {
                            'text': item,
                            'is_complete': False
                        }
                        for item in checklist['items']
                    ]
                }
                element_entry['checklists'].append(checklist_entry)
            
            bitrix_data['elements'].append(element_entry)
        
        return bitrix_data

def main():
    """Основная функция парсера"""
    if len(sys.argv) != 2:
        print("❌ Использование: python checklist_parser.py <assignees_json_file>", file=sys.stderr)
        print("💡 Пример: python checklist_parser.py assignees.json", file=sys.stderr)
        return 1
    
    filepath = sys.argv[1]
    
    if not Path(filepath).exists():
        print(f"❌ Файл не найден: {filepath}", file=sys.stderr)
        return 1
    
    try:
        parser = ChecklistParser()
        
        # Парсим файл
        parsed_data = parser.parse_assignees_file(filepath)
        
        if not parsed_data:
            print("[]")  # Пустой массив если нет чек-листов
            return 0
        
        # Генерируем элементы для Bitrix24
        elements = []
        for element_data in parsed_data:
            element_entry = {
                'element_id': element_data['elementId'],
                'element_name': element_data['elementName'],
                'checklists': []
            }
            
            for checklist in element_data['checklists']:
                checklist_entry = {
                    'title': checklist['name'],
                    'items': [
                        {
                            'text': item,
                            'is_complete': False
                        }
                        for item in checklist['items']
                    ]
                }
                element_entry['checklists'].append(checklist_entry)
            
            elements.append(element_entry)
        
        # Выводим только массив elements
        print(json.dumps(elements, ensure_ascii=False, indent=2))
        
        return 0
        
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
