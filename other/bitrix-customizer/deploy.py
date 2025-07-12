#!/usr/bin/env python3
"""
Скрипт для деплоя JavaScript файлов на сервер Bitrix24
Заменяет copy_js_to_server.cmd для более быстрого развертывания
"""

import subprocess
import os
import sys
import json
import shutil
from pathlib import Path

def load_config():
    """Загружает конфигурацию из файла config.json"""
    config_path = Path(__file__).parent / "config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Файл конфигурации {config_path} не найден")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка в файле конфигурации: {e}")
        return None

def convert_ppk_to_openssh(ppk_path):
    """Конвертирует .ppk ключ в формат OpenSSH"""
    openssh_path = ppk_path.with_suffix('.key')
    
    # Проверяем, есть ли уже сконвертированный ключ
    if openssh_path.exists():
        return str(openssh_path)
    
    # Пытаемся найти puttygen
    puttygen_cmd = shutil.which('puttygen')
    if not puttygen_cmd:
        print("❌ puttygen не найден. Устанавливаем через chocolatey...")
        try:
            subprocess.run(['choco', 'install', 'putty', '-y'], check=True)
            puttygen_cmd = shutil.which('puttygen')
        except:
            print("❌ Не удалось установить PuTTY через chocolatey")
            return None
    
    if not puttygen_cmd:
        print("❌ puttygen не найден. Установите PuTTY или используйте другой метод аутентификации")
        return None
    
    # Конвертируем ключ
    try:
        cmd = [puttygen_cmd, str(ppk_path), '-O', 'private-openssh', '-o', str(openssh_path)]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # Устанавливаем правильные права доступа
        os.chmod(str(openssh_path), 0o600)
        
        print(f"✅ Ключ конвертирован: {openssh_path}")
        return str(openssh_path)
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка конвертации ключа: {e}")
        return None

def deploy_file(file_path, server_config):
    """Копирует файл на сервер используя scp или pscp"""
    if not os.path.exists(file_path):
        print(f"❌ Файл {file_path} не найден")
        return False
    
    print(f"📤 Копирую {file_path} на сервер...")
    
    # Определяем метод аутентификации
    auth_method = server_config.get('auth_method', 'password')
    
    if auth_method == 'key':
        return deploy_with_key(file_path, server_config)
    else:
        return deploy_with_password(file_path, server_config)

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
        key_path = Path(__file__).parent / key_file
    
    if not key_path.exists():
        print(f"❌ Файл ключа {key_path} не найден")
        return False
    
    # Сначала пытаемся использовать pscp (PuTTY версия)
    pscp_cmd = shutil.which('pscp')
    if pscp_cmd:
        return deploy_with_pscp(file_path, server_config, str(key_path))
    
    # Если pscp нет, конвертируем .ppk и используем scp
    if key_path.suffix.lower() == '.ppk':
        openssh_key = convert_ppk_to_openssh(key_path)
        if not openssh_key:
            return False
        key_path = openssh_key
    
    # Используем стандартный scp с ключом
    cmd = [
        "scp", 
        "-i", str(key_path),
        "-o", "StrictHostKeyChecking=no",
        file_path, 
        f"{server_config['user']}@{server_config['host']}:{server_config['path']}"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ {file_path} успешно скопирован")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при копировании {file_path}:")
        print(f"   {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ Команда scp не найдена. Убедитесь, что установлен SSH клиент.")
        return False

def deploy_with_pscp(file_path, server_config, key_path):
    """Деплой с использованием pscp (PuTTY версия)"""
    cmd = [
        "pscp",
        "-i", key_path,
        "-batch",  # Не запрашивать подтверждения
        file_path,
        f"{server_config['user']}@{server_config['host']}:{server_config['path']}"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ {file_path} успешно скопирован")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при копировании {file_path}:")
        print(f"   {e.stderr}")
        return False

def deploy_with_password(file_path, server_config):
    """Деплой с использованием пароля"""
    cmd = [
        "scp", 
        file_path, 
        f"{server_config['user']}@{server_config['host']}:{server_config['path']}"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ {file_path} успешно скопирован")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при копировании {file_path}:")
        print(f"   {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ Команда scp не найдена. Убедитесь, что установлен SSH клиент.")
        return False

def main():
    """Основная функция"""
    print("🚀 Начинаю деплой на сервер Bitrix24...")
    
    # Загружаем конфигурацию
    config = load_config()
    if not config:
        return 1
    
    server_config = config['server']
    files_to_deploy = config['deployment']['files']
    
    print(f"🎯 Сервер: {server_config['user']}@{server_config['host']}")
    print(f"📁 Путь: {server_config['path']}")
    
    # Показываем метод аутентификации
    auth_method = server_config.get('auth_method', 'password')
    if auth_method == 'key':
        key_file = server_config.get('key_file', 'не указан')
        print(f"🔐 Аутентификация: ключ ({key_file})")
    else:
        print(f"🔐 Аутентификация: пароль")
    
    print("-" * 50)
    
    current_dir = Path(__file__).parent
    success_count = 0
    
    for file_name in files_to_deploy:
        file_path = current_dir / file_name
        if deploy_file(str(file_path), server_config):
            success_count += 1
    
    print("-" * 50)
    print(f"✨ Деплой завершен: {success_count}/{len(files_to_deploy)} файлов")
    
    if success_count == len(files_to_deploy):
        print("🎉 Все файлы успешно развернуты!")
        return 0
    else:
        print("⚠️  Некоторые файлы не удалось развернуть")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 