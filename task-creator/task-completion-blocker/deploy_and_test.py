#!/usr/bin/env python3
"""
Главный скрипт для развертывания и тестирования блокировщика завершения задач
"""

import sys
import subprocess
import time
from pathlib import Path

def run_script(script_path, description, args=None):
    """Запускает скрипт и возвращает результат"""
    print(f"\n🚀 {description}")
    print("-" * 60)
    
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    
    try:
        result = subprocess.run(cmd, check=True, text=True)
        print(f"✅ {description} завершен успешно")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка в {description}: {e}")
        return False
    except FileNotFoundError:
        print(f"❌ Скрипт не найден: {script_path}")
        return False

def main():
    """Основная функция"""
    print("🚀 Развертывание и тестирование блокировщика завершения задач")
    print("=" * 70)
    print("📋 Этапы:")
    print("   1. Создание резервной копии оригинальных файлов")
    print("   2. Развертывание блокировщика задач на сервер")
    print("   3. Тестирование развертывания")
    print("=" * 70)
    
    project_root = Path(__file__).parent
    # Система резервирования переехала в backup-restore-system
    backup_system_dir = project_root.parent / "backup-restore-system"
    deployment_dir = project_root / "deployment"
    testing_dir = project_root / "testing"
    
    start_time = time.time()
    
    # Этап 1: Создание резервной копии
    backup_script = backup_system_dir / "backup_manager.py"
    if not run_script(backup_script, "Создание резервной копии", ["create"]):
        print("\n❌ Не удалось создать резервную копию")
        print("💡 Рекомендуется создать резервную копию вручную перед продолжением")
        
        response = input("Продолжить без резервной копии? (y/N): ")
        if response.lower() != 'y':
            print("🛑 Развертывание прервано пользователем")
            return 1
    
    # Этап 2: Развертывание
    deploy_script = deployment_dir / "deploy_task_blocker.py"
    if not run_script(deploy_script, "Развертывание блокировщика задач", ["deploy"]):
        print("\n❌ Развертывание не удалось")
        print("💡 Проверьте:")
        print("   - Подключение к серверу")
        print("   - Настройки аутентификации")
        print("   - Права доступа на сервере")
        print("   - Наличие всех необходимых файлов")
        return 1
    
    # Пауза перед тестированием
    print("\n⏳ Пауза 5 секунд перед тестированием...")
    time.sleep(5)
    
    # Этап 3: Тестирование
    test_script = testing_dir / "test_task_blocker.py"
    if not run_script(test_script, "Тестирование развертывания"):
        print("\n❌ Тестирование выявило проблемы")
        print("💡 Проверьте результаты тестирования и устраните ошибки")
        return 1
    
    end_time = time.time()
    duration = int(end_time - start_time)
    
    # Успешное завершение
    print("\n" + "=" * 70)
    print("🎉 РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО УСПЕШНО!")
    print("=" * 70)
    print(f"⏱️  Общее время: {duration} секунд")
    
    print("\n📋 Что было сделано:")
    print("   ✅ Создана резервная копия оригинальных файлов")
    print("   ✅ Развернут PHP обработчик событий")
    print("   ✅ Развернут JavaScript модификатор")
    print("   ✅ Подключены файлы к системе Bitrix24")
    print("   ✅ Проведено тестирование развертывания")
    
    print("\n🧪 Как проверить работоспособность:")
    print("   1. Войдите в Bitrix24")
    print("   2. Создайте новую задачу")
    print("   3. Установите в задаче поле 'Ожидается результат' = 'Да'")
    print("   4. Заполните поле 'Вопрос на результат'")
    print("   5. Попробуйте завершить задачу без заполнения поля 'Результат ответа'")
    print("   6. Система должна заблокировать завершение с соответствующим сообщением")
    
    print("\n📊 Мониторинг:")
    print("   - Логи блокировщика: /home/bitrix/www/bitrix/logs/")
    print("   - Поиск в логах: grep 'tasks_completion_blocker' /home/bitrix/www/bitrix/logs/*.log")
    print("   - Консоль браузера: откройте DevTools для просмотра JS логов")
    
    print("\n🔧 Управление:")
    print("   - Для отката изменений используйте резервные копии")
    print("   - Для повторного развертывания запустите этот скрипт снова")
    print("   - Для тестирования запустите: python testing/test_task_blocker.py")
    
    print("\n🎯 Блокировщик задач готов к использованию!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 