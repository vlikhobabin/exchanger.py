#!/usr/bin/env python3
"""
Диагностика Universal Camunda Worker
"""

# Добавление родительского каталога в sys.path для импорта модулей проекта
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import camunda_config, routing_config

def check_topics():
    """Проверить топики в конфигурации"""
    topics = list(routing_config.TOPIC_TO_SYSTEM_MAPPING.keys())
    
    print(f"📋 КОНФИГУРАЦИЯ ТОПИКОВ:")
    print(f"   Всего топиков: {len(topics)}")
    
    # Поиск bitrix топиков
    bitrix_topics = [topic for topic in topics if 'bitrix' in topic.lower()]
    print(f"   Bitrix топики: {len(bitrix_topics)}")
    for topic in bitrix_topics:
        print(f"     - {topic}")
    
    # Проверка конкретного топика
    if 'bitrix_create_task' in topics:
        print(f"   ✅ bitrix_create_task НАЙДЕН в конфигурации")
        system = routing_config.get_system_for_topic('bitrix_create_task')
        print(f"   🎯 Система: {system}")
    else:
        print(f"   ❌ bitrix_create_task НЕ НАЙДЕН в конфигурации")
    
    return 'bitrix_create_task' in topics

def check_worker_config():
    """Проверить конфигурацию Worker"""
    print(f"\n🔧 КОНФИГУРАЦИЯ WORKER:")
    print(f"   Worker ID: {camunda_config.worker_id}")
    print(f"   Base URL: {camunda_config.base_url}")
    print(f"   Max Tasks: {camunda_config.max_tasks}")
    print(f"   Lock Duration: {camunda_config.lock_duration}")
    print(f"   Sorting: {repr(camunda_config.sorting)}")
    print(f"   Auth Enabled: {camunda_config.auth_enabled}")
    
    # Предупреждения
    if camunda_config.max_tasks == 1:
        print(f"   ⚠️ ВНИМАНИЕ: maxTasks = 1 - Worker может обрабатывать только 1 задачу одновременно!")
    elif camunda_config.max_tasks < 5:
        print(f"   ⚠️ ВНИМАНИЕ: maxTasks = {camunda_config.max_tasks} - возможны ограничения производительности")

def main():
    """Главная функция диагностики"""
    print("🔍 ДИАГНОСТИКА UNIVERSAL CAMUNDA WORKER")
    print("=" * 50)
    
    topic_ok = check_topics()
    check_worker_config()
    
    print(f"\n📊 ЗАКЛЮЧЕНИЕ:")
    if topic_ok:
        print(f"   ✅ Worker должен обрабатывать bitrix_create_task")
        if camunda_config.max_tasks == 1:
            print(f"   ⚠️ Проблема: Worker может обрабатывать только 1 задачу одновременно")
            print(f"   💡 Решение: Увеличить CAMUNDA_MAX_TASKS в .env до 5-10")
        else:
            print(f"   🎯 Worker настроен корректно")
    else:
        print(f"   ❌ Worker НЕ настроен для обработки bitrix_create_task")

if __name__ == "__main__":
    main() 