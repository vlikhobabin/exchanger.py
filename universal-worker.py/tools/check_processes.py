#!/usr/bin/env python3
"""
Проверка состояния процессов в Camunda
"""

import sys
import os
import json
import requests
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

def check_process_definitions():
    """Проверка определений процессов"""
    print("📋 ОПРЕДЕЛЕНИЯ ПРОЦЕССОВ")
    print("-" * 50)
    
    url = f"{get_camunda_url()}/process-definition"
    params = {"key": "TestProcess"}
    
    response = make_request("GET", url, params=params)
    if not response or response.status_code != 200:
        print("❌ Не удалось получить определения процессов")
        return
    
    definitions = response.json()
    print(f"Найдено определений TestProcess: {len(definitions)}")
    
    for definition in definitions:
        print(f"  📄 Version {definition.get('version')}: {definition.get('id')}")
        print(f"     Deployed: {definition.get('deploymentTime')}")
        print(f"     Resource: {definition.get('resource')}")
        print()

def check_process_instances():
    """Проверка экземпляров процессов"""
    print("🔄 ЭКЗЕМПЛЯРЫ ПРОЦЕССОВ")
    print("-" * 50)
    
    url = f"{get_camunda_url()}/process-instance"
    params = {"processDefinitionKey": "TestProcess"}
    
    response = make_request("GET", url, params=params)
    if not response or response.status_code != 200:
        print("❌ Не удалось получить экземпляры процессов")
        return
    
    instances = response.json()
    print(f"Активных экземпляров TestProcess: {len(instances)}")
    
    for instance in instances:
        print(f"  🔄 Instance: {instance.get('id')}")
        print(f"     Business Key: {instance.get('businessKey')}")
        print(f"     Definition: {instance.get('definitionId')}")
        print(f"     Started: {instance.get('startTime')}")
        
        # Получаем активности
        activities_url = f"{get_camunda_url()}/process-instance/{instance.get('id')}/activity-instances"
        act_response = make_request("GET", activities_url)
        
        if act_response and act_response.status_code == 200:
            activities = act_response.json()
            print(f"     Активные активности:")
            
            def print_activities(activities_list, level=0):
                indent = "       " + "  " * level
                for activity in activities_list:
                    print(f"{indent}🔧 {activity.get('activityId')} ({activity.get('activityType')})")
                    if 'childActivityInstances' in activity:
                        print_activities(activity['childActivityInstances'], level + 1)
            
            if 'childActivityInstances' in activities:
                print_activities(activities['childActivityInstances'])
        print()

def check_external_tasks():
    """Проверка External Tasks"""
    print("🔧 EXTERNAL TASKS")
    print("-" * 50)
    
    url = f"{get_camunda_url()}/external-task"
    
    response = make_request("GET", url)
    if not response or response.status_code != 200:
        print("❌ Не удалось получить External Tasks")
        return
    
    tasks = response.json()
    print(f"Активных External Tasks: {len(tasks)}")
    
    for task in tasks:
        print(f"  🔧 Task: {task.get('id')}")
        print(f"     Topic: {task.get('topicName')}")
        print(f"     Activity: {task.get('activityId')}")
        print(f"     Process Instance: {task.get('processInstanceId')}")
        print(f"     Worker ID: {task.get('workerId')}")
        print(f"     Lock Expiration: {task.get('lockExpirationTime')}")
        
        variables = task.get('variables', {})
        if variables:
            print(f"     Variables: {list(variables.keys())}")
        print()

def start_new_process():
    """Запуск нового процесса TestProcess"""
    print("🚀 ЗАПУСК НОВОГО ПРОЦЕССА")
    print("-" * 50)
    
    # Получаем последнее определение
    defs_url = f"{get_camunda_url()}/process-definition"
    params = {"key": "TestProcess", "latestVersion": "true"}
    
    response = make_request("GET", defs_url, params=params)
    if not response or response.status_code != 200:
        print("❌ Не удалось получить определение процесса")
        return False
    
    definitions = response.json()
    if not definitions:
        print("❌ Процесс TestProcess не найден")
        return False
    
    latest_def = definitions[0]
    version = latest_def.get('version')
    def_id = latest_def.get('id')
    
    print(f"Запуск процесса TestProcess версии {version}")
    print(f"Definition ID: {def_id}")
    
    # Запускаем процесс
    start_url = f"{get_camunda_url()}/process-definition/{def_id}/start"
    payload = {
        "variables": {
            "Input_2khodeq": {"value": "TestValue_v5", "type": "String"},
            "user": {"value": "TestUser_v5", "type": "String"}
        },
        "businessKey": f"manual-test-v{version}"
    }
    
    response = make_request("POST", start_url, json=payload)
    
    if response and response.status_code == 200:
        result = response.json()
        print(f"✅ Процесс запущен!")
        print(f"   Instance ID: {result.get('id')}")
        print(f"   Business Key: {result.get('businessKey')}")
        return True
    else:
        print(f"❌ Ошибка запуска процесса")
        if response:
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
        return False

def main():
    print("🔍 ПРОВЕРКА СОСТОЯНИЯ CAMUNDA")
    print("=" * 60)
    
    check_process_definitions()
    check_process_instances()
    check_external_tasks()
    
    # Если нет активных экземпляров, предлагаем запустить новый
    url = f"{get_camunda_url()}/process-instance"
    params = {"processDefinitionKey": "TestProcess"}
    response = make_request("GET", url, params=params)
    
    if response and response.status_code == 200:
        instances = response.json()
        if len(instances) == 0:
            print("\n💡 Нет активных экземпляров TestProcess")
            choice = input("Запустить новый процесс? (y/N): ").strip().lower()
            if choice in ['y', 'yes']:
                start_new_process()
                print("\n🔄 Повторная проверка после запуска:")
                check_process_instances()
                check_external_tasks()

if __name__ == "__main__":
    main() 