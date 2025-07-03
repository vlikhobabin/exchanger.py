#!/usr/bin/env python3
"""
Сервисный скрипт для получения списка процессов в Camunda
Использует Camunda REST API для получения информации о:
- Определениях процессов (Process Definitions)
- Экземплярах процессов (Process Instances) 
- Внешних задачах (External Tasks)
- Активных задачах пользователей (User Tasks)
"""

import argparse
import json
import sys
import urllib3
from datetime import datetime
from typing import Dict, List, Optional
import requests
from requests.auth import HTTPBasicAuth

# Добавление родительского каталога в sys.path для импорта модулей проекта
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import camunda_config

# Отключение предупреждений SSL для самоподписанных сертификатов
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class CamundaProcessService:
    """Сервис для работы с процессами Camunda"""
    
    def __init__(self):
        self.base_url = camunda_config.base_url.rstrip('/')
        # Если base_url уже содержит /engine-rest, не добавляем его еще раз
        if self.base_url.endswith('/engine-rest'):
            self.engine_url = self.base_url
        else:
            self.engine_url = f"{self.base_url}/engine-rest"
        self.auth = None
        
        if camunda_config.auth_enabled:
            self.auth = HTTPBasicAuth(
                camunda_config.auth_username,
                camunda_config.auth_password
            )
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Выполнить HTTP запрос к Camunda REST API"""
        url = f"{self.engine_url}/{endpoint}"
        
        try:
            response = requests.get(
                url, 
                auth=self.auth,
                params=params or {},
                verify=False,  # Отключение проверки SSL
                timeout=30
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка при запросе к {url}: {e}")
            return None
    
    def get_process_definitions(self) -> List[Dict]:
        """Получить список определений процессов"""
        definitions = self._make_request("process-definition")
        return definitions or []
    
    def get_process_instances(self, active_only: bool = True) -> List[Dict]:
        """Получить список экземпляров процессов"""
        params = {}
        if active_only:
            params['active'] = 'true'
        
        instances = self._make_request("process-instance", params)
        return instances or []
    
    def get_external_tasks(self) -> List[Dict]:
        """Получить список внешних задач"""
        tasks = self._make_request("external-task")
        return tasks or []
    
    def get_user_tasks(self) -> List[Dict]:
        """Получить список пользовательских задач"""
        tasks = self._make_request("task")
        return tasks or []
    
    def get_engine_info(self) -> Dict:
        """Получить информацию о движке Camunda"""
        info = self._make_request("version")
        return info or {}
    
    def get_activity_statistics(self, process_def_id: str) -> List[Dict]:
        """Получить статистику активности для процесса"""
        endpoint = f"process-definition/{process_def_id}/statistics"
        stats = self._make_request(endpoint)
        return stats or []


def format_datetime(dt_string: str) -> str:
    """Форматировать дату-время для отображения"""
    if not dt_string:
        return "N/A"
    
    try:
        dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return dt_string


def print_process_definitions(definitions: List[Dict]):
    """Вывести определения процессов"""
    print("\n" + "="*80)
    print(f"📋 ОПРЕДЕЛЕНИЯ ПРОЦЕССОВ ({len(definitions)})")
    print("="*80)
    
    if not definitions:
        print("Нет определений процессов")
        return
    
    for i, definition in enumerate(definitions, 1):
        print(f"\n{i}. {definition.get('name', 'Без имени')}")
        print(f"   ID: {definition.get('id')}")
        print(f"   Key: {definition.get('key')}")
        print(f"   Version: {definition.get('version')}")
        print(f"   Category: {definition.get('category', 'N/A')}")
        print(f"   Suspended: {'Да' if definition.get('suspended') else 'Нет'}")
        print(f"   Deployment ID: {definition.get('deploymentId')}")


def print_process_instances(instances: List[Dict]):
    """Вывести экземпляры процессов"""
    print("\n" + "="*80)
    print(f"🏃 АКТИВНЫЕ ЭКЗЕМПЛЯРЫ ПРОЦЕССОВ ({len(instances)})")
    print("="*80)
    
    if not instances:
        print("Нет активных экземпляров процессов")
        return
    
    for i, instance in enumerate(instances, 1):
        print(f"\n{i}. Instance ID: {instance.get('id')}")
        print(f"   Process Definition ID: {instance.get('definitionId')}")
        print(f"   Process Definition Key: {instance.get('processDefinitionKey')}")
        print(f"   Business Key: {instance.get('businessKey', 'N/A')}")
        print(f"   Case Instance ID: {instance.get('caseInstanceId', 'N/A')}")
        print(f"   Suspended: {'Да' if instance.get('suspended') else 'Нет'}")
        print(f"   Tenant ID: {instance.get('tenantId', 'N/A')}")


def print_external_tasks(tasks: List[Dict]):
    """Вывести внешние задачи"""
    print("\n" + "="*80)
    print(f"⚡ ВНЕШНИЕ ЗАДАЧИ ({len(tasks)})")
    print("="*80)
    
    if not tasks:
        print("Нет внешних задач")
        return
    
    for i, task in enumerate(tasks, 1):
        print(f"\n{i}. Task ID: {task.get('id')}")
        print(f"   Topic Name: {task.get('topicName')}")
        print(f"   Worker ID: {task.get('workerId', 'N/A')}")
        print(f"   Process Instance ID: {task.get('processInstanceId')}")
        print(f"   Process Definition ID: {task.get('processDefinitionId')}")
        print(f"   Process Definition Key: {task.get('processDefinitionKey')}")
        print(f"   Activity ID: {task.get('activityId')}")
        print(f"   Activity Instance ID: {task.get('activityInstanceId')}")
        print(f"   Execution ID: {task.get('executionId')}")
        print(f"   Retries: {task.get('retries')}")
        print(f"   Suspended: {'Да' if task.get('suspended') else 'Нет'}")
        print(f"   Priority: {task.get('priority')}")
        print(f"   Business Key: {task.get('businessKey', 'N/A')}")
        print(f"   Tenant ID: {task.get('tenantId', 'N/A')}")
        
        # Время блокировки
        lock_time = task.get('lockExpirationTime')
        if lock_time:
            print(f"   Lock Expiration: {format_datetime(lock_time)}")


def print_user_tasks(tasks: List[Dict]):
    """Вывести пользовательские задачи"""
    print("\n" + "="*80)
    print(f"👤 ПОЛЬЗОВАТЕЛЬСКИЕ ЗАДАЧИ ({len(tasks)})")
    print("="*80)
    
    if not tasks:
        print("Нет пользовательских задач")
        return
    
    for i, task in enumerate(tasks, 1):
        print(f"\n{i}. Task ID: {task.get('id')}")
        print(f"   Name: {task.get('name', 'Без имени')}")
        print(f"   Description: {task.get('description', 'N/A')}")
        print(f"   Assignee: {task.get('assignee', 'Не назначен')}")
        print(f"   Owner: {task.get('owner', 'N/A')}")
        print(f"   Process Instance ID: {task.get('processInstanceId')}")
        print(f"   Process Definition Key: {task.get('processDefinitionKey')}")
        print(f"   Task Definition Key: {task.get('taskDefinitionKey')}")
        print(f"   Execution ID: {task.get('executionId')}")
        print(f"   Created: {format_datetime(task.get('created'))}")
        print(f"   Due Date: {format_datetime(task.get('due'))}")
        print(f"   Priority: {task.get('priority')}")
        print(f"   Suspended: {'Да' if task.get('suspended') else 'Нет'}")


def print_engine_info(info: Dict):
    """Вывести информацию о движке"""
    print("\n" + "="*80)
    print("🏗️  ИНФОРМАЦИЯ О ДВИЖКЕ CAMUNDA")
    print("="*80)
    
    if not info:
        print("Не удалось получить информацию о движке")
        return
    
    print(f"Version: {info.get('version', 'N/A')}")
    print(f"Date: {info.get('date', 'N/A')}")
    
    
def print_statistics(service: CamundaProcessService):
    """Вывести общую статистику"""
    print("\n" + "="*80)
    print("📊 ОБЩАЯ СТАТИСТИКА")
    print("="*80)
    
    definitions = service.get_process_definitions()
    instances = service.get_process_instances()
    external_tasks = service.get_external_tasks()
    user_tasks = service.get_user_tasks()
    
    print(f"Определений процессов: {len(definitions)}")
    print(f"Активных экземпляров: {len(instances)}")
    print(f"Внешних задач: {len(external_tasks)}")
    print(f"Пользовательских задач: {len(user_tasks)}")
    
    # Статистика по топикам внешних задач
    if external_tasks:
        topics = {}
        for task in external_tasks:
            topic = task.get('topicName', 'unknown')
            topics[topic] = topics.get(topic, 0) + 1
        
        print(f"\nВнешние задачи по топикам:")
        for topic, count in sorted(topics.items()):
            print(f"  {topic}: {count}")
    
    # Статистика по процессам
    if instances:
        processes = {}
        for instance in instances:
            key = instance.get('processDefinitionKey', 'unknown')
            processes[key] = processes.get(key, 0) + 1
        
        print(f"\nАктивные экземпляры по процессам:")
        for process_key, count in sorted(processes.items()):
            print(f"  {process_key}: {count}")


def export_to_json(service: CamundaProcessService, filename: str):
    """Экспортировать все данные в JSON файл"""
    data = {
        "timestamp": datetime.now().isoformat(),
        "engine_info": service.get_engine_info(),
        "process_definitions": service.get_process_definitions(),
        "process_instances": service.get_process_instances(),
        "external_tasks": service.get_external_tasks(),
        "user_tasks": service.get_user_tasks()
    }
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Данные экспортированы в файл: {filename}")
    except Exception as e:
        print(f"\n❌ Ошибка при экспорте в файл {filename}: {e}")


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description="Сервисный скрипт для получения списка процессов в Camunda",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python camunda_processes.py                    # Показать всю информацию
  python camunda_processes.py --definitions     # Только определения процессов
  python camunda_processes.py --instances       # Только экземпляры процессов
  python camunda_processes.py --external-tasks  # Только внешние задачи
  python camunda_processes.py --user-tasks      # Только пользовательские задачи
  python camunda_processes.py --stats           # Только статистика
  python camunda_processes.py --export data.json # Экспорт в JSON
        """
    )
    
    parser.add_argument('--definitions', action='store_true',
                       help='Показать определения процессов')
    parser.add_argument('--instances', action='store_true',
                       help='Показать экземпляры процессов')
    parser.add_argument('--external-tasks', action='store_true',
                       help='Показать внешние задачи')
    parser.add_argument('--user-tasks', action='store_true',
                       help='Показать пользовательские задачи')
    parser.add_argument('--stats', action='store_true',
                       help='Показать общую статистику')
    parser.add_argument('--export', metavar='FILE',
                       help='Экспортировать данные в JSON файл')
    parser.add_argument('--all-instances', action='store_true',
                       help='Показать все экземпляры (включая завершенные)')
    
    args = parser.parse_args()
    
    # Если не указаны конкретные разделы, показать все
    show_all = not any([args.definitions, args.instances, args.external_tasks, 
                       args.user_tasks, args.stats, args.export])
    
    try:
        service = CamundaProcessService()
        
        print(f"🔗 Подключение к Camunda: {service.base_url}")
        print(f"🔐 Аутентификация: {'Включена' if service.auth else 'Отключена'}")
        
        # Проверка подключения
        engine_info = service.get_engine_info()
        if not engine_info:
            print("❌ Не удалось подключиться к Camunda")
            sys.exit(1)
        
        # Показать информацию о движке
        if show_all or args.stats:
            print_engine_info(engine_info)
        
        # Экспорт в JSON
        if args.export:
            export_to_json(service, args.export)
            if not show_all:
                return
        
        # Показать определения процессов
        if show_all or args.definitions:
            definitions = service.get_process_definitions()
            print_process_definitions(definitions)
        
        # Показать экземпляры процессов
        if show_all or args.instances:
            instances = service.get_process_instances(active_only=not args.all_instances)
            print_process_instances(instances)
        
        # Показать внешние задачи
        if show_all or args.external_tasks:
            external_tasks = service.get_external_tasks()
            print_external_tasks(external_tasks)
        
        # Показать пользовательские задачи
        if show_all or args.user_tasks:
            user_tasks = service.get_user_tasks()
            print_user_tasks(user_tasks)
        
        # Показать статистику
        if show_all or args.stats:
            print_statistics(service)
        
        print(f"\n✅ Операция завершена успешно")
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Операция прервана пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 