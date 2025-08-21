#!/usr/bin/env python3
"""
📥 StormBPMN XML Downloader - Загрузка BPMN диаграмм из StormBPMN

НАЗНАЧЕНИЕ:
    Загружает BPMN диаграмму в XML формате по ID из StormBPMN и сохраняет локально.
    Дополнительно получает и сохраняет список ответственных для автоматической
    интеграции с процессом конвертации в Camunda. Идеально подходит для полного
    экспорта процессов из StormBPMN.

ИСПОЛЬЗОВАНИЕ:
    python get_diagram_xml.py <diagram_id>

ПРИМЕРЫ:
    # Загрузить диаграмму по ID
    python get_diagram_xml.py 9d5687e5-6108-4f05-b46a-2d24b120ba9d
    
    # Загрузить несколько диаграмм (bash/cmd)
    for id in abc123 def456 ghi789; do python get_diagram_xml.py $id; done

РЕЗУЛЬТАТ:
    Создаются два файла в корне проекта:
    1. <diagram_name>.bpmn - BPMN диаграмма в XML формате (готова для convert.py)
    2. <diagram_name>_assignees.json - список ответственных (автоматически используется convert.py)

ПРИМЕР РЕЗУЛЬТАТА:
    ✅ XML схемы сохранена в файл: Процесс_согласования.bpmn
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
    - Обработка ошибок при недоступности ответственных

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

# Добавляем родительскую папку в путь для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stormbpmn_client import StormBPMNClient, StormBPMNAuthError, StormBPMNNotFoundError

# Настройка логирования
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

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