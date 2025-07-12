#!/usr/bin/env python3
"""
Утилита для проверки и настройки аутентификации на сервере
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

def check_tool(tool_name, description):
    """Проверяет доступность инструмента"""
    tool_path = shutil.which(tool_name)
    if tool_path:
        print(f"✅ {description}: {tool_path}")
        return True
    else:
        print(f"❌ {description}: не найден")
        return False

def check_ssh_tools():
    """Проверяет доступность SSH инструментов"""
    print("🔍 Проверка SSH инструментов:")
    print("-" * 40)
    
    tools = [
        ('ssh', 'SSH клиент'),
        ('scp', 'SCP (безопасное копирование)'),
        ('pscp', 'PSCP (PuTTY версия SCP)'),
        ('puttygen', 'PuTTY генератор ключей'),
        ('plink', 'PuTTY SSH клиент')
    ]
    
    available = {}
    for tool, desc in tools:
        available[tool] = check_tool(tool, desc)
    
    return available

def check_config():
    """Проверяет конфигурацию"""
    print("\n🔍 Проверка конфигурации:")
    print("-" * 40)
    
    config_path = Path(__file__).parent.parent / "config.json"
    if not config_path.exists():
        print("❌ Файл config.json не найден")
        return None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        server_config = config.get('server', {})
        auth_method = server_config.get('auth_method', 'password')
        
        print(f"✅ Конфигурация загружена")
        print(f"   Сервер: {server_config.get('user')}@{server_config.get('host')}")
        print(f"   Метод аутентификации: {auth_method}")
        
        if auth_method == 'key':
            key_file = server_config.get('key_file')
            if key_file:
                # Поддерживаем как относительные, так и абсолютные пути
                import os
                if os.path.isabs(key_file):
                    key_path = Path(key_file)
                else:
                    key_path = Path(__file__).parent / key_file
                
                if key_path.exists():
                    print(f"✅ Файл ключа: {key_file}")
                    print(f"   Путь: {key_path}")
                    print(f"   Размер: {key_path.stat().st_size} байт")
                else:
                    print(f"❌ Файл ключа не найден: {key_file}")
            else:
                print("❌ Файл ключа не указан в конфигурации")
        
        return config
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка в файле конфигурации: {e}")
        return None

def test_connection(config):
    """Тестирует подключение к серверу"""
    print("\n🔍 Тестирование подключения:")
    print("-" * 40)
    
    if not config:
        print("❌ Нет конфигурации для тестирования")
        return False
    
    server_config = config.get('server', {})
    auth_method = server_config.get('auth_method', 'password')
    
    if auth_method == 'key':
        key_file = server_config.get('key_file')
        if not key_file:
            print("❌ Файл ключа не указан")
            return False
        
        # Поддерживаем как относительные, так и абсолютные пути
        import os
        if os.path.isabs(key_file):
            key_path = Path(key_file)
        else:
            key_path = Path(__file__).parent / key_file
        
        if not key_path.exists():
            print(f"❌ Файл ключа не найден: {key_file}")
            return False
        
        # Проверяем, есть ли plink
        if shutil.which('plink'):
            cmd = [
                'plink',
                '-i', str(key_path),
                '-batch',
                f"{server_config['user']}@{server_config['host']}",
                'echo "Подключение успешно"'
            ]
        else:
            # Пытаемся использовать ssh
            if key_path.suffix.lower() == '.ppk':
                print("❌ .ppk ключ требует PuTTY утилиты (plink) для тестирования")
                return False
            
            cmd = [
                'ssh',
                '-i', str(key_path),
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'ConnectTimeout=10',
                f"{server_config['user']}@{server_config['host']}",
                'echo "Подключение успешно"'
            ]
    else:
        print("ℹ️  Тестирование с паролем не поддерживается")
        return False
    
    try:
        print(f"🔗 Подключаюсь к {server_config['user']}@{server_config['host']}...")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
        print("✅ Подключение успешно!")
        print(f"   Ответ сервера: {result.stdout.strip()}")
        return True
    except subprocess.TimeoutExpired:
        print("❌ Таймаут подключения")
        return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка подключения: {e}")
        if e.stderr:
            print(f"   Детали: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ SSH клиент не найден")
        return False

def suggest_fixes(available_tools, config):
    """Предлагает варианты исправления проблем"""
    print("\n💡 Рекомендации:")
    print("-" * 40)
    
    if not config:
        print("1. Создайте файл config.json с корректной конфигурацией")
        return
    
    server_config = config.get('server', {})
    auth_method = server_config.get('auth_method', 'password')
    
    if auth_method == 'key':
        key_file = server_config.get('key_file', '')
        # Поддерживаем как относительные, так и абсолютные пути
        import os
        if os.path.isabs(key_file):
            key_path = Path(key_file)
        else:
            key_path = Path(__file__).parent / key_file
        
        if not key_path.exists():
            if os.path.isabs(key_file):
                print(f"1. Создайте файл ключа по пути: {key_file}")
            else:
                print(f"1. Скопируйте файл ключа {key_file} в директорию скрипта")
        
        if key_file.endswith('.ppk'):
            if not available_tools.get('pscp'):
                print("2. Установите PuTTY для работы с .ppk ключами:")
                print("   - Через chocolatey: choco install putty")
                print("   - Или скачайте с https://putty.org/")
            
            if not available_tools.get('puttygen'):
                print("3. Установите puttygen для конвертации ключей")
        
        if not available_tools.get('scp') and not available_tools.get('pscp'):
            print("4. Установите SSH клиент:")
            print("   - Git for Windows (включает SSH)")
            print("   - OpenSSH для Windows")
            print("   - PuTTY suite")
    
    print("\n5. Альтернативные варианты:")
    print("   - Конвертируйте .ppk в OpenSSH формат")
    print("   - Используйте WSL с SSH")
    print("   - Настройте аутентификацию по паролю")

def main():
    """Основная функция"""
    print("🔧 Проверка настроек аутентификации")
    print("=" * 50)
    
    # Проверяем доступные инструменты
    available_tools = check_ssh_tools()
    
    # Проверяем конфигурацию
    config = check_config()
    
    # Тестируем подключение
    if config:
        test_connection(config)
    
    # Предлагаем исправления
    suggest_fixes(available_tools, config)
    
    print("\n" + "=" * 50)
    print("🎯 Для деплоя запустите: python deploy.py")

if __name__ == "__main__":
    main() 