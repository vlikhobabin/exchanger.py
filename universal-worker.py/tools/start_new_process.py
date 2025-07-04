#!/usr/bin/env python3
"""
Быстрый запуск нового экземпляра TestProcess
"""

import sys
import os
import json
import requests
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import camunda_config

def get_camunda_url():
    base_url = camunda_config.base_url.rstrip('/')
    if base_url.endswith('/engine-rest'):
        return base_url
    else:
        return f"{base_url}/engine-rest"

def get_camunda_auth():
    if camunda_config.auth_enabled:
        return (camunda_config.auth_username, camunda_config.auth_password)
    return None

def make_request(method, url, **kwargs):
    try:
        auth = get_camunda_auth()
        response = requests.request(method, url, auth=auth, timeout=30, **kwargs)
        return response
    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return None

def start_new_process():
    print("🚀 ЗАПУСК НОВОГО TESTPROCESS V5")
    print("=" * 50)
    
    # Получаем определение процесса v5
    defs_url = f"{get_camunda_url()}/process-definition"
    params = {"key": "TestProcess", "version": "5"}
    
    response = make_request("GET", defs_url, params=params)
    if not response or response.status_code != 200:
        print("❌ Не удалось получить определение процесса v5")
        return None
    
    definitions = response.json()
    if not definitions:
        print("❌ TestProcess v5 не найден")
        return None
    
    process_def = definitions[0]
    def_id = process_def.get('id')
    print(f"📋 Найдено определение: {def_id}")
    
    # Запускаем новый процесс
    start_url = f"{get_camunda_url()}/process-definition/{def_id}/start"
    
    # Уникальные данные для нового экземпляра
    timestamp = int(time.time())
    payload = {
        "variables": {
            "Input_2khodeq": {
                "value": f"ErrorTest_{timestamp}",
                "type": "String"
            },
            "user": {
                "value": f"ErrorTestUser_{timestamp}",
                "type": "String"
            }
        },
        "businessKey": f"error-path-test-{timestamp}"
    }
    
    print(f"📤 Запуск процесса...")
    print(f"   Business Key: {payload['businessKey']}")
    
    response = make_request("POST", start_url, json=payload)
    
    if response and response.status_code == 200:
        result = response.json()
        instance_id = result.get('id')
        
        print(f"✅ Новый процесс запущен!")
        print(f"   Instance ID: {instance_id}")
        print(f"   Business Key: {result.get('businessKey')}")
        
        # Ждем немного и проверяем External Task
        print("\n⏳ Проверка External Task через 2 секунды...")
        time.sleep(2)
        
        tasks_url = f"{get_camunda_url()}/external-task"
        task_params = {"processInstanceId": instance_id}
        
        task_response = make_request("GET", tasks_url, params=task_params)
        if task_response and task_response.status_code == 200:
            tasks = task_response.json()
            if tasks:
                task = tasks[0]
                print(f"🔧 External Task создана:")
                print(f"   Task ID: {task.get('id')}")
                print(f"   Topic: {task.get('topicName')}")
                print(f"   Activity: {task.get('activityId')}")
        
        return {
            "instance_id": instance_id,
            "business_key": result.get('businessKey'),
            "definition_id": def_id
        }
    else:
        print(f"❌ Ошибка запуска процесса")
        if response:
            print(f"   Статус: {response.status_code}")
            print(f"   Ответ: {response.text}")
        return None

if __name__ == "__main__":
    start_new_process() 