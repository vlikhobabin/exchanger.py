#!/usr/bin/env python3
"""
Скрипт для получения списка ответственных по ID диаграммы
Использование: python get_diagram_assignees.py <diagram_id>
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