#!/usr/bin/env python3
"""
Скрипт для получения отчета инспекции Bitrix24 с сервера
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
import datetime

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

def download_report(server_config):
    """Скачивает отчет инспекции с сервера"""
    print(f"📥 Скачивание отчета с сервера...")
    
    # Генерируем имя файла с временной меткой
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    local_filename = f"bitrix_inspection_report_{timestamp}.json"
    local_path = Path(__file__).parent / "reports" / local_filename
    
    # Создаем директорию для отчетов если её нет
    local_path.parent.mkdir(exist_ok=True)
    
    remote_path = f"/home/{server_config['user']}/bitrix_inspection_report.json"
    
    auth_method = server_config.get('auth_method', 'password')
    
    if auth_method == 'key':
        return download_with_key(server_config, remote_path, local_path)
    else:
        return download_with_password(server_config, remote_path, local_path)

def download_with_key(server_config, remote_path, local_path):
    """Скачивание с использованием ключа"""
    key_file = server_config.get('key_file')
    if not key_file:
        print("❌ Не указан файл ключа в конфигурации")
        return None
    
    # Поддерживаем как относительные, так и абсолютные пути
    if os.path.isabs(key_file):
        key_path = Path(key_file)
    else:
        # Относительный путь ищем в корне проекта
        key_path = Path(__file__).parent.parent / key_file
    
    if not key_path.exists():
        print(f"❌ Файл ключа {key_path} не найден")
        return None
    
    # Сначала пытаемся использовать pscp (PuTTY версия)
    pscp_cmd = shutil.which('pscp')
    if pscp_cmd:
        return download_with_pscp(server_config, key_path, remote_path, local_path)
    
    # Если pscp нет, используем scp
    if key_path.suffix.lower() == '.ppk':
        print("❌ .ppk ключ требует PuTTY утилиты (pscp) для скачивания")
        return None
    
    # Используем стандартный scp с ключом
    cmd = [
        "scp", 
        "-i", str(key_path),
        "-o", "StrictHostKeyChecking=no",
        f"{server_config['user']}@{server_config['host']}:{remote_path}",
        str(local_path)
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ Отчет скачан: {local_path}")
        return str(local_path)
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при скачивании отчета:")
        print(f"   {e.stderr}")
        return None
    except FileNotFoundError:
        print("❌ Команда scp не найдена. Убедитесь, что установлен SSH клиент.")
        return None

def download_with_pscp(server_config, key_path, remote_path, local_path):
    """Скачивание с использованием pscp (PuTTY версия)"""
    cmd = [
        "pscp",
        "-i", str(key_path),
        "-batch",  # Не запрашивать подтверждения
        f"{server_config['user']}@{server_config['host']}:{remote_path}",
        str(local_path)
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ Отчет скачан: {local_path}")
        return str(local_path)
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при скачивании отчета:")
        print(f"   {e.stderr}")
        return None

def download_with_password(server_config, remote_path, local_path):
    """Скачивание с использованием пароля"""
    cmd = [
        "scp", 
        f"{server_config['user']}@{server_config['host']}:{remote_path}",
        str(local_path)
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ Отчет скачан: {local_path}")
        return str(local_path)
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при скачивании отчета:")
        print(f"   {e.stderr}")
        return None
    except FileNotFoundError:
        print("❌ Команда scp не найдена. Убедитесь, что установлен SSH клиент.")
        return None

def analyze_report(report_path):
    """Анализирует и выводит ключевую информацию из отчета"""
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения отчета: {e}")
        return False
    
    print("\n" + "="*60)
    print("📊 АНАЛИЗ ОТЧЕТА BITRIX24")
    print("="*60)
    
    # Основная информация
    print(f"🕒 Время инспекции: {report.get('timestamp', 'неизвестно')}")
    print(f"🖥️  Хост: {report.get('hostname', 'неизвестно')}")
    
    # Системная информация
    system_info = report.get('system_info', {})
    print(f"🐧 ОС: {system_info.get('os', 'неизвестно')}")
    print(f"🔧 Ядро: {system_info.get('kernel', 'неизвестно')}")
    if system_info.get('load_avg'):
        print(f"📈 Загрузка: {system_info['load_avg']}")
    if system_info.get('disk_usage'):
        print(f"💾 Диск: {system_info['disk_usage']}")
    
    # Информация о Bitrix24
    print("\n📦 BITRIX24:")
    bitrix_info = report.get('bitrix_info', {})
    if bitrix_info.get('main_path'):
        print(f"📁 Путь установки: {bitrix_info['main_path']}")
        print(f"📦 Версия: {bitrix_info.get('version', 'неизвестна')}")
        if bitrix_info.get('version_date'):
            print(f"📅 Дата версии: {bitrix_info['version_date']}")
        
        # Проверки файлов
        checks = []
        if bitrix_info.get('has_settings'): checks.append("✅ .settings.php")
        if bitrix_info.get('has_dbconn'): checks.append("✅ dbconn.php")
        if bitrix_info.get('has_license'): checks.append("✅ license_key.php")
        
        if checks:
            print(f"📋 Файлы: {', '.join(checks)}")
    else:
        print("❌ Bitrix24 не найден!")
    
    # Информация о PHP
    print("\n🐘 PHP:")
    php_info = report.get('php_info', {})
    if php_info.get('version'):
        print(f"📦 Версия: {php_info['version']}")
        
        settings = php_info.get('settings', {})
        if settings:
            print("⚙️  Ключевые настройки:")
            for key, value in settings.items():
                print(f"   {key}: {value}")
        
        modules = php_info.get('modules', [])
        important_modules = ['mysqli', 'mbstring', 'gd', 'curl', 'openssl', 'zip']
        available_modules = [m for m in important_modules if m in modules]
        if available_modules:
            print(f"🔧 Важные модули: {', '.join(available_modules)}")
    
    # Информация о веб-сервере
    print("\n🌐 ВЕБ-СЕРВЕР:")
    web_server = report.get('web_server', {})
    if web_server.get('apache'):
        print(f"⚡ Apache: {web_server['apache']}")
    elif web_server.get('nginx'):
        print(f"⚡ Nginx: {web_server['nginx']}")
    else:
        print("❓ Веб-сервер не определен")
    
    # Структура файлов
    print("\n📁 СТРУКТУРА ФАЙЛОВ:")
    file_structure = report.get('file_structure', {})
    for dir_name, info in file_structure.items():
        if info.get('exists'):
            if 'error' in info:
                print(f"❌ {dir_name}: ошибка доступа")
            else:
                dirs_count = info.get('dirs_count', 0)
                files_count = info.get('files_count', 0)
                print(f"📂 {dir_name}: {dirs_count} папок, {files_count} файлов")
        else:
            print(f"❌ {dir_name}: не найдена")
    
    # Шаблоны
    print("\n🎨 ШАБЛОНЫ:")
    templates = report.get('templates', {})
    if templates.get('local'):
        print(f"🏠 Local: {', '.join(templates['local'])}")
    if templates.get('bitrix'):
        bitrix_templates = templates['bitrix'][:5]  # Первые 5
        more = " ..." if len(templates['bitrix']) > 5 else ""
        print(f"🔧 Bitrix: {', '.join(bitrix_templates)}{more}")
    
    # Права доступа
    print("\n🔐 ПРАВА ДОСТУПА:")
    permissions = report.get('permissions', {})
    for path, info in permissions.items():
        if 'error' in info:
            print(f"❌ {path}: ошибка")
        else:
            mode = info.get('mode', '???')
            owner = info.get('owner', '?')
            group = info.get('group', '?')
            print(f"📁 {path}: {mode} {owner}:{group}")
    
    # Информация о кастомизации
    print("\n🔧 КАСТОМИЗАЦИЯ:")
    customization_files = report.get('customization_files', {})
    if customization_files:
        init_files = {path: info for path, info in customization_files.items() if info.get('type') == 'init_file'}
        existing_init = [path for path, info in init_files.items() if info.get('exists')]
        missing_init = [path for path, info in init_files.items() if not info.get('exists')]
        
        if existing_init:
            print(f"✅ Найдены init.php файлы ({len(existing_init)}):")
            for file_path in existing_init:
                info = init_files[file_path]
                size = info.get('size', 0)
                print(f"   📄 {file_path} ({size} bytes)")
                
                # Показываем анализ содержимого
                content_analysis = info.get('content_analysis', {})
                if content_analysis:
                    if content_analysis.get('has_tasks_handlers'):
                        print(f"      🎯 Содержит обработчики задач")
                    if content_analysis.get('has_event_handlers'):
                        print(f"      ⚡ Содержит обработчики событий")
        
        if missing_init:
            print(f"❌ Отсутствуют init.php файлы ({len(missing_init)}):")
            for file_path in missing_init:
                info = init_files[file_path]
                can_create = info.get('can_create', {})
                if can_create.get('can_create'):
                    print(f"   📝 {file_path} (можно создать)")
                else:
                    reason = can_create.get('reason', 'неизвестная причина')
                    print(f"   ❌ {file_path} (нельзя создать: {reason})")
    
    # Места для кастомизации
    customization_places = report.get('customization_places', {})
    if customization_places:
        print(f"\n📁 МЕСТА ДЛЯ КАСТОМИЗАЦИИ:")
        high_priority = [path for path, info in customization_places.items() if info.get('priority') == 'high']
        
        for place_path in high_priority:
            info = customization_places[place_path]
            status = "✅ Существует" if info.get('exists') else "❌ Отсутствует"
            purpose = info.get('purpose', '')
            print(f"   {status} {place_path} - {purpose}")
            
            if info.get('exists'):
                writable = "✅ Записываемая" if info.get('writable') else "❌ Не записываемая"
                items_count = info.get('items_count', 0)
                print(f"      {writable}, элементов: {items_count}")
    
    # Существующие кастомизации
    existing_customizations = report.get('existing_customizations', {})
    if existing_customizations:
        print(f"\n🎨 СУЩЕСТВУЮЩИЕ КАСТОМИЗАЦИИ:")
        for location, info in existing_customizations.items():
            if isinstance(info, dict):
                if location == 'local':
                    php_count = len(info.get('php_files', []))
                    js_count = len(info.get('js_files', []))
                    components_count = len(info.get('components', []))
                    templates_count = len(info.get('templates', []))
                    
                    if php_count > 0:
                        print(f"   📄 Local PHP файлы: {php_count}")
                    if js_count > 0:
                        print(f"   📄 Local JS файлы: {js_count}")
                    if components_count > 0:
                        print(f"   🔧 Local компоненты: {components_count}")
                    if templates_count > 0:
                        print(f"   🎨 Local шаблоны: {templates_count}")
                elif location == 'upload':
                    suspicious_count = len(info.get('suspicious_files', []))
                    custom_dirs_count = len(info.get('custom_dirs', []))
                    
                    if suspicious_count > 0:
                        print(f"   ⚠️  Подозрительные файлы в upload: {suspicious_count}")
                    if custom_dirs_count > 0:
                        print(f"   📁 Кастомные папки в upload: {custom_dirs_count}")
                elif location == 'bitrix_templates':
                    modified_count = len(info.get('modified_templates', []))
                    custom_files_count = len(info.get('custom_files', []))
                    
                    if modified_count > 0:
                        print(f"   🔧 Модифицированные шаблоны: {modified_count}")
                    if custom_files_count > 0:
                        print(f"   📄 Кастомные файлы в шаблонах: {custom_files_count}")
    
    # Ошибки
    errors = report.get('errors', [])
    if errors:
        print(f"\n⚠️  ОШИБКИ ({len(errors)}):")
        for error in errors[:10]:  # Первые 10 ошибок
            print(f"   - {error}")
    
    print("\n" + "="*60)
    print(f"📄 Полный отчет сохранен в: {report_path}")
    
    return True

def create_summary_report(report_path):
    """Создает краткую сводку для быстрого просмотра"""
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения отчета: {e}")
        return False
    
    # Создаем краткую сводку
    summary_path = report_path.replace('.json', '_summary.txt')
    
    try:
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("КРАТКАЯ СВОДКА BITRIX24 ИНСПЕКЦИИ\n")
            f.write("="*50 + "\n\n")
            
            f.write(f"Время: {report.get('timestamp', 'неизвестно')}\n")
            f.write(f"Хост: {report.get('hostname', 'неизвестно')}\n")
            f.write(f"ОС: {report.get('system_info', {}).get('os', 'неизвестно')}\n\n")
            
            bitrix_info = report.get('bitrix_info', {})
            if bitrix_info.get('main_path'):
                f.write(f"Bitrix24 путь: {bitrix_info['main_path']}\n")
                f.write(f"Версия: {bitrix_info.get('version', 'неизвестна')}\n")
            else:
                f.write("❌ Bitrix24 не найден\n")
            
            f.write(f"\nPHP: {report.get('php_info', {}).get('version', 'неизвестно')}\n")
            
            web_server = report.get('web_server', {})
            if web_server.get('apache'):
                f.write(f"Веб-сервер: {web_server['apache']}\n")
            elif web_server.get('nginx'):
                f.write(f"Веб-сервер: {web_server['nginx']}\n")
            
            errors = report.get('errors', [])
            if errors:
                f.write(f"\nОшибки ({len(errors)}):\n")
                for error in errors:
                    f.write(f"  - {error}\n")
        
        print(f"📝 Краткая сводка создана: {summary_path}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания сводки: {e}")
        return False

def main():
    """Основная функция"""
    print("📥 Получение отчета Bitrix24 Inspector")
    print("=" * 50)
    
    # Загружаем конфигурацию
    config = load_config()
    if not config:
        return 1
    
    server_config = config['server']
    
    print(f"🎯 Сервер: {server_config['user']}@{server_config['host']}")
    print("-" * 50)
    
    # Скачиваем отчет
    report_path = download_report(server_config)
    if not report_path:
        print("\n❌ Не удалось скачать отчет")
        return 1
    
    # Анализируем отчет
    analyze_report(report_path)
    
    # Создаем краткую сводку
    create_summary_report(report_path)
    
    print("\n🎉 Получение отчета завершено!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 