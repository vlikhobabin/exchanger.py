#!/usr/bin/env python3
"""
Сервисный скрипт для запуска экземпляров процессов в Camunda
Использует Camunda REST API для создания новых экземпляров процессов по ключу
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


class CamundaProcessStarter:
    """Сервис для запуска процессов в Camunda"""
    
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
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
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
    
    def get_process_instance(self, instance_id: str) -> Optional[Dict]:
        """Получить информацию об экземпляре процесса"""
        endpoint = f"process-instance/{instance_id}"
        return self._make_request("GET", endpoint)


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


def print_process_definition_info(definition: Dict):
    """Вывести информацию об определении процесса"""
    print("\n" + "="*80)
    print("📋 ИНФОРМАЦИЯ О ПРОЦЕССЕ")
    print("="*80)
    
    print(f"Название: {definition.get('name', 'Без названия')}")
    print(f"Ключ: {definition.get('key')}")
    print(f"ID: {definition.get('id')}")
    print(f"Версия: {definition.get('version')}")
    print(f"Категория: {definition.get('category', 'N/A')}")
    print(f"Описание: {definition.get('description', 'N/A')}")
    print(f"Deployment ID: {definition.get('deploymentId')}")
    print(f"Приостановлен: {'Да' if definition.get('suspended') else 'Нет'}")
    
    if definition.get('versionTag'):
        print(f"Тег версии: {definition.get('versionTag')}")


def print_process_instance_info(instance: Dict):
    """Вывести информацию о созданном экземпляре процесса"""
    print("\n" + "="*80)
    print("🚀 ЭКЗЕМПЛЯР ПРОЦЕССА СОЗДАН")
    print("="*80)
    
    print(f"ID экземпляра: {instance.get('id')}")
    print(f"Business Key: {instance.get('businessKey', 'N/A')}")
    print(f"Process Definition ID: {instance.get('definitionId')}")
    print(f"Case Instance ID: {instance.get('caseInstanceId', 'N/A')}")
    print(f"Завершен: {'Да' if instance.get('ended') else 'Нет'}")
    print(f"Приостановлен: {'Да' if instance.get('suspended') else 'Нет'}")
    print(f"Tenant ID: {instance.get('tenantId', 'N/A')}")
    
    # Ссылки для удобства
    base_url = camunda_config.base_url
    print(f"\n🔗 Ссылки:")
    print(f"Cockpit: {base_url}/camunda/app/cockpit/default/#/process-instance/{instance.get('id')}")
    print(f"Tasklist: {base_url}/camunda/app/tasklist/default/")


def list_process_versions(service: CamundaProcessStarter, process_key: str):
    """Показать все версии процесса"""
    print(f"\n🔍 Поиск версий процесса '{process_key}'...")
    
    definitions = service.get_process_definitions_by_key(process_key)
    
    if not definitions:
        print(f"❌ Процесс с ключом '{process_key}' не найден")
        return
    
    print(f"\n📋 Найдено версий: {len(definitions)}")
    print("="*80)
    
    for i, definition in enumerate(sorted(definitions, key=lambda x: x.get('version', 0), reverse=True), 1):
        print(f"\n{i}. Версия {definition.get('version')}")
        print(f"   ID: {definition.get('id')}")
        print(f"   Название: {definition.get('name', 'Без названия')}")
        print(f"   Deployment ID: {definition.get('deploymentId')}")
        print(f"   Приостановлен: {'Да' if definition.get('suspended') else 'Нет'}")
        
        if definition.get('versionTag'):
            print(f"   Тег версии: {definition.get('versionTag')}")


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description="Сервисный скрипт для запуска экземпляров процессов в Camunda",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  # Запуск процесса без переменных
  python start_process.py TestProcess

  # Запуск с business key
  python start_process.py TestProcess --business-key "ORDER-123"

  # Запуск с переменными (JSON формат)
  python start_process.py TestProcess --variables '{"userName": "John", "amount": 100, "approved": true}'

  # Запуск с переменными (key=value формат)
  python start_process.py TestProcess --variables "userName=John,amount=100,approved=true"

  # Запуск конкретной версии процесса
  python start_process.py TestProcess --version 2 --variables "userName=Jane"

  # Показать информацию о процессе без запуска
  python start_process.py TestProcess --info

  # Показать все версии процесса
  python start_process.py TestProcess --list-versions

Типы переменных:
  - Строки: "userName=John"
  - Числа: "amount=100" 
  - Булевы: "approved=true"
  - JSON: "data={\"key\": \"value\"}"
        """
    )
    
    parser.add_argument('process_key', 
                       help='Ключ процесса для запуска (например, TestProcess)')
    parser.add_argument('--variables', '-v',
                       help='Переменные для процесса в JSON формате или key=value пары')
    parser.add_argument('--business-key', '-b',
                       help='Business key для экземпляра процесса')
    parser.add_argument('--version',
                       help='Версия процесса для запуска (по умолчанию - последняя)')
    parser.add_argument('--info', action='store_true',
                       help='Показать информацию о процессе без запуска')
    parser.add_argument('--list-versions', action='store_true',
                       help='Показать все версии процесса')
    parser.add_argument('--dry-run', action='store_true',
                       help='Показать что будет отправлено без фактического запуска')
    
    args = parser.parse_args()
    
    try:
        service = CamundaProcessStarter()
        
        print(f"🔗 Подключение к Camunda: {service.base_url}")
        print(f"🔐 Аутентификация: {'Включена' if service.auth else 'Отключена'}")
        
        # Показать все версии процесса
        if args.list_versions:
            list_process_versions(service, args.process_key)
            return
        
        # Получить информацию о процессе
        if args.version:
            print(f"🔍 Поиск процесса '{args.process_key}' версии {args.version}...")
            endpoint = f"process-definition/key/{args.process_key}/version/{args.version}"
            definition = service._make_request("GET", endpoint)
        else:
            print(f"🔍 Поиск процесса '{args.process_key}'...")
            definition = service.get_process_definition_by_key(args.process_key)
        
        if not definition:
            print(f"❌ Процесс с ключом '{args.process_key}' не найден")
            # Предложить показать доступные процессы
            print("\n💡 Попробуйте команду для просмотра всех процессов:")
            print("python camunda_processes.py --definitions")
            sys.exit(1)
        
        # Показать информацию о процессе
        print_process_definition_info(definition)
        
        # Если запрошена только информация - выходим
        if args.info:
            return
        
        # Проверка на приостановленный процесс
        if definition.get('suspended'):
            print(f"\n⚠️  Внимание: Процесс приостановлен. Запуск может не сработать.")
            response = input("Продолжить? (y/N): ")
            if response.lower() != 'y':
                print("Операция отменена")
                return
        
        # Парсинг переменных
        variables = {}
        if args.variables:
            try:
                variables = parse_variables(args.variables)
                print(f"\n📝 Переменные для запуска:")
                for key, value in variables.items():
                    print(f"   {key}: {value} ({type(value).__name__})")
            except Exception as e:
                print(f"❌ Ошибка при парсинге переменных: {e}")
                print("Пример правильного формата: 'userName=John,amount=100' или '{\"userName\": \"John\"}'")
                sys.exit(1)
        
        # Business key
        if args.business_key:
            print(f"\n🔑 Business Key: {args.business_key}")
        
        # Dry run - показать что будет отправлено
        if args.dry_run:
            print(f"\n🧪 DRY RUN - Данные для отправки:")
            start_data = {}
            if variables:
                start_data["variables"] = variables
            if args.business_key:
                start_data["businessKey"] = args.business_key
            print(json.dumps(start_data, indent=2, ensure_ascii=False))
            return
        
        # Подтверждение запуска
        print(f"\n🚀 Готов к запуску процесса '{args.process_key}'")
        if not args.variables and not args.business_key:
            response = input("Запустить процесс? (Y/n): ")
            if response.lower() == 'n':
                print("Операция отменена")
                return
        
        # Запуск процесса
        print(f"\n⏳ Запуск процесса...")
        instance = service.start_process_by_key(
            args.process_key, 
            variables=variables,
            business_key=args.business_key,
            version=args.version
        )
        
        if not instance:
            print("❌ Не удалось запустить процесс")
            sys.exit(1)
        
        # Показать информацию о созданном экземпляре
        print_process_instance_info(instance)
        
        # Дополнительная информация об экземпляре
        instance_info = service.get_process_instance(instance.get('id'))
        if instance_info and instance_info.get('ended'):
            print(f"\n💡 Процесс уже завершился (синхронное выполнение)")
        else:
            print(f"\n💡 Процесс выполняется. Проверьте статус в Camunda Cockpit")
        
        print(f"\n✅ Операция завершена успешно")
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Операция прервана пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 