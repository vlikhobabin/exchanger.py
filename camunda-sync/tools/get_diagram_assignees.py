#!/usr/bin/env python3
"""
👥 StormBPMN Assignees Tool - Получение ответственных по диаграмме

НАЗНАЧЕНИЕ:
    Получает список ответственных лиц для элементов конкретной BPMN диаграммы из StormBPMN.
    Используется для анализа назначений задач, подготовки данных для конвертации в Camunda,
    и аудита распределения ответственности по процессам.

ИСПОЛЬЗОВАНИЕ:
    python get_diagram_assignees.py <diagram_id>

ПРИМЕРЫ:
    # Получить ответственных по конкретной диаграмме
    python get_diagram_assignees.py 9d5687e5-6108-4f05-b46a-2d24b120ba9d
    
    # Сохранить результат в файл
    python get_diagram_assignees.py abc123-def456 > assignees.json
    
    # Получить ID диаграммы можно из get_diagrams_list.py
    python get_diagrams_list.py | grep "process_name" -A 5 -B 5

РЕЗУЛЬТАТ:
    - JSON список ответственных с детальной информацией
    - Статистика: общее количество, количество людей vs системных ответственных
    - Сводка по ответственным: кто и за сколько элементов отвечает
    
ФОРМАТ ВЫВОДА:
    [
      {
        "assigneeId": "123456",
        "assigneeName": "Иванов Иван Иванович",
        "assigneeType": "HUMAN",
        "elementId": "Activity_abc123",
        "elementName": "Проверка документов",
        "diagramId": "diagram-uuid"
      },
      ...
    ]
    
    📋 Краткая сводка:
       👤 Иванов И.И. (123456): 5 элементов
       👤 Петров П.П. (789012): 3 элемента

ТРЕБОВАНИЯ:
    - Python 3.6+
    - Библиотека loguru (pip install loguru)
    - Модуль stormbpmn_client.py в родительской папке
    - Переменная окружения:
      * STORMBPMN_BEARER_TOKEN - токен авторизации для StormBPMN API

НАСТРОЙКА:
    1. Получите Bearer Token из StormBPMN
    2. Добавьте STORMBPMN_BEARER_TOKEN в .env файл
    3. Найдите ID нужной диаграммы с помощью get_diagrams_list.py

ПРИМЕНЕНИЕ:
    - Подготовка данных для конвертации в Camunda (автоматическое встраивание ответственных)
    - Аудит назначений в процессах
    - Анализ нагрузки по исполнителям
    - Миграция ответственных между системами

ИНТЕГРАЦИЯ:
    Результат можно сохранить как *_assignees.json для использования в convert.py:
    python get_diagram_assignees.py <id> > process_assignees.json
    python convert.py process.bpmn  # автоматически подхватит assignees
"""
import json
import sys
import os
from loguru import logger

# Добавляем родительскую папку в путь для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stormbpmn_client import StormBPMNClient, StormBPMNAuthError, StormBPMNNotFoundError

# Настройка логирования
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

def get_diagram_assignees(diagram_id: str) -> None:
    """Получить и вывести список ответственных по ID диаграммы"""
    
    try:
        # Создание клиента
        client = StormBPMNClient()
        logger.info(f"StormBPMN Client создан")
        
        # Получение списка ответственных
        logger.info(f"Запрос ответственных для диаграммы: {diagram_id}")
        assignees = client.get_diagram_assignees(diagram_id)
        
        # Вывод результата в консоль
        print("\n" + "="*80)
        print("СПИСОК ОТВЕТСТВЕННЫХ ПО ДИАГРАММЕ")
        print("="*80)
        print(json.dumps(assignees, ensure_ascii=False, indent=2))
        print("="*80)
        
        # Краткая статистика
        logger.info(f"Получено {len(assignees)} ответственных")
        
        if assignees:
            # Группировка по типам для статистики
            human_count = sum(1 for item in assignees if item.get('assigneeType') == 'HUMAN')
            system_count = len(assignees) - human_count
            
            logger.info(f"Ответственных людей: {human_count}")
            if system_count > 0:
                logger.info(f"Системных ответственных: {system_count}")
            
            # Показываем краткую сводку по ответственным
            assignee_summary = {}
            for assignee in assignees:
                assignee_name = assignee.get('assigneeName', 'Без имени')
                assignee_id = assignee.get('assigneeId')
                element_id = assignee.get('elementId')
                
                if assignee_name not in assignee_summary:
                    assignee_summary[assignee_name] = {
                        'assignee_id': assignee_id,
                        'element_ids': set()
                    }
                
                if element_id:
                    assignee_summary[assignee_name]['element_ids'].add(element_id)
            
            print("\n📋 Краткая сводка по ответственным:")
            print("-" * 50)
            for assignee_name, data in assignee_summary.items():
                assignee_id = data['assignee_id']
                element_count = len(data['element_ids'])
                print(f"   👤 {assignee_name} ({assignee_id}): {element_count}")
        else:
            logger.info("Ответственные не найдены")
        
    except StormBPMNNotFoundError:
        logger.error(f"❌ Диаграмма с ID '{diagram_id}' не найдена")
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
        print("🎯 Получение списка ответственных по диаграмме из StormBPMN")
        print("=" * 60)
        print("📖 Использование:")
        print("   python get_diagram_assignees.py <diagram_id>")
        print()
        print("💡 Примеры:")
        print("   python get_diagram_assignees.py 9d5687e5-6108-4f05-b46a-2d24b120ba9d")
        print("   python get_diagram_assignees.py 1d5b8dcd-5a91-4895-9a2f-42a930d435ae")
        print()
        print("📝 Описание:")
        print("   Скрипт получает список ответственных по элементам диаграммы.")
        print("   Результат выводится в JSON формате для дальнейшей обработки.")
        print()
        print("🔧 Настройка:")
        print("   Убедитесь, что в .env установлен:")
        print("   - STORMBPMN_BEARER_TOKEN")
        sys.exit(1)
    
    diagram_id = sys.argv[1].strip()
    
    if not diagram_id:
        logger.error("ID диаграммы не может быть пустым")
        sys.exit(1)
    
    logger.info("🚀 Начинаем получение списка ответственных...")
    get_diagram_assignees(diagram_id)

if __name__ == "__main__":
    main() 