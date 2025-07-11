#!/usr/bin/env python3
"""
Тестовый скрипт для сброса и перезапуска процесса Process_1d4oa6g46
Выполняет полную очистку окружения и запуск нового экземпляра процесса

Этапы выполнения:
1. Очистка всех очередей RabbitMQ
2. Удаление всех экземпляров процесса Process_1d4oa6g46
3. Запуск нового экземпляра с конфигурацией из process_config_RnS.yaml

Использует существующие сервисные модули проекта.
"""

import os
import sys
import time
from pathlib import Path

# Добавляем пути к модулям
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir / "universal-worker.py" / "tools"))
sys.path.insert(0, str(script_dir / "universal-worker.py"))

try:
    # Импорты из сервисных модулей
    from queue_reader import QueueReader
    from process_manager import CamundaProcessManager  
    from start_process import CamundaProcessStarter, load_config_from_yaml
    from rabbitmq_client import RabbitMQClient
except ImportError as e:
    print(f"❌ Ошибка импорта модулей: {e}")
    print("Убедитесь, что скрипт запускается из корневой директории проекта")
    sys.exit(1)


class ProcessResetTester:
    """Класс для тестирования сброса и перезапуска процесса"""
    
    def __init__(self, process_key: str = "Process_1d4oa6g46"):
        self.process_key = process_key
        self.config_file = "universal-worker.py/tools/process_config_RnS.yaml"
        
        # Инициализация сервисных компонентов
        self.queue_reader = QueueReader()
        self.process_manager = CamundaProcessManager()
        self.process_starter = CamundaProcessStarter()
        self.rabbitmq_client = RabbitMQClient()
    
    def print_header(self, title: str):
        """Вывод заголовка этапа"""
        print("\n" + "="*80)
        print(f"🔄 {title}")
        print("="*80)
    
    def step1_clear_rabbitmq_queues(self) -> bool:
        """Этап 1: Очистка всех очередей RabbitMQ"""
        self.print_header("ЭТАП 1: ОЧИСТКА ОЧЕРЕДЕЙ RABBITMQ")
        
        try:
            # Подключаемся к RabbitMQ через существующий клиент
            if not self.rabbitmq_client.connect():
                print("❌ Не удалось подключиться к RabbitMQ")
                return False
            
            # Получаем список всех очередей
            queues_info = self.rabbitmq_client.get_all_queues_info()
            
            if not queues_info:
                print("❌ Не удалось получить список очередей")
                return False
            
            print(f"📊 Найдено очередей: {len(queues_info)}")
            
            # Фильтруем очереди с сообщениями
            queues_to_clear = []
            for queue_name, info in queues_info.items():
                msg_count = info.get("message_count", 0)
                if msg_count > 0:
                    queues_to_clear.append((queue_name, msg_count))
                    print(f"   📬 {queue_name}: {msg_count:,} сообщений")
                else:
                    print(f"   📭 {queue_name}: пустая")
            
            if not queues_to_clear:
                print("✅ Все очереди уже пустые")
                return True
            
            print(f"\n🗑️ Очистка {len(queues_to_clear)} очередей с сообщениями...")
            
            # Очищаем очереди через QueueReader с принудительной очисткой
            cleared_count = 0
            for queue_name, msg_count in queues_to_clear:
                print(f"   🔄 Очистка {queue_name} ({msg_count:,} сообщений)...")
                
                if self.queue_reader.clear_queue(queue_name, force=True):
                    cleared_count += 1
                    print(f"   ✅ {queue_name} очищена")
                else:
                    print(f"   ❌ Не удалось очистить {queue_name}")
            
            print(f"\n📊 Результат очистки очередей:")
            print(f"   Очищено: {cleared_count} из {len(queues_to_clear)}")
            
            self.rabbitmq_client.disconnect()
            return cleared_count == len(queues_to_clear)
            
        except Exception as e:
            print(f"❌ Ошибка при очистке очередей: {e}")
            return False
    
    def step2_delete_process_instances(self) -> bool:
        """Этап 2: Удаление всех экземпляров процесса"""
        self.print_header(f"ЭТАП 2: УДАЛЕНИЕ ЭКЗЕМПЛЯРОВ ПРОЦЕССА {self.process_key}")
        
        try:
            # Проверяем существование процесса
            definition = self.process_manager.get_process_definition_by_key(self.process_key)
            if not definition:
                print(f"⚠️ Процесс с ключом '{self.process_key}' не найден")
                return True  # Считаем успехом, так как цель достигнута
            
            print(f"📋 Процесс найден: {definition.get('name', 'Без названия')} (версия {definition.get('version')})")
            
            # Получаем активные экземпляры
            instances = self.process_manager.get_process_instances_by_key(self.process_key)
            external_tasks = self.process_manager.get_external_tasks_by_process_key(self.process_key)
            
            print(f"🚀 Активных экземпляров: {len(instances)}")
            print(f"🔧 External Tasks: {len(external_tasks)}")
            
            if not instances and not external_tasks:
                print("✅ Нет активных экземпляров или задач для удаления")
                return True
            
            # Сначала очищаем "осиротевшие" External Tasks (не привязанные к активным процессам)
            orphaned_tasks = []
            active_instance_ids = {instance.get('id') for instance in instances}
            
            for task in external_tasks:
                task_process_id = task.get('processInstanceId')
                if task_process_id not in active_instance_ids:
                    orphaned_tasks.append(task)
            
            cleaned_orphaned = 0
            if orphaned_tasks:
                print(f"\n🧹 Очистка {len(orphaned_tasks)} осиротевших External Tasks...")
                for task in orphaned_tasks:
                    task_id = task.get('id')
                    if self.process_manager.delete_external_task(task_id):
                        cleaned_orphaned += 1
                        print(f"   ✅ Очищена осиротевшая задача: {task_id}")
                    else:
                        print(f"   ❌ Не удалось очистить задачу: {task_id}")
            
            # Удаляем все экземпляры (External Tasks удалятся автоматически)
            stopped_count = 0
            if instances:
                print(f"\n🗑️ Удаление {len(instances)} экземпляров...")
                for instance in instances:
                    instance_id = instance.get('id')
                    if self.process_manager.delete_process_instance(
                        instance_id, 
                        f"Тестовая очистка - {time.strftime('%Y-%m-%d %H:%M:%S')}"
                    ):
                        stopped_count += 1
                        print(f"   ✅ Удален экземпляр: {instance_id}")
                    else:
                        print(f"   ❌ Не удалось удалить экземпляр: {instance_id}")
            
            # Подсчитываем связанные External Tasks, которые удалятся автоматически
            linked_tasks_count = len(external_tasks) - len(orphaned_tasks)
            
            print(f"\n📊 Результат удаления:")
            print(f"   Удалено экземпляров: {stopped_count} из {len(instances)}")
            print(f"   Очищено осиротевших External Tasks: {cleaned_orphaned} из {len(orphaned_tasks)}")
            print(f"   Автоматически удалено External Tasks: {linked_tasks_count} (вместе с экземплярами)")
            
            return stopped_count == len(instances) and cleaned_orphaned == len(orphaned_tasks)
            
        except Exception as e:
            print(f"❌ Ошибка при удалении экземпляров процесса: {e}")
            return False
    
    def step3_start_new_process(self) -> bool:
        """Этап 3: Запуск нового экземпляра процесса"""
        self.print_header(f"ЭТАП 3: ЗАПУСК НОВОГО ЭКЗЕМПЛЯРА ПРОЦЕССА {self.process_key}")
        
        try:
            # Проверяем существование конфигурационного файла
            if not os.path.exists(self.config_file):
                print(f"❌ Конфигурационный файл не найден: {self.config_file}")
                return False
            
            # Загружаем конфигурацию из YAML
            print(f"📄 Загрузка конфигурации из {self.config_file}...")
            config = load_config_from_yaml(self.config_file)
            
            # Проверяем, что ключ процесса совпадает
            config_process_key = config.get('process_key')
            if config_process_key != self.process_key:
                print(f"⚠️ В конфигурации указан другой процесс: '{config_process_key}', ожидался '{self.process_key}'")
                print("Используем процесс из конфигурации...")
                self.process_key = config_process_key
            
            print(f"📋 Процесс: {self.process_key}")
            
            # Показываем конфигурацию
            variables = config.get('variables', {})
            business_key = config.get('business_key')
            version = config.get('version')
            
            if variables:
                print(f"📝 Переменные ({len(variables)}):")
                for key, value in variables.items():
                    print(f"   {key}: {value}")
            
            if business_key:
                print(f"🔑 Business Key: {business_key}")
            
            if version:
                print(f"🔢 Версия: {version}")
            
            # Проверяем существование процесса
            if version:
                endpoint = f"process-definition/key/{self.process_key}/version/{version}"
                definition = self.process_starter._make_request("GET", endpoint)
            else:
                definition = self.process_starter.get_process_definition_by_key(self.process_key)
            
            if not definition:
                print(f"❌ Процесс с ключом '{self.process_key}' не найден")
                return False
            
            print(f"📋 Процесс найден: {definition.get('name', 'Без названия')} (версия {definition.get('version')})")
            
            # Проверяем статус процесса
            if definition.get('suspended'):
                print(f"⚠️ Процесс приостановлен! Запуск может не сработать")
                return False
            
            # Запускаем процесс
            print(f"\n🚀 Запуск нового экземпляра процесса...")
            instance = self.process_starter.start_process_by_key(
                self.process_key,
                variables=variables,
                business_key=business_key,
                version=version
            )
            
            if not instance:
                print("❌ Не удалось запустить процесс")
                return False
            
            # Показываем результат
            instance_id = instance.get('id')
            print(f"✅ Процесс запущен успешно!")
            print(f"   ID экземпляра: {instance_id}")
            print(f"   Business Key: {instance.get('businessKey', 'N/A')}")
            print(f"   Process Definition ID: {instance.get('definitionId')}")
            
            # Дополнительная информация
            print(f"\n🔗 Ссылки:")
            base_url = self.process_starter.base_url
            print(f"   Cockpit: {base_url}/camunda/app/cockpit/default/#/process-instance/{instance_id}")
            print(f"   Tasklist: {base_url}/camunda/app/tasklist/default/")
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка при запуске процесса: {e}")
            return False
    
    def run_full_reset(self) -> bool:
        """Выполнить полный сброс и перезапуск"""
        print("🔄 ТЕСТОВЫЙ СБРОС И ПЕРЕЗАПУСК ПРОЦЕССА")
        print(f"Процесс: {self.process_key}")
        print(f"Конфигурация: {self.config_file}")
        print("=" * 80)
        
        success_steps = 0
        total_steps = 3
        
        # Этап 1: Очистка очередей
        if self.step1_clear_rabbitmq_queues():
            success_steps += 1
        else:
            print("❌ Этап 1 завершился с ошибками")
        
        # Небольшая пауза между этапами
        time.sleep(2)
        
        # Этап 2: Удаление экземпляров
        if self.step2_delete_process_instances():
            success_steps += 1
        else:
            print("❌ Этап 2 завершился с ошибками")
        
        # Небольшая пауза перед запуском
        time.sleep(2)
        
        # Этап 3: Запуск нового процесса
        if self.step3_start_new_process():
            success_steps += 1
        else:
            print("❌ Этап 3 завершился с ошибками")
        
        # Итоговый результат
        self.print_header("ИТОГОВЫЙ РЕЗУЛЬТАТ")
        
        if success_steps == total_steps:
            print("🎉 ВСЕ ЭТАПЫ ВЫПОЛНЕНЫ УСПЕШНО!")
            print("✅ Окружение полностью очищено и процесс перезапущен")
        else:
            print(f"⚠️ ВЫПОЛНЕНО {success_steps} из {total_steps} ЭТАПОВ")
            print("Проверьте логи выше для диагностики проблем")
        
        print(f"\n💡 Для мониторинга процесса используйте:")
        print(f"   python universal-worker.py/tools/camunda_processes.py --external-tasks")
        print(f"   python universal-worker.py/tools/check_queues.py")
        
        return success_steps == total_steps


def main():
    """Главная функция"""
    print("🧪 ТЕСТОВЫЙ СКРИПТ СБРОСА ПРОЦЕССА")
    print("=" * 50)
    
    try:
        # Проверяем рабочую директорию
        if not os.path.exists("universal-worker.py"):
            print("❌ Скрипт должен запускаться из корневой директории проекта")
            print("Перейдите в директорию с файлом exchanger.py")
            sys.exit(1)
        
        # Создаем и запускаем тестер
        tester = ProcessResetTester()
        
        # Показываем предупреждение
        print("⚠️ ВНИМАНИЕ!")
        print("Этот скрипт выполнит следующие действия:")
        print("1. Очистит ВСЕ очереди RabbitMQ")
        print("2. Удалит ВСЕ экземпляры процесса Process_1d4oa6g46")
        print("3. Запустит новый экземпляр процесса")
        print("\nЭто действие НЕОБРАТИМО!")
        
        # Запрашиваем подтверждение
        response = input("\nПродолжить? (введите 'YES' для подтверждения): ").strip()
        
        if response != 'YES':
            print("❌ Операция отменена")
            sys.exit(0)
        
        # Выполняем полный сброс
        success = tester.run_full_reset()
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print(f"\n⏹️ Операция прервана пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 