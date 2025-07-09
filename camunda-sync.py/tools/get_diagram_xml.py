#!/usr/bin/env python3
"""
Скрипт для получения XML схемы по ID и сохранения в файл
Использование: python get_diagram_xml.py <diagram_id>
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