#!/usr/bin/env python3
"""
Скрипт для разблокировки заблокированных External Tasks
"""
import requests
from requests.auth import HTTPBasicAuth

# Добавление родительского каталога в sys.path для импорта модулей проекта
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import camunda_config

def unlock_task(task_id):
    """Разблокировать конкретную задачу"""
    print(f"🔓 Разблокировка задачи: {task_id}")
    
    # URL для разблокировки - правильное формирование с учетом /engine-rest
    base_url = camunda_config.base_url.rstrip('/')
    if base_url.endswith('/engine-rest'):
        unlock_url = f"{base_url}/external-task/{task_id}/unlock"
    else:
        unlock_url = f"{base_url}/engine-rest/external-task/{task_id}/unlock"
    
    # Аутентификация
    auth = None
    if camunda_config.auth_enabled:
        auth = HTTPBasicAuth(camunda_config.auth_username, camunda_config.auth_password)
    
    try:
        print(f"🌐 URL: {unlock_url}")
        
        response = requests.post(unlock_url, auth=auth, verify=False, timeout=10)
        
        if response.status_code == 204:
            print(f"✅ Задача {task_id} успешно разблокирована!")
            return True
        else:
            print(f"❌ Ошибка разблокировки: HTTP {response.status_code}")
            print(f"📄 Ответ: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка разблокировки: {e}")
        return False

def get_locked_tasks():
    """Получить список заблокированных задач"""
    print("🔍 Поиск заблокированных задач...")
    
    base_url = camunda_config.base_url.rstrip('/')
    if base_url.endswith('/engine-rest'):
        tasks_url = f"{base_url}/external-task"
    else:
        tasks_url = f"{base_url}/engine-rest/external-task"
    
    auth = None
    if camunda_config.auth_enabled:
        auth = HTTPBasicAuth(camunda_config.auth_username, camunda_config.auth_password)
    
    try:
        response = requests.get(tasks_url, auth=auth, verify=False, timeout=10)
        
        if response.status_code == 200:
            tasks = response.json()
            locked_tasks = [task for task in tasks if task.get('workerId') is not None]
            
            print(f"📋 Найдено заблокированных задач: {len(locked_tasks)}")
            
            for i, task in enumerate(locked_tasks, 1):
                print(f"\n🎯 Задача {i}:")
                print(f"   ID: {task.get('id')}")
                print(f"   Topic: {task.get('topicName')}")
                print(f"   Worker ID: {task.get('workerId')}")
                print(f"   Lock Expiration: {task.get('lockExpirationTime')}")
                
            return locked_tasks
        else:
            print(f"❌ Ошибка получения задач: HTTP {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return []

def unlock_all_test_tasks():
    """Разблокировать все задачи заблокированные тестовыми worker'ами"""
    print("🧹 Разблокировка всех тестовых задач...")
    
    locked_tasks = get_locked_tasks()
    # test_workers = ['test-direct-client', 'test-fetch-worker', 'test-fixed-worker', 'debug-test-worker']
    
    unlocked_count = 0
    
    for task in locked_tasks:
        worker_id = task.get('workerId', '')
        task_id = task.get('id')
        
        # if any(test_worker in worker_id for test_worker in test_workers):
        print(f"\n🎯 Найдена задача:")
        print(f"   Task ID: {task_id}")
        print(f"   Worker ID: {worker_id}")
        print(f"   Topic: {task.get('topicName')}")
        
        if unlock_task(task_id):
            unlocked_count += 1
    
    print(f"\n📊 Результат: разблокировано {unlocked_count} тестовых задач")
    return unlocked_count

def main():
    """Главная функция"""
    print("🔓 РАЗБЛОКИРОВКА EXTERNAL TASKS")
    print("=" * 50)
    print(f"🔗 Camunda URL: {camunda_config.base_url}")
    print(f"🔐 Аутентификация: {'Включена' if camunda_config.auth_enabled else 'Отключена'}")
    print()
    
    # Специфичная разблокировка известной задачи
    known_task_id = "93e739d5-5697-11f0-a3a6-00b436387543"
    print(f"🎯 Разблокировка известной задачи: {known_task_id}")
    
    if unlock_task(known_task_id):
        print("✅ Известная задача разблокирована!")
    else:
        print("⚠️ Не удалось разблокировать известную задачу")
    
    print("\n" + "=" * 50)
    
    # Разблокировка всех тестовых задач
    unlock_all_test_tasks()
    
    print("\n" + "=" * 50)
    print("✅ Разблокировка завершена!")

if __name__ == "__main__":
    main() 