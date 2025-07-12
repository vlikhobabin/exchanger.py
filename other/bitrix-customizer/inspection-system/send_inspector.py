#!/usr/bin/env python3
"""
Скрипт для отправки инспектора Bitrix24 на сервер и его запуска
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

def load_config():
    """Загружает конфигурацию из файла config.json"""
    config_path = Path(__file__).parent.parent / "config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Файл конфигурации {config_path} не найден")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка в файле конфигурации: {e}")
        return None

def deploy_inspector(server_config):
    """Отправляет инспектор на сервер"""
    # Путь к файлу инспектора
    inspector_file = Path(__file__).parent / "bitrix_inspector.py"
    
    print(f"📤 Отправка инспектора на сервер...")
    print(f"🔍 Локальный файл: {inspector_file}")
    print(f"🔍 Существует ли файл: {inspector_file.exists()}")
    
    if not inspector_file.exists():
        print(f"❌ Файл инспектора не найден: {inspector_file}")
        return False
    
    auth_method = server_config.get('auth_method', 'password')
    
    if auth_method == 'key':
        return deploy_with_key(inspector_file, server_config)
    else:
        return deploy_with_password(inspector_file, server_config)

def deploy_with_key(file_path, server_config):
    """Деплой с использованием ключа"""
    key_file = server_config.get('key_file')
    if not key_file:
        print("❌ Не указан файл ключа в конфигурации")
        return False
    
    # Поддерживаем как относительные, так и абсолютные пути
    if os.path.isabs(key_file):
        key_path = Path(key_file)
    else:
        # Относительный путь ищем в корне проекта
        key_path = Path(__file__).parent.parent / key_file
    
    if not key_path.exists():
        print(f"❌ Файл ключа {key_path} не найден")
        return False
    
    # Отправляем в домашнюю директорию пользователя
    remote_path = f"/home/{server_config['user']}/bitrix_inspector.py"
    remote_dir = f"/home/{server_config['user']}"
    
    # Создаем папку на сервере если она не существует
    if not create_remote_directory(server_config, remote_dir):
        return False
    
    # Сначала пытаемся использовать pscp (PuTTY версия)
    pscp_cmd = shutil.which('pscp')
    if pscp_cmd:
        return deploy_with_pscp(file_path, server_config, str(key_path), remote_path)
    
    # Если pscp нет, используем scp
    if key_path.suffix.lower() == '.ppk':
        print("❌ .ppk ключ требует PuTTY утилиты (pscp) для отправки")
        return False
    
    # Используем стандартный scp с ключом
    cmd = [
        "scp", 
        "-i", str(key_path),
        "-o", "StrictHostKeyChecking=no",
        str(file_path), 
        f"{server_config['user']}@{server_config['host']}:{remote_path}"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ Инспектор отправлен на сервер: {remote_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при отправке инспектора:")
        print(f"   {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ Команда scp не найдена. Убедитесь, что установлен SSH клиент.")
        return False

def deploy_with_pscp(file_path, server_config, key_path, remote_path):
    """Деплой с использованием pscp (PuTTY версия)"""
    cmd = [
        "pscp",
        "-i", key_path,
        "-batch",  # Не запрашивать подтверждения
        str(file_path),
        f"{server_config['user']}@{server_config['host']}:{remote_path}"
    ]
    
    print(f"🔍 Выполняемая команда: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ Инспектор отправлен на сервер: {remote_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при отправке инспектора:")
        print(f"   {e.stderr}")
        return False

def deploy_with_password(file_path, server_config):
    """Деплой с использованием пароля"""
    remote_path = f"/home/{server_config['user']}/bitrix_inspector.py"
    
    cmd = [
        "scp", 
        str(file_path), 
        f"{server_config['user']}@{server_config['host']}:{remote_path}"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ Инспектор отправлен на сервер: {remote_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при отправке инспектора:")
        print(f"   {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ Команда scp не найдена. Убедитесь, что установлен SSH клиент.")
        return False

def create_remote_directory(server_config, remote_dir):
    """Создает папку на удаленном сервере"""
    auth_method = server_config.get('auth_method', 'password')
    
    command = f"mkdir -p {remote_dir}"
    
    if auth_method == 'key':
        return execute_remote_command_with_key(server_config, command)
    else:
        return execute_remote_command_with_password(server_config, command)

def execute_remote_command_with_key(server_config, command):
    """Выполняет команду на удаленном сервере с ключом"""
    key_file = server_config.get('key_file')
    if not key_file:
        return False
    
    # Поддерживаем как относительные, так и абсолютные пути
    if os.path.isabs(key_file):
        key_path = Path(key_file)
    else:
        # Относительный путь ищем в корне проекта
        key_path = Path(__file__).parent.parent / key_file
    
    if not key_path.exists():
        return False
    
    # Проверяем, есть ли plink
    plink_cmd = shutil.which('plink')
    if plink_cmd:
        cmd = [
            'plink',
            '-i', str(key_path),
            '-batch',
            f"{server_config['user']}@{server_config['host']}",
            command
        ]
    else:
        # Используем SSH
        if key_path.suffix.lower() == '.ppk':
            return False
        
        cmd = [
            'ssh',
            '-i', str(key_path),
            '-o', 'StrictHostKeyChecking=no',
            f"{server_config['user']}@{server_config['host']}",
            command
        ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
        return True
    except:
        return False

def execute_remote_command_with_password(server_config, command):
    """Выполняет команду на удаленном сервере с паролем"""
    cmd = [
        'ssh',
        '-o', 'StrictHostKeyChecking=no',
        f"{server_config['user']}@{server_config['host']}",
        command
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
        return True
    except:
        return False

def run_inspector_on_server(server_config):
    """Запускает инспектор на сервере"""
    print(f"🚀 Запуск инспектора на сервере...")
    
    auth_method = server_config.get('auth_method', 'password')
    remote_script = f"/home/{server_config['user']}/bitrix_inspector.py"
    
    # Делаем файл исполняемым и запускаем
    commands = [
        f"chmod +x {remote_script}",
        f"cd /home/{server_config['user']} && python3 {remote_script}"
    ]
    
    if auth_method == 'key':
        return run_ssh_with_key(server_config, commands)
    else:
        return run_ssh_with_password(server_config, commands)

def run_ssh_with_key(server_config, commands):
    """Выполняет команды через SSH с ключом"""
    key_file = server_config.get('key_file')
    if not key_file:
        print("❌ Не указан файл ключа в конфигурации")
        return False
    
    # Поддерживаем как относительные, так и абсолютные пути
    if os.path.isabs(key_file):
        key_path = Path(key_file)
    else:
        # Относительный путь ищем в корне проекта
        key_path = Path(__file__).parent.parent / key_file
    
    if not key_path.exists():
        print(f"❌ Файл ключа {key_path} не найден")
        return False
    
    # Объединяем команды
    full_command = " && ".join(commands)
    
    # Проверяем, есть ли plink
    plink_cmd = shutil.which('plink')
    if plink_cmd:
        cmd = [
            'plink',
            '-i', str(key_path),
            '-batch',
            f"{server_config['user']}@{server_config['host']}",
            full_command
        ]
    else:
        # Используем SSH
        if key_path.suffix.lower() == '.ppk':
            print("❌ .ppk ключ требует PuTTY утилиты (plink) для выполнения команд")
            return False
        
        cmd = [
            'ssh',
            '-i', str(key_path),
            '-o', 'StrictHostKeyChecking=no',
            f"{server_config['user']}@{server_config['host']}",
            full_command
        ]
    
    try:
        print("🔗 Подключение к серверу...")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
        
        print("✅ Инспектор выполнен!")
        print("\n📋 Вывод инспектора:")
        print("-" * 50)
        print(result.stdout)
        
        if result.stderr:
            print("\n⚠️  Предупреждения:")
            print(result.stderr)
        
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ Таймаут выполнения инспектора")
        return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка выполнения инспектора: {e}")
        if e.stdout:
            print(f"Вывод: {e.stdout}")
        if e.stderr:
            print(f"Ошибки: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ SSH клиент не найден")
        return False

def run_ssh_with_password(server_config, commands):
    """Выполняет команды через SSH с паролем"""
    full_command = " && ".join(commands)
    
    cmd = [
        'ssh',
        '-o', 'StrictHostKeyChecking=no',
        f"{server_config['user']}@{server_config['host']}",
        full_command
    ]
    
    try:
        print("🔗 Подключение к серверу...")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
        
        print("✅ Инспектор выполнен!")
        print("\n📋 Вывод инспектора:")
        print("-" * 50)
        print(result.stdout)
        
        if result.stderr:
            print("\n⚠️  Предупреждения:")
            print(result.stderr)
        
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ Таймаут выполнения инспектора")
        return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка выполнения инспектора: {e}")
        if e.stdout:
            print(f"Вывод: {e.stdout}")
        if e.stderr:
            print(f"Ошибки: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ SSH клиент не найден")
        return False

def main():
    """Основная функция"""
    print("🚀 Отправка и запуск Bitrix24 Inspector")
    print("=" * 50)
    
    # Загружаем конфигурацию
    config = load_config()
    if not config:
        return 1
    
    server_config = config['server']
    
    print(f"🎯 Сервер: {server_config['user']}@{server_config['host']}")
    print(f"🔐 Аутентификация: {server_config.get('auth_method', 'password')}")
    print("-" * 50)
    
    # Отправляем инспектор
    if not deploy_inspector(server_config):
        print("\n❌ Не удалось отправить инспектор")
        return 1
    
    # Запускаем инспектор
    if not run_inspector_on_server(server_config):
        print("\n❌ Не удалось запустить инспектор")
        return 1
    
    print("\n" + "=" * 50)
    print("🎉 Инспекция завершена!")
    print("📥 Для получения подробного отчета запустите: python get_report.py")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 