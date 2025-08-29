#!/usr/bin/env python3
"""
📋 StormBPMN Diagrams List Tool - Получение списка диаграмм из StormBPMN

НАЗНАЧЕНИЕ:
    Получает список BPMN диаграмм из StormBPMN через REST API и выводит их в JSON формате.
    Используется для обзора доступных схем, поиска нужных диаграмм по названию или ID,
    и анализа общей статистики процессов в системе.

ИСПОЛЬЗОВАНИЕ:
    python get_diagrams_list.py

ПРИМЕРЫ:
    # Получить первые 20 схем
    python get_diagrams_list.py
    
    # Перенаправить вывод в файл для анализа
    python get_diagrams_list.py > diagrams_list.json
    
    # Получить список и найти схему по названию (Linux/Mac)
    python get_diagrams_list.py | grep -i "название_процесса"

РЕЗУЛЬТАТ:
    - JSON список с информацией о диаграммах (первые 20)
    - Краткая статистика: количество полученных схем из общего числа
    - Для каждой диаграммы: ID, название, статус, автор, тип, даты создания/обновления

ФОРМАТ ВЫВОДА:
    {
      "content": [
        {
          "id": "diagram-uuid",
          "name": "Название процесса",
          "status": "ACTIVE",
          "authorUsername": "user.name",
          "type": "BPMN",
          "createdAt": "2024-01-01T12:00:00Z",
          ...
        }
      ],
      "totalElements": 150,
      "totalPages": 8,
      ...
    }

ТРЕБОВАНИЯ:
    - Python 3.6+
    - Библиотека loguru (pip install loguru)
    - Модуль stormbpmn_client.py в родительской папке
    - Переменная окружения:
      * STORMBPMN_BEARER_TOKEN - токен авторизации для StormBPMN API

НАСТРОЙКА:
    1. Получите Bearer Token из StormBPMN (настройки API → создать токен)
    2. Добавьте STORMBPMN_BEARER_TOKEN в .env файл
    3. Убедитесь в доступности StormBPMN сервера

ПРИМЕНЕНИЕ:
    - Поиск процессов перед конвертацией
    - Инвентаризация существующих диаграмм
    - Подготовка списка для массовой обработки
"""
import json
import sys
import os
from loguru import logger

# Добавляем родительскую папку в путь для импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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