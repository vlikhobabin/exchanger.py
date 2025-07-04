#!/usr/bin/env python3
"""
Утилита для проверки статуса задачи в Camunda
"""

import sys
import os
import json
import requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import camunda_config

def check_task_status(task_id: str):
    """Проверка статуса задачи в Camunda"""
    print(f"🔍 Проверка статуса задачи {task_id} в Camunda")
    print("=" * 60)
    
    try:
        # Формируем базовый URL
        base_url = camunda_config.base_url.rstrip('/')
        if base_url.endswith('/engine-rest'):
            api_base_url = base_url
        else:
            api_base_url = f"{base_url}/engine-rest"
        
        # Настраиваем аутентификацию
        auth = None
        if camunda_config.auth_enabled:
            auth = (camunda_config.auth_username, camunda_config.auth_password)
            print(f"🔐 Аутентификация: {camunda_config.auth_username}")
        else:
            print("🔐 Аутентификация: не используется")
        
        print(f"🌐 Camunda URL: {api_base_url}")
        print()
        
        # 1. Проверяем задачу в External Tasks
        print("1️⃣ Проверка в External Tasks...")
        url = f"{api_base_url}/external-task/{task_id}"
        
        try:
            response = requests.get(url, auth=auth, timeout=10)
            print(f"   Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                task_data = response.json()
                print("   ✅ Задача найдена в External Tasks")
                print(f"   📝 Worker ID: {task_data.get('workerId', 'N/A')}")
                print(f"   📝 Topic: {task_data.get('topicName', 'N/A')}")
                print(f"   📝 Process Instance: {task_data.get('processInstanceId', 'N/A')}")
                print(f"   📝 Activity ID: {task_data.get('activityId', 'N/A')}")
                print(f"   📝 Lock Expiration: {task_data.get('lockExpirationTime', 'N/A')}")
                print(f"   📝 Retries: {task_data.get('retries', 'N/A')}")
                
                # Показываем переменные если есть
                if 'variables' in task_data and task_data['variables']:
                    print(f"   📝 Переменные: {json.dumps(task_data['variables'], ensure_ascii=False, indent=6)}")
                
            elif response.status_code == 404:
                print("   ❌ Задача НЕ найдена в External Tasks")
                print("   💡 Возможно задача уже завершена или не существует")
            else:
                print(f"   ❌ Ошибка: {response.status_code} - {response.text}")
                
        except requests.exceptions.Timeout:
            print("   ⏰ Таймаут запроса к Camunda")
        except Exception as e:
            print(f"   💥 Ошибка: {e}")
        
        print()
        
        # 2. Ищем задачу в активностях процесса
        print("2️⃣ Поиск в процессах...")
        url = f"{api_base_url}/external-task"
        params = {"processInstanceId": None}  # Будем искать без фильтра сначала
        
        try:
            response = requests.get(url, auth=auth, timeout=10, params={})
            print(f"   Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                tasks = response.json()
                print(f"   📊 Всего активных External Tasks: {len(tasks)}")
                
                # Ищем нашу задачу
                found_task = None
                for task in tasks:
                    if task.get('id') == task_id:
                        found_task = task
                        break
                
                if found_task:
                    print(f"   ✅ Задача {task_id} найдена в списке активных задач")
                else:
                    print(f"   ❌ Задача {task_id} НЕ найдена среди активных задач")
                    
                # Показываем похожие задачи по process instance
                print(f"\n   📋 Активные задачи (показываем первые 5):")
                for i, task in enumerate(tasks[:5]):
                    print(f"      {i+1}. ID: {task.get('id')}")
                    print(f"         Topic: {task.get('topicName')}")
                    print(f"         Process: {task.get('processInstanceId')}")
                    print(f"         Activity: {task.get('activityId')}")
                    print()
                
            else:
                print(f"   ❌ Ошибка: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"   💥 Ошибка: {e}")
        
        print()
        
        # 3. Проверяем историю
        print("3️⃣ Проверка в истории...")
        url = f"{api_base_url}/history/external-task-log"
        params = {"externalTaskId": task_id}
        
        try:
            response = requests.get(url, auth=auth, timeout=10, params=params)
            print(f"   Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                history = response.json()
                print(f"   📊 Записей в истории: {len(history)}")
                
                for i, record in enumerate(history):
                    print(f"   📝 Запись {i+1}:")
                    print(f"      Время: {record.get('timestamp', 'N/A')}")
                    print(f"      Состояние: {record.get('state', 'N/A')}")
                    print(f"      Ошибка: {record.get('errorMessage', 'N/A')}")
                    print()
                    
            else:
                print(f"   ❌ Ошибка: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"   💥 Ошибка: {e}")
            
    except Exception as e:
        print(f"💥 Общая ошибка: {e}")

def main():
    """Главная функция"""
    if len(sys.argv) != 2:
        print("📖 Использование: python check_task_status.py <task_id>")
        print()
        print("Примеры:")
        print("  python check_task_status.py fb57c8d1-57d5-11f0-a3a6-00b436387543")
        print("  python check_task_status.py bae9056d-57f6-11f0-a3a6-00b436387543")
        return
    
    task_id = sys.argv[1].strip()
    check_task_status(task_id)

if __name__ == "__main__":
    main() 