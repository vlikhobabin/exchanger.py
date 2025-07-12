#!/usr/bin/env python3
"""
Скрипт для быстрой настройки проекта Bitrix24 Custom Task Modifier
"""

import json
import os
import shutil
import sys
from pathlib import Path

def print_header():
    """Выводит заголовок"""
    print("🚀 Настройка Bitrix24 Custom Task Modifier")
    print("=" * 50)

def check_config_exists():
    """Проверяет, существует ли файл конфигурации"""
    config_path = Path(__file__).parent.parent / "config.json"
    return config_path.exists()

def create_config_from_template():
    """Создает конфигурацию из шаблона"""
    template_path = Path(__file__).parent / "config.example.json"
    config_path = Path(__file__).parent.parent / "config.json"
    
    if not template_path.exists():
        print("❌ Файл config.example.json не найден")
        return False
    
    try:
        shutil.copy(template_path, config_path)
        print("✅ Создан файл config.json из шаблона")
        return True
    except Exception as e:
        print(f"❌ Ошибка при создании config.json: {e}")
        return False

def get_user_input(prompt, default=None):
    """Получает ввод от пользователя"""
    if default:
        response = input(f"{prompt} [{default}]: ").strip()
        return response if response else default
    else:
        return input(f"{prompt}: ").strip()

def interactive_config():
    """Интерактивная настройка конфигурации"""
    print("\n🔧 Интерактивная настройка конфигурации")
    print("-" * 40)
    
    # Загружаем текущую конфигурацию
    config_path = Path(__file__).parent.parent / "config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except:
        print("❌ Не удалось загрузить конфигурацию")
        return False
    
    print("\n📡 Настройки сервера:")
    config['server']['host'] = get_user_input("IP адрес сервера", config['server']['host'])
    config['server']['user'] = get_user_input("Пользователь", config['server']['user'])
    config['server']['path'] = get_user_input("Путь на сервере", config['server']['path'])
    
    print("\n🔐 Настройки аутентификации:")
    print("1. Ключ (рекомендуется)")
    print("2. Пароль")
    auth_choice = get_user_input("Выберите метод аутентификации", "1")
    
    if auth_choice == "1":
        config['server']['auth_method'] = 'key'
        
        # Предлагаем стандартные пути
        username = os.environ.get('USERNAME', 'user')
        default_key_path = f"C:/Users/{username}/.ssh/privete-key.ppk"
        
        config['server']['key_file'] = get_user_input("Путь к файлу ключа", default_key_path)
        
        # Проверяем, существует ли файл ключа
        if not Path(config['server']['key_file']).exists():
            print(f"⚠️  Файл ключа {config['server']['key_file']} не найден")
            print("   Не забудьте скопировать файл ключа в указанное место!")
    else:
        config['server']['auth_method'] = 'password'
        if 'key_file' in config['server']:
            del config['server']['key_file']
    
    print("\n📋 Настройки полей Bitrix24:")
    print("Если вы не знаете ID полей, можете пропустить этот шаг")
    
    update_fields = get_user_input("Обновить ID полей? (y/n)", "n").lower()
    if update_fields == 'y':
        yes_id = get_user_input("ID для 'ДА'", str(config['bitrix_field_config']['UF_RESULT_ANSWER']['values']['yes']))
        no_id = get_user_input("ID для 'НЕТ'", str(config['bitrix_field_config']['UF_RESULT_ANSWER']['values']['no']))
        
        config['bitrix_field_config']['UF_RESULT_ANSWER']['values']['yes'] = int(yes_id)
        config['bitrix_field_config']['UF_RESULT_ANSWER']['values']['no'] = int(no_id)
    
    # Сохраняем конфигурацию
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        print("\n✅ Конфигурация сохранена")
        return True
    except Exception as e:
        print(f"\n❌ Ошибка при сохранении конфигурации: {e}")
        return False

def check_key_security():
    """Проверяет безопасность ключа"""
    print("\n🛡️ Проверка безопасности")
    print("-" * 40)
    
    # Проверяем, нет ли ключей в директории проекта
    project_dir = Path(__file__).parent
    key_files = list(project_dir.glob("*.ppk")) + list(project_dir.glob("*.pem")) + list(project_dir.glob("id_*"))
    
    if key_files:
        print("⚠️  Найдены файлы ключей в директории проекта:")
        for key_file in key_files:
            print(f"   - {key_file.name}")
        
        print("\n🔴 ВНИМАНИЕ: Приватные ключи не должны находиться в директории проекта!")
        print("   Переместите их в безопасное место (например, ~/.ssh/)")
        
        return False
    else:
        print("✅ Приватные ключи не найдены в директории проекта")
        return True

def run_diagnostics():
    """Запускает диагностику"""
    print("\n🔍 Запуск диагностики")
    print("-" * 40)
    
    try:
        import subprocess
        result = subprocess.run([sys.executable, "check_auth.py"], 
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✅ Диагностика прошла успешно")
            return True
        else:
            print("❌ Проблемы обнаружены при диагностике")
            print(result.stdout)
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Ошибка при запуске диагностики: {e}")
        return False

def main():
    """Основная функция"""
    print_header()
    
    # Проверяем существование конфигурации
    if not check_config_exists():
        print("📄 Конфигурационный файл не найден")
        if not create_config_from_template():
            return 1
    else:
        print("📄 Конфигурационный файл найден")
    
    # Интерактивная настройка
    if not interactive_config():
        return 1
    
    # Проверка безопасности
    check_key_security()
    
    # Запуск диагностики
    if not run_diagnostics():
        print("\n⚠️  Обнаружены проблемы. Запустите 'python check_auth.py' для подробной диагностики")
    
    print("\n" + "=" * 50)
    print("🎉 Настройка завершена!")
    print("\n📋 Следующие шаги:")
    print("1. Убедитесь, что файл ключа находится в безопасном месте")
    print("2. Запустите 'python check_auth.py' для проверки")
    print("3. Запустите 'python quick_deploy.py' для деплоя")
    print("4. Ознакомьтесь с SECURITY.md для дополнительных рекомендаций")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 