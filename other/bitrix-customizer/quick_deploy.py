#!/usr/bin/env python3
"""
Мастер-скрипт для быстрого деплоя
Выполняет: обновление конфигурации JS + деплой на сервер
"""

import sys
import subprocess
from pathlib import Path

def run_script(script_name, description):
    """Запускает Python скрипт и возвращает код выхода"""
    script_path = Path(__file__).parent / script_name
    
    print(f"\n🚀 {description}")
    print("-" * 50)
    
    try:
        result = subprocess.run([sys.executable, str(script_path)], 
                              check=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при выполнении {script_name}: {e}")
        return False
    except FileNotFoundError:
        print(f"❌ Скрипт {script_name} не найден")
        return False

def main():
    """Основная функция"""
    print("⚡ Быстрый деплой Bitrix24 Custom Task Modifier")
    print("=" * 60)
    
    # Шаг 1: Обновление конфигурации
    if not run_script("update_js_config.py", "Обновление конфигурации JavaScript"):
        print("\n❌ Ошибка при обновлении конфигурации")
        return 1
    
    # Шаг 2: Деплой на сервер
    if not run_script("deploy.py", "Деплой на сервер"):
        print("\n❌ Ошибка при деплое")
        return 1
    
    print("\n" + "=" * 60)
    print("🎉 Быстрый деплой завершен успешно!")
    print("   ✅ Конфигурация обновлена")
    print("   ✅ Файлы развернуты на сервере")
    print("   ℹ️  Не забудьте очистить кеш Bitrix24")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 