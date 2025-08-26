#!/usr/bin/env python3
"""
📥 StormBPMN XML Downloader - Загрузка BPMN диаграмм из StormBPMN

НАЗНАЧЕНИЕ:
    Загружает BPMN диаграмму в XML формате по ID из StormBPMN и сохраняет локально.
    Автоматически добавляет в XML метаданные диаграммы (id, название, статус, автор и др.)
    через extensionElements с custom namespace. Дополнительно получает и сохраняет 
    список ответственных для автоматической интеграции с процессом конвертации в Camunda.
    Идеально подходит для полного экспорта процессов из StormBPMN с сохранением метаданных.

ИСПОЛЬЗОВАНИЕ:
    python get_diagram_xml.py <diagram_id>

ПРИМЕРЫ:
    # Загрузить диаграмму по ID
    python get_diagram_xml.py 9d5687e5-6108-4f05-b46a-2d24b120ba9d
    
    # Загрузить несколько диаграмм (bash/cmd)
    for id in abc123 def456 ghi789; do python get_diagram_xml.py $id; done

РЕЗУЛЬТАТ:
    Создаются два файла в корне проекта:
    1. <diagram_name>.bpmn - BPMN диаграмма в XML формате с добавленными метаданными (готова для convert.py)
    2. <diagram_name>_assignees.json - список ответственных (автоматически используется convert.py)

ФОРМАТ МЕТАДАННЫХ:
    В корень <bpmn:definitions> добавляется блок:
    <bpmn:extensionElements>
        <custom:diagram>
            <custom:id>диаграмма_id</custom:id>
            <custom:name>название_диаграммы</custom:name>
            <custom:status>статус</custom:status>
            <custom:authorUsername>автор</custom:authorUsername>
            <custom:processedOn>2024-01-15T10:30:00</custom:processedOn>
            ... (все доступные поля из StormBPMN API)
        </custom:diagram>
    </bpmn:extensionElements>

ПРИМЕР РЕЗУЛЬТАТА:
    ✅ XML схемы сохранена в файл: Процесс_согласования.bpmn
    📝 Добавление метаданных диаграммы...
    ✅ Добавлены метаданные диаграммы: 18 полей
    ✅ Список ответственных сохранен в файл: Процесс_согласования_assignees.json
    📊 Получено 15 ответственных
    
    📊 Информация о схеме:
       - Название: Процесс согласования документов
       - ID: 9d5687e5-6108-4f05-b46a-2d24b120ba9d
       - Статус: ACTIVE
       - Автор: user.admin
       - Размер XML: 125,847 символов

ОСОБЕННОСТИ:
    - Автоматическая очистка имен файлов от недопустимых символов
    - Ограничение длины имени файла (200 символов)
    - Безопасное сохранение в UTF-8 кодировке
    - Автоматическое добавление метаданных диаграммы в BPMN XML через extensionElements
    - Использование custom namespace (xmlns:custom="http://eg-holding.ru/bpmn/custom")
    - Обработка ошибок при недоступности ответственных или метаданных

ТРЕБОВАНИЯ:
    - Python 3.6+
    - Библиотека loguru (pip install loguru)
    - Модуль stormbpmn_client.py в родительской папке
    - Переменная окружения:
      * STORMBPMN_BEARER_TOKEN - токен авторизации для StormBPMN API

НАСТРОЙКА:
    1. Получите Bearer Token из StormBPMN
    2. Добавьте STORMBPMN_BEARER_TOKEN в .env файл
    3. Найдите ID диаграммы с помощью get_diagrams_list.py

ТИПИЧНЫЙ WORKFLOW:
    1. python get_diagrams_list.py > list.json  # получить список диаграмм
    2. python get_diagram_xml.py <diagram_id>   # скачать нужную диаграмму
    3. python convert.py <diagram_name>.bpmn    # конвертировать для Camunda
    4. python deploy.py camunda_<diagram_name>.bpmn  # развернуть в Camunda

БЕЗОПАСНОСТЬ:
    - Все файлы сохраняются в корень проекта (не перезаписывают системные файлы)
    - Недопустимые символы в именах файлов автоматически заменяются на '_'
    - При ошибках загрузки ответственных основной процесс не прерывается
"""
import json
import sys
import os
import re
from pathlib import Path
from loguru import logger
import xml.etree.ElementTree as ET
from datetime import datetime

# Добавляем родительскую папку в путь для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stormbpmn_client import StormBPMNClient, StormBPMNAuthError, StormBPMNNotFoundError
from tools.logging_utils import setup_tool_logging

# Настройка полноценного логирования (консоль + файлы)
setup_tool_logging("get_diagram_xml")

def sanitize_filename(filename: str) -> str:
    """Очистка имени файла от недопустимых символов"""
    # Удаляем или заменяем недопустимые символы
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Убираем лишние пробелы и точки в конце
    sanitized = sanitized.strip('. ')
    # Ограничиваем длину
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    return sanitized

def add_diagram_metadata(xml_file_path: Path, diagram_data: dict) -> None:
    """
    Добавить метаданные диаграммы в BPMN XML файл
    
    Args:
        xml_file_path: Путь к XML файлу диаграммы
        diagram_data: Данные диаграммы из API StormBPMN
    """
    try:
        # Регистрируем namespaces для правильного парсинга
        ET.register_namespace('', 'http://www.omg.org/spec/BPMN/20100524/MODEL')
        ET.register_namespace('bpmn', 'http://www.omg.org/spec/BPMN/20100524/MODEL')
        ET.register_namespace('bpmndi', 'http://www.omg.org/spec/BPMN/20100524/DI')
        ET.register_namespace('dc', 'http://www.omg.org/spec/DD/20100524/DC')
        ET.register_namespace('di', 'http://www.omg.org/spec/DD/20100524/DI')
        ET.register_namespace('custom', 'http://eg-holding.ru/bpmn/custom')
        
        # Парсим XML файл
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        
        logger.debug(f"Парсинг XML файла: {xml_file_path}")
        
        # Ищем элемент definitions (корневой элемент)
        definitions = root
        if definitions.tag.endswith('}definitions'):
            # Добавляем custom namespace в атрибуты definitions
            definitions.set('xmlns:custom', 'http://eg-holding.ru/bpmn/custom')
            logger.debug("Добавлен custom namespace в definitions")
        else:
            logger.error(f"Не найден элемент definitions. Найден: {definitions.tag}")
            return
        
        # Проверяем, есть ли уже extensionElements в definitions
        extension_elements = None
        for child in definitions:
            if child.tag.endswith('}extensionElements'):
                extension_elements = child
                logger.debug("Найден существующий extensionElements")
                break
        
        # Если extensionElements не найден, создаем новый
        if extension_elements is None:
            # Определяем namespace для BPMN элементов
            bpmn_ns = ''
            if definitions.tag.startswith('{'):
                bpmn_ns = definitions.tag.split('}')[0] + '}'
            
            extension_elements = ET.Element(f'{bpmn_ns}extensionElements')
            # Вставляем extensionElements в начало definitions (после атрибутов)
            definitions.insert(0, extension_elements)
            logger.debug("Создан новый extensionElements")
        
        # Создаем custom:diagram элемент с метаданными
        custom_diagram = ET.SubElement(extension_elements, 'custom:diagram')
        
        # Добавляем метаданные из diagram_data
        metadata_fields = [
            'id', 'createdOn', 'updatedOn', 'updateBy', 'userFolderName', 'teamFolderName',
            'userFolderId', 'teamFolderId', 'favoritesCount', 'favored', 'name', 'status',
            'authorUsername', 'you', 'versionNumber', 'description', 'public', 'type',
            'tags', 'totalApprovals', 'trueApprovals', 'falseApprovals', 'outcommingLinks',
            'incommingLinks', 'autosaveIndex', 'processType', 'linkedDiagramId',
            'linkedDiagramName', 'teamId'
        ]
        
        added_count = 0
        for field in metadata_fields:
            value = diagram_data.get(field)
            if value is not None:
                # Конвертируем значение в строку
                if isinstance(value, bool):
                    str_value = str(value).lower()
                elif isinstance(value, (int, float)):
                    str_value = str(value)
                else:
                    str_value = str(value) if value else ''
                
                # Создаем элемент только если значение не пустое
                if str_value:
                    element = ET.SubElement(custom_diagram, f'custom:{field}')
                    element.text = str_value
                    added_count += 1
        
        # Добавляем timestamp обработки
        processed_element = ET.SubElement(custom_diagram, 'custom:processedOn')
        processed_element.text = datetime.now().isoformat()
        added_count += 1
        
        # Сохраняем обновленный XML
        # Используем метод write с xml_declaration для корректного UTF-8 вывода
        tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)
        
        logger.info(f"✅ Добавлены метаданные диаграммы: {added_count} полей")
        logger.debug(f"Метаданные добавлены в файл: {xml_file_path}")
        
    except ET.ParseError as e:
        logger.error(f"Ошибка парсинга XML: {e}")
        raise
    except Exception as e:
        logger.error(f"Ошибка при добавлении метаданных: {e}")
        raise

def save_diagram_xml(diagram_id: str) -> None:
    """Получить и сохранить XML схемы по ID"""
    
    try:
        # Создание клиента
        client = StormBPMNClient()
        logger.info(f"StormBPMN Client создан")
        
        # Получение данных схемы
        logger.info(f"Запрос схемы с ID: {diagram_id}")
        result = client.get_diagram_by_id(diagram_id)
        
        # Извлечение данных
        diagram = result.get('diagram', {})
        if not diagram:
            logger.error("Данные диаграммы не найдены в ответе")
            sys.exit(1)
        
        diagram_name = diagram.get('name', 'diagram')
        diagram_body = diagram.get('body', '')
        
        if not diagram_body:
            logger.error("XML данные диаграммы отсутствуют")
            sys.exit(1)
        
        # Очистка имени файла
        safe_filename = sanitize_filename(diagram_name)
        filename = f"{safe_filename}.bpmn"
        
        # Путь к файлу в корне проекта (на уровень выше от camunda-sync.py)
        root_path = Path(__file__).parent.parent.parent
        file_path = root_path / filename
        
        # Сохранение XML файла
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(diagram_body)
            
            logger.info(f"✅ XML схемы сохранена в файл: {file_path}")
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении XML файла: {e}")
            sys.exit(1)
        
        # Добавление метаданных диаграммы в XML
        logger.info(f"📝 Добавление метаданных диаграммы...")
        try:
            add_diagram_metadata(file_path, diagram)
        except Exception as e:
            logger.warning(f"⚠️ Не удалось добавить метаданные: {e}")
            logger.info("Продолжаем без метаданных...")
        
        # Получение и сохранение списка ответственных
        logger.info(f"📋 Запрос списка ответственных...")
        try:
            assignees = client.get_diagram_assignees(diagram_id)
            
            # Сохранение JSON файла с ответственными
            assignees_filename = f"{safe_filename}_assignees.json"
            assignees_file_path = root_path / assignees_filename
            
            with open(assignees_file_path, 'w', encoding='utf-8') as f:
                json.dump(assignees, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ Список ответственных сохранен в файл: {assignees_file_path}")
            logger.info(f"📊 Получено {len(assignees)} ответственных")
            
        except Exception as e:
            logger.warning(f"⚠️ Не удалось получить список ответственных: {e}")
            logger.info("Продолжаем без списка ответственных...")
        
        # Итоговая информация
        logger.info(f"📊 Информация о схеме:")
        logger.info(f"   - Название: {diagram_name}")
        logger.info(f"   - ID: {diagram.get('id', 'N/A')}")
        logger.info(f"   - Статус: {diagram.get('status', 'N/A')}")
        logger.info(f"   - Тип: {diagram.get('type', 'N/A')}")
        logger.info(f"   - Автор: {diagram.get('authorUsername', 'N/A')}")
        logger.info(f"   - Размер XML: {len(diagram_body)} символов")
        
    except StormBPMNNotFoundError:
        logger.error(f"❌ Схема с ID '{diagram_id}' не найдена")
        sys.exit(1)
    except StormBPMNAuthError as e:
        logger.error(f"❌ Ошибка аутентификации: {e}")
        logger.error("Установите STORMBPMN_BEARER_TOKEN")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        sys.exit(1)

def main():
    """Главная функция"""
    
    # Проверка аргументов
    if len(sys.argv) != 2:
        logger.error("Использование: python get_diagram_xml.py <diagram_id>")
        logger.error("Пример: python get_diagram_xml.py 9d5687e5-6108-4f05-b46a-2d24b120ba9d")
        sys.exit(1)
    
    diagram_id = sys.argv[1].strip()
    
    if not diagram_id:
        logger.error("ID диаграммы не может быть пустым")
        sys.exit(1)
    
    logger.info("🚀 Начинаем загрузку XML схемы...")
    save_diagram_xml(diagram_id)

if __name__ == "__main__":
    main() 