#!/usr/bin/env python3
"""
Ручной скрипт для работы с API StormBPMN
Получение списка схем и вывод в консоль
"""
import json
import sys
from loguru import logger
from stormbpmn_client import StormBPMNClient, StormBPMNAuthError

# Простое логирование
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

def main():
    """Получить список первых 20 схем из StormBPMN"""
    
    try:
        # Создание клиента
        client = StormBPMNClient()
        logger.info("StormBPMN Client создан")
        
        # Получение списка схем
        logger.info("Запрос списка первых 20 схем...")
        diagrams = client.get_diagrams_list(size=20, page=0)
        
        # Вывод результата в консоль
        print("\n" + "="*80)
        print("СПИСОК СХЕМ ИЗ STORMBPMN")
        print("="*80)
        print(json.dumps(diagrams, ensure_ascii=False, indent=2))
        print("="*80)
        
        # Краткая статистика
        total = diagrams.get('totalElements', 0)
        content = diagrams.get('content', [])
        logger.info(f"Получено {len(content)} схем из {total} всего")
        
    except StormBPMNAuthError as e:
        logger.error(f"Ошибка аутентификации: {e}")
        logger.error("Установите STORMBPMN_BEARER_TOKEN")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 