#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для деплоя BPMN схем в Camunda
Использование: python deploy.py <input_file.bpmn>
"""

import sys
import os
from pathlib import Path

# Добавляем родительскую директорию в путь для импорта
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from camunda_client import CamundaClient, CamundaAuthError, CamundaValidationError, CamundaDeployError, CamundaAPIError


def main():
    """Основная функция скрипта"""
    print("🚀 BPMN Deploy - отправка схем в Camunda")
    print("=" * 50)
    
    if len(sys.argv) != 2:
        print("❌ Неверное количество аргументов!")
        print("\n📖 Использование:")
        print("   python deploy.py <input_file.bpmn>")
        print("\n💡 Примеры:")
        print("   python deploy.py ../my_process.bpmn")
        print("   python deploy.py camunda_converted_process.bpmn")
        print("\n📝 Описание:")
        print("   Скрипт отправляет BPMN схему в Camunda через REST API.")
        print("   Создается новый деплой с определениями процессов.")
        print("\n🔧 Настройка:")
        print("   Убедитесь, что в .env настроены параметры:")
        print("   - CAMUNDA_BASE_URL")
        print("   - CAMUNDA_AUTH_USERNAME")
        print("   - CAMUNDA_AUTH_PASSWORD")
        return 1
        
    input_file = sys.argv[1]
    
    # Проверяем существование файла
    if not os.path.exists(input_file):
        print(f"❌ Файл не найден: {input_file}")
        return 1
        
    # Проверяем расширение файла
    if not input_file.lower().endswith('.bpmn'):
        print(f"⚠️ Предупреждение: файл не имеет расширения .bpmn")
        print(f"   Продолжаем обработку...")
    
    try:
        # Создаем клиента Camunda
        print("🔗 Инициализация Camunda Client...")
        client = CamundaClient()
        
        # Тестируем соединение
        print("🔍 Проверка соединения с Camunda...")
        if not client.test_connection():
            print("❌ Не удалось подключиться к Camunda!")
            print("   Проверьте:")
            print("   - Доступность Camunda сервера")
            print("   - Правильность URL (CAMUNDA_BASE_URL)")
            print("   - Учетные данные (CAMUNDA_AUTH_USERNAME/PASSWORD)")
            return 1
        
        print("✅ Соединение с Camunda установлено")
        
        # Выполняем деплой
        print(f"\n🚀 Начинаем деплой схемы...")
        result = client.deploy_diagram(input_file)
        
        # Отображаем результат
        print(f"\n🎉 Деплой завершен успешно!")
        print(f"" + "=" * 60)
        print(f"📁 Исходный файл: {input_file}")
        print(f"🆔 ID деплоя: {result.get('id')}")
        print(f"📅 Дата деплоя: {result.get('deploymentTime')}")
        print(f"🏷️ Название деплоя: {result.get('name')}")
        print(f"📦 Источник: {result.get('source', 'camunda-sync')}")
        
        # Информация о развернутых процессах
        deployed_processes = result.get('deployedProcessDefinitions', {})
        if deployed_processes:
            print(f"\n📋 Развернутые процессы ({len(deployed_processes)}):")
            print("-" * 40)
            
            for process_key, process_def in deployed_processes.items():
                process_name = process_def.get('name', 'Без названия')
                process_id = process_def.get('id')
                process_version = process_def.get('version')
                is_executable = process_def.get('executable', False)
                
                print(f"   📋 {process_name}")
                print(f"      Key: {process_key}")
                print(f"      ID: {process_id}")
                print(f"      Версия: {process_version}")
                print(f"      Исполняемый: {'✅ Да' if is_executable else '❌ Нет'}")
                print()
        
        # Информация о ресурсах деплоя (опционально)
        deployed_resources = result.get('deployedCaseDefinitions', {})
        if deployed_resources:
            print(f"📄 Дополнительные ресурсы: {len(deployed_resources)}")
        
        print("=" * 60)
        print("✅ Схема успешно развернута в Camunda!")
        print("🌐 Вы можете просмотреть её в Camunda Cockpit:")
        print(f"   https://camunda.eg-holding.ru/camunda/app/cockpit/")
        
        return 0
        
    except CamundaAuthError as e:
        print(f"❌ Ошибка аутентификации: {e}")
        print("   Проверьте учетные данные в .env файле:")
        print("   - CAMUNDA_AUTH_USERNAME")
        print("   - CAMUNDA_AUTH_PASSWORD")
        return 1
        
    except CamundaValidationError as e:
        print(f"❌ Ошибка валидации BPMN: {e}")
        print("   Возможные причины:")
        print("   - Некорректный XML формат")
        print("   - Отсутствуют обязательные элементы BPMN")
        print("   - Неправильные ID элементов")
        print("   - Нарушена структура процесса")
        print("\n💡 Рекомендации:")
        print("   - Проверьте схему в BPMN редакторе")
        print("   - Убедитесь, что схема сконвертирована для Camunda")
        print("   - Используйте convert.py для конвертации из StormBPMN")
        return 1
        
    except CamundaDeployError as e:
        print(f"❌ Ошибка деплоя: {e}")
        print("   Возможные причины:")
        print("   - Конфликт с существующими процессами")
        print("   - Проблемы с определениями процессов")
        print("   - Ограничения сервера Camunda")
        return 1
        
    except FileNotFoundError as e:
        print(f"❌ Файл не найден: {e}")
        return 1
        
    except CamundaAPIError as e:
        print(f"❌ Ошибка API Camunda: {e}")
        print("   Проверьте:")
        print("   - Доступность сервера Camunda")
        print("   - Правильность URL API")
        print("   - Состояние сети")
        return 1
        
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        print(f"🔍 Тип ошибки: {type(e).__name__}")
        
        # Дополнительная информация для отладки
        if hasattr(e, '__traceback__'):
            import traceback
            print(f"📍 Детали ошибки:")
            traceback.print_exc()
            
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 