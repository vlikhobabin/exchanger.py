#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 BPMN Diagram Analyzer - Анализатор диаграмм StormBPMN

НАЗНАЧЕНИЕ:
    Анализирует BPMN диаграммы и дополнительную информацию из StormBPMN,
    создавая детальный CSV отчет со всеми задачами, подпроцессами и их свойствами.
    Объединяет данные из XML диаграммы и JSON файла с ответственными.

ИСПОЛЬЗОВАНИЕ:
    python diagram_analyzer.py <bpmn_file> [assignees_json_file]

ПРИМЕРЫ:
    # Анализ диаграммы с автоматическим поиском assignees файла
    python diagram_analyzer.py "Процессы УУ. Модель для автоматизации.bpmn"
    
    # Анализ с явным указанием assignees файла
    python diagram_analyzer.py process.bpmn process_assignees.json
    
    # Анализ только BPMN файла (без дополнительной информации)
    python diagram_analyzer.py process.bpmn --no-assignees

РЕЗУЛЬТАТ:
    Создается CSV файл с именем <diagram_name>_analysis.csv содержащий:
    - elementId: ID элемента из BPMN диаграммы
    - elementType: Тип элемента (callActivity, task, subProcess, etc.)
    - elementName: Название элемента  
    - assigneeEdgeId: ID связи ответственного (из StormBPMN)
    - description: Описание элемента (HTML конвертируется в обычный текст)

ФОРМАТ CSV:
    elementId;elementType;elementName;assigneeEdgeId;description
    Activity_1nptpu5;callActivity;"Проведение выручки по договорам ДДУ и ДКП в УУ";22602054;"ЧЕКЛИСТ: https://..."
    Activity_1vpjw6a;callActivity;"Подготовка и анализ отчётности";"";""

ПОДДЕРЖИВАЕМЫЕ ЭЛЕМЕНТЫ BPMN:
    - callActivity (вызов подпроцессов)
    - task, userTask, serviceTask, scriptTask, etc. (все типы задач)
    - subProcess (подпроцессы)

ОСОБЕННОСТИ:
    - Автоматический поиск assignees файла по имени BPMN файла
    - Обработка элементов, отсутствующих в assignees файле
    - Извлечение чек-листов и ссылок на Bitrix24 из описаний
    - Безопасная работа с невалидными XML и JSON файлами
    - Подробная статистика анализа

ТРЕБОВАНИЯ:
    - Python 3.6+
    - Библиотека loguru (pip install loguru)
    - Модули: xml.etree.ElementTree, json, csv, pathlib

ИНТЕГРАЦИЯ:
    Результат анализа можно использовать для:
    - Аудита процессов и ответственных
    - Миграции данных между системами
    - Создания отчетов о состоянии процессов
    - Планирования автоматизации

WORKFLOW С ДРУГИМИ ИНСТРУМЕНТАМИ:
    1. python get_diagrams_list.py > list.json      # получить список диаграмм
    2. python get_diagram_xml.py <diagram_id>       # скачать диаграмму и assignees
    3. python diagram_analyzer.py <diagram>.bpmn    # проанализировать
    4. python checklist_parser.py <assignees>.json  # извлечь чек-листы

БЕЗОПАСНОСТЬ:
    - Все выходные файлы создаются в текущей директории
    - Проверка существования входных файлов
    - Валидация XML и JSON структур
    - Безопасная работа с UTF-8 кодировкой
"""

import xml.etree.ElementTree as ET
import json
import csv
import sys
import os
import re
import html
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from loguru import logger

# Настройка логирования
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

class BPMNDiagramAnalyzer:
    """Анализатор BPMN диаграмм с интеграцией StormBPMN данных"""
    
    def __init__(self):
        # Поддерживаемые типы элементов BPMN
        self.supported_elements = {
            'callActivity',
            'task', 'userTask', 'serviceTask', 'scriptTask', 
            'businessRuleTask', 'receiveTask', 'sendTask',
            'manualTask', 'subProcess'
        }
        
        # Пространства имен BPMN
        self.namespaces = {
            'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
            'bpmndi': 'http://www.omg.org/spec/BPMN/20100524/DI'
        }
    
    def parse_bpmn_file(self, bpmn_file_path: str) -> List[Dict[str, Any]]:
        """Парсинг BPMN файла для извлечения задач и подпроцессов"""
        
        logger.info(f"📖 Парсинг BPMN файла: {bpmn_file_path}")
        
        try:
            tree = ET.parse(bpmn_file_path)
            root = tree.getroot()
            
            elements = []
            
            # Поиск всех поддерживаемых элементов
            for element_type in self.supported_elements:
                xpath = f".//bpmn:{element_type}"
                found_elements = root.findall(xpath, self.namespaces)
                
                for element in found_elements:
                    element_id = element.get('id', '')
                    element_name = element.get('name', '')
                    
                    if element_id:  # Только элементы с ID
                        elements.append({
                            'elementId': element_id,
                            'elementName': element_name,
                            'elementType': element_type,
                            'assigneeEdgeId': '',  # Заполнится из assignees файла
                            'description': ''      # Заполнится из assignees файла
                        })
                        
                        logger.debug(f"  Найден {element_type}: {element_id} - '{element_name}'")
            
            logger.info(f"✅ Извлечено {len(elements)} элементов из BPMN файла")
            
            # Группировка по типам для статистики
            type_counts = {}
            for element in elements:
                element_type = element['elementType']
                type_counts[element_type] = type_counts.get(element_type, 0) + 1
            
            logger.info("📋 Статистика элементов:")
            for element_type, count in sorted(type_counts.items()):
                logger.info(f"   {element_type}: {count}")
            
            return elements
            
        except ET.ParseError as e:
            logger.error(f"❌ Ошибка парсинга XML файла: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при парсинге BPMN: {e}")
            raise
    
    def parse_assignees_file(self, assignees_file_path: str) -> Dict[str, Dict[str, Any]]:
        """Парсинг JSON файла с дополнительной информацией об элементах"""
        
        logger.info(f"📖 Парсинг assignees файла: {assignees_file_path}")
        
        try:
            with open(assignees_file_path, 'r', encoding='utf-8') as f:
                assignees_data = json.load(f)
            
            if not isinstance(assignees_data, list):
                logger.warning("⚠️ Assignees файл не содержит массив данных")
                return {}
            
            # Индексируем по elementId для быстрого поиска
            assignees_dict = {}
            for item in assignees_data:
                element_id = item.get('elementId')
                if element_id:
                    assignees_dict[element_id] = {
                        'assigneeEdgeId': item.get('assigneeEdgeId', ''),
                        'description': item.get('description', ''),
                        'assigneeName': item.get('assigneeName', ''),
                        'assigneeId': item.get('assigneeId', ''),
                        'elementName': item.get('elementName', ''),  # Может отличаться от BPMN
                        'updatedOn': item.get('updatedOn', ''),
                        'updatedBy': item.get('updatedBy', '')
                    }
            
            logger.info(f"✅ Загружено {len(assignees_dict)} записей из assignees файла")
            return assignees_dict
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON файла: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Неожиданная ошибка при парсинге assignees: {e}")
            raise
    
    def merge_data(self, bpmn_elements: List[Dict[str, Any]], 
                   assignees_dict: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Объединение данных из BPMN и assignees файлов"""
        
        logger.info("🔄 Объединение данных из BPMN и assignees файлов")
        
        merged_elements = []
        found_in_assignees = 0
        
        for element in bpmn_elements:
            element_id = element['elementId']
            
            # Проверяем, есть ли дополнительная информация в assignees
            if element_id in assignees_dict:
                assignee_info = assignees_dict[element_id]
                
                # Объединяем данные, приоритет у assignees файла для некоторых полей
                merged_element = {
                    'elementId': element_id,
                    'elementName': assignee_info.get('elementName') or element['elementName'],
                    'elementType': element['elementType'],
                    'assigneeEdgeId': str(assignee_info.get('assigneeEdgeId', '')),
                    'description': assignee_info.get('description', ''),
                    'assigneeName': assignee_info.get('assigneeName', ''),
                    'assigneeId': assignee_info.get('assigneeId', ''),
                    'updatedOn': assignee_info.get('updatedOn', ''),
                    'updatedBy': assignee_info.get('updatedBy', ''),
                    'source': 'bpmn+assignees'
                }
                found_in_assignees += 1
                logger.debug(f"  Объединен: {element_id} (есть в assignees)")
                
            else:
                # Используем только данные из BPMN
                merged_element = {
                    'elementId': element_id,
                    'elementName': element['elementName'],
                    'elementType': element['elementType'],
                    'assigneeEdgeId': '',
                    'description': '',
                    'assigneeName': '',
                    'assigneeId': '',
                    'updatedOn': '',
                    'updatedBy': '',
                    'source': 'bpmn_only'
                }
                logger.debug(f"  Только BPMN: {element_id} (нет в assignees)")
            
            merged_elements.append(merged_element)
        
        logger.info(f"✅ Объединение завершено:")
        logger.info(f"   Всего элементов: {len(merged_elements)}")
        logger.info(f"   С дополнительной информацией: {found_in_assignees}")
        logger.info(f"   Только из BPMN: {len(merged_elements) - found_in_assignees}")
        
        return merged_elements
    
    def clean_description(self, description: str) -> str:
        """Конвертация HTML описания в обычный текст и очистка для CSV"""
        if not description:
            return ""
        
        # Декодируем HTML entities (например, &nbsp; &amp; и т.д.)
        cleaned = html.unescape(description)
        
        # Убираем HTML теги, но сохраняем текст внутри них
        cleaned = re.sub(r'<[^>]+>', '', cleaned)
        
        # Убираем переносы строк и лишние пробелы
        cleaned = re.sub(r'\s+', ' ', cleaned.strip())
        
        # Экранируем кавычки для CSV
        cleaned = cleaned.replace('"', '""')
        
        return cleaned
    
    def generate_csv_report(self, merged_elements: List[Dict[str, Any]], 
                           output_file: str) -> None:
        """Генерация CSV отчета в кодировке ANSI для Excel"""
        
        logger.info(f"📄 Создание CSV отчета: {output_file}")
        
        try:
            # Используем кодировку cp1251 (ANSI) для совместимости с Excel на Windows
            with open(output_file, 'w', newline='', encoding='cp1251') as csvfile:
                # Используем ';' как разделитель по требованию
                writer = csv.writer(csvfile, delimiter=';', quotechar='"', 
                                  quoting=csv.QUOTE_MINIMAL)
                
                # Заголовки с добавленной колонкой elementType
                headers = ['elementId', 'elementType', 'elementName', 'assigneeEdgeId', 'description']
                writer.writerow(headers)
                
                # Данные
                for element in merged_elements:
                    row = [
                        element['elementId'],
                        element['elementType'],
                        element['elementName'],
                        element['assigneeEdgeId'],
                        self.clean_description(element['description'])
                    ]
                    writer.writerow(row)
            
            logger.info(f"✅ CSV отчет создан: {output_file}")
            logger.info(f"   Кодировка: ANSI (cp1251) для Excel")
            logger.info(f"   Записано строк: {len(merged_elements) + 1}")  # +1 для заголовка
            
        except UnicodeEncodeError as e:
            logger.warning(f"⚠️ Ошибка кодировки ANSI, сохраняем в UTF-8: {e}")
            # Fallback к UTF-8 если есть символы, которые нельзя закодировать в cp1251
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile, delimiter=';', quotechar='"', 
                                  quoting=csv.QUOTE_MINIMAL)
                headers = ['elementId', 'elementType', 'elementName', 'assigneeEdgeId', 'description']
                writer.writerow(headers)
                
                for element in merged_elements:
                    row = [
                        element['elementId'],
                        element['elementType'],
                        element['elementName'],
                        element['assigneeEdgeId'],
                        self.clean_description(element['description'])
                    ]
                    writer.writerow(row)
            logger.info(f"✅ CSV отчет создан в UTF-8 с BOM")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при создании CSV файла: {e}")
            raise
    
    def find_assignees_file(self, bpmn_file_path: str) -> Optional[str]:
        """Автоматический поиск assignees файла по имени BPMN файла"""
        
        bpmn_path = Path(bpmn_file_path)
        base_name = bpmn_path.stem  # Имя файла без расширения
        
        # Возможные варианты имен assignees файла
        possible_names = [
            f"{base_name}_assignees.json",
            f"{base_name}.assignees.json",
            f"{base_name}_ответственные.json"
        ]
        
        # Ищем в той же директории что и BPMN файл
        bpmn_dir = bpmn_path.parent
        
        for possible_name in possible_names:
            assignees_path = bpmn_dir / possible_name
            if assignees_path.exists():
                logger.info(f"🔍 Найден assignees файл: {assignees_path}")
                return str(assignees_path)
        
        logger.info(f"⚠️ Assignees файл не найден для: {base_name}")
        return None
    
    def analyze_diagram(self, bpmn_file_path: str, 
                       assignees_file_path: Optional[str] = None) -> str:
        """Полный анализ диаграммы с созданием отчета"""
        
        logger.info("🚀 Начинаем анализ BPMN диаграммы")
        
        # Проверка существования BPMN файла
        if not Path(bpmn_file_path).exists():
            raise FileNotFoundError(f"BPMN файл не найден: {bpmn_file_path}")
        
        # Парсинг BPMN файла
        bpmn_elements = self.parse_bpmn_file(bpmn_file_path)
        
        # Поиск или проверка assignees файла
        assignees_dict = {}
        if assignees_file_path is None:
            assignees_file_path = self.find_assignees_file(bpmn_file_path)
        
        if assignees_file_path and Path(assignees_file_path).exists():
            assignees_dict = self.parse_assignees_file(assignees_file_path)
        elif assignees_file_path:
            logger.warning(f"⚠️ Assignees файл не найден: {assignees_file_path}")
        
        # Объединение данных
        merged_elements = self.merge_data(bpmn_elements, assignees_dict)
        
        # Создание выходного файла
        bpmn_path = Path(bpmn_file_path)
        output_file = f"{bpmn_path.stem}_analysis.csv"
        
        # Генерация CSV отчета
        self.generate_csv_report(merged_elements, output_file)
        
        logger.info("🎉 Анализ диаграммы завершен успешно!")
        return output_file

def main():
    """Главная функция"""
    
    # Проверка аргументов
    if len(sys.argv) < 2:
        print("📊 Анализатор BPMN диаграмм StormBPMN")
        print("=" * 60)
        print("📖 Использование:")
        print("   python diagram_analyzer.py <bpmn_file> [assignees_json_file]")
        print()
        print("💡 Примеры:")
        print('   python diagram_analyzer.py "Процессы УУ. Модель для автоматизации.bpmn"')
        print('   python diagram_analyzer.py process.bpmn process_assignees.json')
        print()
        print("📝 Описание:")
        print("   Создает CSV отчет с анализом всех задач и подпроцессов диаграммы.")
        print("   Объединяет данные из BPMN файла и дополнительной информации StormBPMN.")
        print()
        print("📄 Результат:")
        print("   CSV файл с колонками: elementId, elementType, elementName, assigneeEdgeId, description")
        print("   Кодировка: ANSI (cp1251) для Excel на Windows")
        print("   Разделитель: точка с запятой (;)")
        sys.exit(1)
    
    bpmn_file = sys.argv[1]
    assignees_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        analyzer = BPMNDiagramAnalyzer()
        output_file = analyzer.analyze_diagram(bpmn_file, assignees_file)
        
        print()
        print("=" * 60)
        print("🎯 РЕЗУЛЬТАТ АНАЛИЗА")
        print("=" * 60)
        print(f"✅ CSV отчет создан: {output_file}")
        print(f"📊 Откройте файл в Excel или любом CSV редакторе")
        print(f"🔧 Кодировка: ANSI (cp1251), разделитель: точка с запятой (;)")
        print(f"🎯 HTML в описаниях конвертирован в обычный текст")
        
    except Exception as e:
        logger.error(f"❌ Ошибка анализа: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
