#!/usr/bin/env python3
"""
Многофункциональный скрипт управления процессами Camunda
Позволяет просматривать, запускать, останавливать и удалять процессы

КОМАНДЫ ДЛЯ РАБОТЫ:

# Показать список всех процессов
python process_manager.py list

# Показать больше процессов
python process_manager.py list --limit 20

# Подробная информация о процессе
python process_manager.py info TestProcess

# Запустить процесс с переменными (JSON формат)
python process_manager.py start TestProcess --variables '{"user": "John", "amount": 100}'

# Запустить процесс с переменными (key=value формат)
python process_manager.py start TestProcess --variables "user=John,amount=100" --business-key "ORDER-123"

# Запустить конкретную версию процесса
python process_manager.py start TestProcess --version 2 --variables "test=true"

# Остановить все экземпляры процесса
python process_manager.py stop TestProcess

# Удалить процесс полностью
python process_manager.py delete TestProcess

# Принудительные операции без подтверждения
python universal-worker.py/tools/process_manager.py stop Process_3f946f12_5071_4a9f_9960_0f57b4c05e45 --force
python process_manager.py delete TestProcess --force

# Показать справку по командам
python process_manager.py --help
python process_manager.py start --help
"""

import argparse
import json
import sys
import urllib3
from datetime import datetime
from typing import Dict, List, Optional, Any
import requests
from requests.auth import HTTPBasicAuth

# Добавление родительского каталога в sys.path для импорта модулей проекта
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import camunda_config

# Отключение предупреждений SSL для самоподписанных сертификатов
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class CamundaProcessManager:
    """Комплексный сервис для управления процессами в Camunda"""
    
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
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Optional[Dict]:
        """Выполнить HTTP запрос к Camunda REST API"""
        url = f"{self.engine_url}/{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(
                    url, 
                    auth=self.auth,
                    params=params or {},
                    verify=False,
                    timeout=30
                )
            elif method.upper() == 'POST':
                response = requests.post(
                    url,
                    auth=self.auth,
                    json=data or {},
                    params=params or {},
                    verify=False,
                    timeout=30
                )
            elif method.upper() == 'DELETE':
                response = requests.delete(
                    url,
                    auth=self.auth,
                    params=params or {},
                    verify=False,
                    timeout=30
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            
            # Некоторые DELETE запросы возвращают пустой ответ
            if response.status_code == 204 or not response.text.strip():
                return {"status": "success"}
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка при запросе к {url}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details = e.response.json()
                    print(f"   Детали ошибки: {error_details}")
                except:
                    print(f"   HTTP статус: {e.response.status_code}")
                    print(f"   Ответ сервера: {e.response.text[:200]}")
            return None

    # === МЕТОДЫ ДЛЯ РАБОТЫ С ОПРЕДЕЛЕНИЯМИ ПРОЦЕССОВ ===
    
    def list_processes(self, limit: int = 10) -> List[Dict]:
        """Получить список первых N процессов"""
        endpoint = "process-definition"
        params = {
            "sortBy": "name",
            "sortOrder": "asc",
            "firstResult": 0,
            "maxResults": limit
        }
        definitions = self._make_request("GET", endpoint, params=params)
        return definitions or []
    
    def get_process_definition_by_key(self, process_key: str) -> Optional[Dict]:
        """Получить определение процесса по ключу"""
        endpoint = f"process-definition/key/{process_key}"
        return self._make_request("GET", endpoint)
    
    def get_process_definitions_by_key(self, process_key: str) -> List[Dict]:
        """Получить все версии определения процесса по ключу"""
        endpoint = "process-definition"
        params = {"key": process_key}
        definitions = self._make_request("GET", endpoint, params=params)
        return definitions or []
    
    def delete_process_definition(self, definition_id: str, cascade: bool = True) -> bool:
        """Удалить определение процесса"""
        endpoint = f"process-definition/{definition_id}"
        params = {"cascade": "true" if cascade else "false"}
        result = self._make_request("DELETE", endpoint, params=params)
        return result is not None

    # === МЕТОДЫ ДЛЯ РАБОТЫ С ЭКЗЕМПЛЯРАМИ ПРОЦЕССОВ ===
    
    def get_process_instances_by_key(self, process_key: str) -> List[Dict]:
        """Получить все активные экземпляры процесса по ключу"""
        endpoint = "process-instance"
        params = {"processDefinitionKey": process_key}
        instances = self._make_request("GET", endpoint, params=params)
        return instances or []
    
    def start_process_by_key(self, process_key: str, variables: Dict[str, Any] = None, 
                           business_key: str = None, version: str = None) -> Optional[Dict]:
        """Запустить процесс по ключу"""
        
        # Определяем endpoint в зависимости от того, указана ли версия
        if version:
            endpoint = f"process-definition/key/{process_key}/version/{version}/start"
        else:
            endpoint = f"process-definition/key/{process_key}/start"
        
        # Подготовка данных для запуска
        start_data = {}
        
        if variables:
            # Конвертируем переменные в формат Camunda
            camunda_variables = {}
            for key, value in variables.items():
                if isinstance(value, bool):
                    camunda_variables[key] = {"value": value, "type": "Boolean"}
                elif isinstance(value, int):
                    camunda_variables[key] = {"value": value, "type": "Integer"}
                elif isinstance(value, float):
                    camunda_variables[key] = {"value": value, "type": "Double"}
                elif isinstance(value, str):
                    camunda_variables[key] = {"value": value, "type": "String"}
                elif isinstance(value, dict) or isinstance(value, list):
                    camunda_variables[key] = {"value": json.dumps(value), "type": "Json"}
                else:
                    camunda_variables[key] = {"value": str(value), "type": "String"}
            
            start_data["variables"] = camunda_variables
        
        if business_key:
            start_data["businessKey"] = business_key
        
        return self._make_request("POST", endpoint, start_data)
    
    def delete_process_instance(self, instance_id: str, reason: str = "Удалено через Process Manager") -> bool:
        """Удалить экземпляр процесса"""
        endpoint = f"process-instance/{instance_id}"
        params = {"reason": reason}
        result = self._make_request("DELETE", endpoint, params=params)
        return result is not None
    
    def stop_all_process_instances(self, process_key: str) -> int:
        """Остановить все экземпляры процесса и вернуть количество остановленных"""
        instances = self.get_process_instances_by_key(process_key)
        stopped_count = 0
        
        for instance in instances:
            instance_id = instance.get('id')
            if self.delete_process_instance(instance_id, f"Массовая остановка процесса {process_key}"):
                stopped_count += 1
                print(f"   ✅ Остановлен экземпляр: {instance_id}")
            else:
                print(f"   ❌ Не удалось остановить экземпляр: {instance_id}")
        
        return stopped_count

    # === МЕТОДЫ ДЛЯ РАБОТЫ С EXTERNAL TASKS ===
    
    def get_external_tasks_by_process_key(self, process_key: str) -> List[Dict]:
        """Получить все External Tasks для процесса"""
        endpoint = "external-task"
        params = {"processDefinitionKey": process_key}
        tasks = self._make_request("GET", endpoint, params=params)
        return tasks or []
    
    def delete_external_task(self, task_id: str) -> bool:
        """Удалить External Task (разблокировать)"""
        endpoint = f"external-task/{task_id}/unlock"
        result = self._make_request("POST", endpoint)
        return result is not None
    
    def cleanup_external_tasks(self, process_key: str) -> int:
        """Очистить все External Tasks для процесса"""
        tasks = self.get_external_tasks_by_process_key(process_key)
        cleaned_count = 0
        
        for task in tasks:
            task_id = task.get('id')
            if self.delete_external_task(task_id):
                cleaned_count += 1
                print(f"   ✅ Очищена задача: {task_id}")
            else:
                print(f"   ❌ Не удалось очистить задачу: {task_id}")
        
        return cleaned_count


def parse_variables(variables_str: str) -> Dict[str, Any]:
    """Парсинг переменных из строки"""
    if not variables_str:
        return {}
    
    try:
        # Попытка парсинга как JSON
        return json.loads(variables_str)
    except json.JSONDecodeError:
        # Парсинг как key=value пары, разделенные запятыми
        variables = {}
        pairs = variables_str.split(',')
        
        for pair in pairs:
            if '=' not in pair:
                continue
            
            key, value = pair.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            # Попытка определения типа значения
            if value.lower() in ('true', 'false'):
                variables[key] = value.lower() == 'true'
            elif value.isdigit():
                variables[key] = int(value)
            elif value.replace('.', '', 1).isdigit():
                variables[key] = float(value)
            elif value.startswith('{') or value.startswith('['):
                try:
                    variables[key] = json.loads(value)
                except:
                    variables[key] = value
            else:
                variables[key] = value
        
        return variables


def print_processes_list(processes: List[Dict]):
    """Вывести краткий список процессов"""
    if not processes:
        print("❌ Процессы не найдены")
        return
    
    print("\n" + "="*100)
    print("📋 СПИСОК ПРОЦЕССОВ")
    print("="*100)
    
    # Заголовок таблицы
    print(f"{'№':<3} {'Ключ':<25} {'Название':<35} {'Версия':<8} {'Статус':<12}")
    print("-" * 100)
    
    for i, process in enumerate(processes, 1):
        key = process.get('key', 'N/A')[:24]
        name = process.get('name', 'Без названия')[:34]
        version = str(process.get('version', 'N/A'))
        status = "Приостановлен" if process.get('suspended') else "Активен"
        
        print(f"{i:<3} {key:<25} {name:<35} {version:<8} {status:<12}")


def print_process_detailed_info(manager: CamundaProcessManager, process_key: str):
    """Вывести подробную информацию о процессе"""
    definitions = manager.get_process_definitions_by_key(process_key)
    
    if not definitions:
        print(f"❌ Процесс с ключом '{process_key}' не найден")
        return
    
    print("\n" + "="*80)
    print(f"📋 ПОДРОБНАЯ ИНФОРМАЦИЯ О ПРОЦЕССЕ: {process_key}")
    print("="*80)
    
    # Сортируем по версии (последняя версия первой)
    definitions.sort(key=lambda x: x.get('version', 0), reverse=True)
    latest = definitions[0]
    
    print(f"Название: {latest.get('name', 'Без названия')}")
    print(f"Ключ: {latest.get('key')}")
    print(f"Категория: {latest.get('category', 'N/A')}")
    print(f"Описание: {latest.get('description', 'N/A')}")
    print(f"Всего версий: {len(definitions)}")
    print(f"Последняя версия: {latest.get('version')}")
    print(f"Статус: {'Приостановлен' if latest.get('suspended') else 'Активен'}")
    
    # Информация о версиях
    print(f"\n📋 Все версии:")
    for definition in definitions:
        status = "🔴 Приостановлен" if definition.get('suspended') else "🟢 Активен"
        print(f"   Версия {definition.get('version')}: {definition.get('id')} ({status})")
    
    # Активные экземпляры
    instances = manager.get_process_instances_by_key(process_key)
    print(f"\n🚀 Активные экземпляры: {len(instances)}")
    
    if instances:
        for instance in instances[:5]:  # Показываем первые 5
            business_key = instance.get('businessKey', 'N/A')
            print(f"   {instance.get('id')} (Business Key: {business_key})")
        
        if len(instances) > 5:
            print(f"   ... и еще {len(instances) - 5} экземпляров")
    
    # External Tasks
    external_tasks = manager.get_external_tasks_by_process_key(process_key)
    print(f"\n🔧 External Tasks: {len(external_tasks)}")
    
    if external_tasks:
        for task in external_tasks[:3]:  # Показываем первые 3
            topic = task.get('topicName', 'N/A')
            worker_id = task.get('workerId', 'N/A')
            print(f"   {task.get('id')} (Topic: {topic}, Worker: {worker_id})")
        
        if len(external_tasks) > 3:
            print(f"   ... и еще {len(external_tasks) - 3} задач")


def confirm_dangerous_action(action: str, target: str) -> bool:
    """Запросить подтверждение для опасных операций"""
    print(f"\n⚠️  ВНИМАНИЕ: Вы собираетесь {action} '{target}'")
    print("Это действие необратимо!")
    
    confirmation = input(f"Для подтверждения введите название процесса '{target}': ")
    
    if confirmation != target:
        print("❌ Подтверждение не совпадает. Операция отменена.")
        return False
    
    final_confirm = input("Вы уверены? (введите 'ДА' для подтверждения): ")
    if final_confirm != 'ДА':
        print("❌ Операция отменена.")
        return False
    
    return True


def cmd_list(manager: CamundaProcessManager, args):
    """Команда: показать список процессов"""
    print(f"🔗 Подключение к Camunda: {manager.base_url}")
    
    processes = manager.list_processes(args.limit)
    print_processes_list(processes)
    
    if processes:
        print(f"\n💡 Для подробной информации используйте: python process_manager.py info <process_key>")


def cmd_info(manager: CamundaProcessManager, args):
    """Команда: показать подробную информацию о процессе"""
    print(f"🔗 Подключение к Camunda: {manager.base_url}")
    print_process_detailed_info(manager, args.process_key)


def cmd_start(manager: CamundaProcessManager, args):
    """Команда: запустить процесс"""
    print(f"🔗 Подключение к Camunda: {manager.base_url}")
    
    # Проверяем существование процесса
    definition = manager.get_process_definition_by_key(args.process_key)
    if not definition:
        print(f"❌ Процесс с ключом '{args.process_key}' не найден")
        return
    
    print(f"📋 Процесс найден: {definition.get('name', 'Без названия')} (версия {definition.get('version')})")
    
    # Парсинг переменных
    variables = {}
    if args.variables:
        try:
            variables = parse_variables(args.variables)
            print(f"📝 Переменные:")
            for key, value in variables.items():
                print(f"   {key}: {value} ({type(value).__name__})")
        except Exception as e:
            print(f"❌ Ошибка при парсинге переменных: {e}")
            return
    
    if args.business_key:
        print(f"🔑 Business Key: {args.business_key}")
    
    # Запуск
    print(f"\n⏳ Запуск процесса '{args.process_key}'...")
    instance = manager.start_process_by_key(
        args.process_key,
        variables=variables,
        business_key=args.business_key,
        version=args.version
    )
    
    if instance:
        print(f"✅ Процесс запущен успешно!")
        print(f"   ID экземпляра: {instance.get('id')}")
        print(f"   Business Key: {instance.get('businessKey', 'N/A')}")
    else:
        print("❌ Не удалось запустить процесс")


def cmd_stop(manager: CamundaProcessManager, args):
    """Команда: остановить все экземпляры процесса"""
    print(f"🔗 Подключение к Camunda: {manager.base_url}")
    
    # Проверяем существование процесса
    definition = manager.get_process_definition_by_key(args.process_key)
    if not definition:
        print(f"❌ Процесс с ключом '{args.process_key}' не найден")
        return
    
    # Получаем информацию о процессе
    instances = manager.get_process_instances_by_key(args.process_key)
    external_tasks = manager.get_external_tasks_by_process_key(args.process_key)
    
    print(f"📋 Процесс: {definition.get('name', 'Без названия')}")
    print(f"🚀 Активных экземпляров: {len(instances)}")
    print(f"🔧 External Tasks: {len(external_tasks)}")
    
    if not instances and not external_tasks:
        print("💡 Нет активных экземпляров или задач для остановки")
        return
    
    # Подтверждение
    if not args.force:
        if not confirm_dangerous_action("остановить все экземпляры процесса", args.process_key):
            return
    
    # Остановка экземпляров
    stopped_count = 0
    if instances:
        print(f"\n⏳ Остановка {len(instances)} экземпляров...")
        stopped_count = manager.stop_all_process_instances(args.process_key)
    
    # Очистка External Tasks
    cleaned_count = 0
    if external_tasks:
        print(f"\n⏳ Очистка {len(external_tasks)} External Tasks...")
        cleaned_count = manager.cleanup_external_tasks(args.process_key)
    
    print(f"\n✅ Операция завершена:")
    print(f"   Остановлено экземпляров: {stopped_count}")
    print(f"   Очищено External Tasks: {cleaned_count}")


def cmd_delete(manager: CamundaProcessManager, args):
    """Команда: удалить процесс"""
    print(f"🔗 Подключение к Camunda: {manager.base_url}")
    
    # Получаем все версии процесса
    definitions = manager.get_process_definitions_by_key(args.process_key)
    if not definitions:
        print(f"❌ Процесс с ключом '{args.process_key}' не найден")
        return
    
    print(f"📋 Найдено версий процесса: {len(definitions)}")
    for definition in definitions:
        print(f"   Версия {definition.get('version')}: {definition.get('id')}")
    
    # Проверяем активные экземпляры
    instances = manager.get_process_instances_by_key(args.process_key)
    if instances and not args.force:
        print(f"\n⚠️  Найдено {len(instances)} активных экземпляров!")
        print("Сначала остановите их командой: python process_manager.py stop <process_key>")
        print("Или используйте флаг --force для принудительного удаления")
        return
    
    # Подтверждение
    if not args.force:
        if not confirm_dangerous_action("удалить процесс", args.process_key):
            return
    
    # Удаление всех версий
    print(f"\n⏳ Удаление {len(definitions)} версий процесса...")
    deleted_count = 0
    
    for definition in definitions:
        definition_id = definition.get('id')
        version = definition.get('version')
        
        if manager.delete_process_definition(definition_id, cascade=True):
            deleted_count += 1
            print(f"   ✅ Удалена версия {version}: {definition_id}")
        else:
            print(f"   ❌ Не удалось удалить версию {version}: {definition_id}")
    
    print(f"\n✅ Операция завершена: удалено {deleted_count} из {len(definitions)} версий")


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description="Многофункциональный скрипт управления процессами Camunda",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Команды:

  list                    Показать список процессов
  info <process_key>      Подробная информация о процессе  
  start <process_key>     Запустить экземпляр процесса
  stop <process_key>      Остановить все экземпляры процесса
  delete <process_key>    Удалить процесс полностью

Примеры:

  # Показать первые 10 процессов
  python process_manager.py list

  # Показать первые 20 процессов  
  python process_manager.py list --limit 20

  # Подробная информация о процессе
  python process_manager.py info TestProcess

  # Запустить процесс с переменными
  python process_manager.py start TestProcess --variables '{"user": "John", "amount": 100}'
  python process_manager.py start TestProcess --variables "user=John,amount=100" --business-key "ORDER-123"

  # Остановить все экземпляры процесса
  python process_manager.py stop TestProcess

  # Принудительная остановка без подтверждения
  python process_manager.py stop TestProcess --force

  # Удалить процесс
  python process_manager.py delete TestProcess

  # Принудительное удаление
  python process_manager.py delete TestProcess --force
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Доступные команды')
    
    # Команда list
    list_parser = subparsers.add_parser('list', help='Показать список процессов')
    list_parser.add_argument('--limit', type=int, default=10, 
                           help='Количество процессов для показа (по умолчанию: 10)')
    
    # Команда info  
    info_parser = subparsers.add_parser('info', help='Подробная информация о процессе')
    info_parser.add_argument('process_key', help='Ключ процесса')
    
    # Команда start
    start_parser = subparsers.add_parser('start', help='Запустить экземпляр процесса')
    start_parser.add_argument('process_key', help='Ключ процесса')
    start_parser.add_argument('--variables', '-v', help='Переменные (JSON или key=value)')
    start_parser.add_argument('--business-key', '-b', help='Business key для экземпляра')
    start_parser.add_argument('--version', help='Версия процесса')
    
    # Команда stop
    stop_parser = subparsers.add_parser('stop', help='Остановить все экземпляры процесса')
    stop_parser.add_argument('process_key', help='Ключ процесса')
    stop_parser.add_argument('--force', action='store_true', 
                           help='Принудительная остановка без подтверждения')
    
    # Команда delete
    delete_parser = subparsers.add_parser('delete', help='Удалить процесс полностью')
    delete_parser.add_argument('process_key', help='Ключ процесса')
    delete_parser.add_argument('--force', action='store_true',
                             help='Принудительное удаление без подтверждения')
    
    args = parser.parse_args()
    
    try:
        manager = CamundaProcessManager()
        
        # Если команда не указана, показываем список процессов по умолчанию
        if not args.command:
            # Создаем объект args для команды list с лимитом по умолчанию
            class DefaultArgs:
                def __init__(self):
                    self.limit = 10
            
            default_args = DefaultArgs()
            cmd_list(manager, default_args)
        elif args.command == 'list':
            cmd_list(manager, args)
        elif args.command == 'info':
            cmd_info(manager, args)
        elif args.command == 'start':
            cmd_start(manager, args)
        elif args.command == 'stop':
            cmd_stop(manager, args)
        elif args.command == 'delete':
            cmd_delete(manager, args)
        else:
            print(f"❌ Неизвестная команда: {args.command}")
            parser.print_help()
            
    except KeyboardInterrupt:
        print(f"\n⏹️  Операция прервана пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 