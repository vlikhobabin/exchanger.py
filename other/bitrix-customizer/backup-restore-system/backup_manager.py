#!/usr/bin/env python3
"""
Скрипт для создания резервных копий оригинальных файлов Bitrix24
перед их модификацией
"""

import os
import sys
import json
import shutil
import subprocess
import datetime
from pathlib import Path

class BitrixBackupManager:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.backup_dir = self.project_root / "backups"
        self.config_file = self.project_root.parent / "config.json"
        self.backup_list = [
            # Файлы для резервного копирования
            {
                "remote_path": "/home/bitrix/www/local/php_interface/init.php",
                "local_path": "local_php_interface_init.php",
                "description": "Файл инициализации локальных модификаций"
            },
            {
                "remote_path": "/home/bitrix/www/bitrix/php_interface/init.php", 
                "local_path": "bitrix_php_interface_init.php",
                "description": "Системный файл инициализации Bitrix24"
            },
            # КРИТИЧЕСКИ ВАЖНО: Добавляем header.php в резервное копирование
            {
                "remote_path": "/home/bitrix/www/local/templates/bitrix24/header.php",
                "local_path": "local_templates_bitrix24_header.php",
                "description": "Заголовок локального шаблона Bitrix24",
                "required": False  # Файл может не существовать
            },
            {
                "remote_path": "/home/bitrix/www/local/templates/bitrix24/footer.php",
                "local_path": "local_templates_bitrix24_footer.php",
                "description": "Подвал локального шаблона Bitrix24",
                "required": False  # Файл может не существовать
            },
            # Дополнительные критически важные файлы
            {
                "remote_path": "/home/bitrix/www/.settings.php",
                "local_path": "root_settings.php",
                "description": "Основные настройки Bitrix24",
                "required": False
            },
            {
                "remote_path": "/home/bitrix/www/bitrix/.settings.php",
                "local_path": "bitrix_settings.php",
                "description": "Системные настройки Bitrix24",
                "required": False
            }
        ]
        
    def load_config(self):
        """Загружает конфигурацию сервера"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Файл конфигурации {self.config_file} не найден")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка в файле конфигурации: {e}")
            return None
    
    def load_inspection_report(self):
        """Загружает последний отчет инспекции для анализа файлов"""
        reports_dir = self.project_root.parent / "inspection-system" / "reports"
        if not reports_dir.exists():
            print("ℹ️  Отчет инспекции не найден, используется стандартный список файлов")
            return None
        
        # Ищем последний отчет
        json_files = list(reports_dir.glob("bitrix_inspection_report_*.json"))
        if not json_files:
            print("ℹ️  Отчет инспекции не найден, используется стандартный список файлов")
            return None
        
        # Сортируем по дате в названии файла
        latest_report = max(json_files, key=lambda x: x.name)
        
        try:
            with open(latest_report, 'r', encoding='utf-8') as f:
                report = json.load(f)
            print(f"📊 Загружен отчет инспекции: {latest_report.name}")
            return report
        except Exception as e:
            print(f"❌ Ошибка загрузки отчета инспекции: {e}")
            return None
    
    def update_backup_list_from_report(self, report):
        """Обновляет список файлов для резервного копирования на основе отчета"""
        if not report:
            return
        
        customization_files = report.get('customization_files', {})
        if not customization_files:
            return
        
        # Создаем новый список файлов на основе отчета
        new_backup_list = []
        
        for file_path, file_info in customization_files.items():
            # Резервируем только существующие файлы
            if file_info.get('exists') and file_info.get('type') in ['init_file', 'db_config']:
                local_filename = file_path.replace('/', '_').replace('\\', '_')
                new_backup_list.append({
                    "remote_path": file_info['full_path'],
                    "local_path": local_filename,
                    "description": file_info.get('purpose', 'Файл кастомизации'),
                    "file_type": file_info.get('type'),
                    "size": file_info.get('size', 0)
                })
        
        if new_backup_list:
            print(f"📋 Список файлов обновлен на основе отчета инспекции: {len(new_backup_list)} файлов")
            self.backup_list = new_backup_list
        else:
            print("ℹ️  В отчете инспекции не найдены файлы для резервного копирования")
    
    def analyze_files_for_backup(self, report):
        """Анализирует файлы из отчета и выводит план резервного копирования"""
        if not report:
            return
        
        customization_files = report.get('customization_files', {})
        if not customization_files:
            return
        
        print("\n📊 Анализ файлов для резервного копирования:")
        print("-" * 50)
        
        existing_files = []
        missing_files = []
        
        for file_path, file_info in customization_files.items():
            if file_info.get('type') in ['init_file', 'db_config']:
                if file_info.get('exists'):
                    existing_files.append({
                        'path': file_path,
                        'size': file_info.get('size', 0),
                        'purpose': file_info.get('purpose', ''),
                        'type': file_info.get('type')
                    })
                else:
                    missing_files.append({
                        'path': file_path,
                        'purpose': file_info.get('purpose', ''),
                        'can_create': file_info.get('can_create', {}).get('can_create', False)
                    })
        
        if existing_files:
            print(f"✅ Файлы для резервного копирования ({len(existing_files)}):")
            for file_info in existing_files:
                size_str = f"({file_info['size']} байт)" if file_info['size'] > 0 else ""
                print(f"   📄 {file_info['path']} {size_str}")
                print(f"      {file_info['purpose']}")
        
        if missing_files:
            print(f"\n❌ Файлы отсутствуют на сервере ({len(missing_files)}):")
            for file_info in missing_files:
                create_status = "можно создать" if file_info['can_create'] else "нельзя создать"
                print(f"   📝 {file_info['path']} ({create_status})")
                print(f"      {file_info['purpose']}")
        
        print("-" * 50)
    
    def create_backup_directory(self):
        """Создает структуру папок для резервных копий"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_session_dir = self.backup_dir / f"backup_{timestamp}"
        backup_session_dir.mkdir(parents=True, exist_ok=True)
        
        # Создаем файл с информацией о резервной копии
        backup_info = {
            "timestamp": datetime.datetime.now().isoformat(),
            "files": [],
            "server_info": None
        }
        
        return backup_session_dir, backup_info
    
    def backup_file_from_server(self, server_config, remote_path, local_path):
        """Скачивает файл с сервера для резервного копирования"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._backup_with_key(server_config, remote_path, local_path)
        else:
            return self._backup_with_password(server_config, remote_path, local_path)
    
    def _backup_with_key(self, server_config, remote_path, local_path):
        """Резервное копирование с использованием ключа"""
        key_file = server_config.get('key_file')
        if not key_file:
            print("❌ Не указан файл ключа в конфигурации")
            return False
        
        # Поддерживаем как относительные, так и абсолютные пути
        if os.path.isabs(key_file):
            key_path = Path(key_file)
        else:
            key_path = self.project_root.parent / key_file
        
        if not key_path.exists():
            print(f"❌ Файл ключа {key_path} не найден")
            return False
        
        # Проверяем, есть ли pscp
        pscp_cmd = shutil.which('pscp')
        if pscp_cmd and key_path.suffix.lower() == '.ppk':
            cmd = [
                "pscp",
                "-i", str(key_path),
                "-batch",
                f"{server_config['user']}@{server_config['host']}:{remote_path}",
                str(local_path)
            ]
        else:
            # Используем scp
            if key_path.suffix.lower() == '.ppk':
                print("❌ .ppk ключ требует PuTTY утилиты (pscp)")
                return False
            
            cmd = [
                "scp",
                "-i", str(key_path),
                "-o", "StrictHostKeyChecking=no",
                f"{server_config['user']}@{server_config['host']}:{remote_path}",
                str(local_path)
            ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            # Файл может не существовать - это нормально
            if "No such file" in e.stderr:
                print(f"⚠️  Файл {remote_path} не найден на сервере (возможно, еще не создан)")
                return False
            else:
                print(f"❌ Ошибка при копировании {remote_path}: {e.stderr}")
                return False
        except FileNotFoundError:
            print("❌ Команда scp/pscp не найдена")
            return False
    
    def _backup_with_password(self, server_config, remote_path, local_path):
        """Резервное копирование с использованием пароля"""
        cmd = [
            "scp",
            f"{server_config['user']}@{server_config['host']}:{remote_path}",
            str(local_path)
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            if "No such file" in e.stderr:
                print(f"⚠️  Файл {remote_path} не найден на сервере (возможно, еще не создан)")
                return False
            else:
                print(f"❌ Ошибка при копировании {remote_path}: {e.stderr}")
                return False
        except FileNotFoundError:
            print("❌ Команда scp не найдена")
            return False
    
    def create_backup(self):
        """Создает полную резервную копию"""
        print("📦 Создание резервной копии оригинальных файлов Bitrix24")
        print("=" * 60)
        
        # Загружаем конфигурацию
        config = self.load_config()
        if not config:
            return False
        
        server_config = config['server']
        print(f"🎯 Сервер: {server_config['user']}@{server_config['host']}")
        print("-" * 60)
        
        # Загружаем и анализируем отчет инспекции
        inspection_report = self.load_inspection_report()
        if inspection_report:
            self.analyze_files_for_backup(inspection_report)
            self.update_backup_list_from_report(inspection_report)
        
        # Создаем папку для резервной копии
        backup_session_dir, backup_info = self.create_backup_directory()
        backup_info['server_info'] = {
            'host': server_config['host'],
            'user': server_config['user'],
            'auth_method': server_config.get('auth_method', 'password')
        }
        
        # Добавляем информацию об отчете инспекции
        if inspection_report:
            backup_info['inspection_report'] = {
                'timestamp': inspection_report.get('timestamp'),
                'hostname': inspection_report.get('hostname'),
                'bitrix_path': inspection_report.get('bitrix_info', {}).get('main_path')
            }
        
        print(f"📁 Папка резервной копии: {backup_session_dir}")
        
        # Проверяем, есть ли файлы для резервного копирования
        if not self.backup_list:
            print("\n⚠️  Нет файлов для резервного копирования")
            print("ℹ️  Возможно, файлы init.php еще не созданы на сервере")
            print("ℹ️  Резервное копирование будет выполнено после создания файлов")
            
            # Сохраняем информацию о пустой резервной копии
            info_file = backup_session_dir / "backup_info.json"
            try:
                with open(info_file, 'w', encoding='utf-8') as f:
                    json.dump(backup_info, f, indent=2, ensure_ascii=False)
                print(f"📄 Информация сохранена: {info_file}")
            except Exception as e:
                print(f"❌ Ошибка сохранения информации: {e}")
            
            return False
        
        # Копируем файлы
        successful_backups = 0
        failed_backups = 0
        
        for file_info in self.backup_list:
            remote_path = file_info['remote_path']
            local_filename = file_info['local_path']
            local_path = backup_session_dir / local_filename
            is_required = file_info.get('required', True)
            
            print(f"\n📥 Копирование: {remote_path}")
            
            if self.backup_file_from_server(server_config, remote_path, local_path):
                print(f"✅ Успешно скопирован: {local_filename}")
                backup_info['files'].append({
                    'remote_path': remote_path,
                    'local_path': local_filename,
                    'description': file_info['description'],
                    'file_type': file_info.get('file_type'),
                    'size': file_info.get('size', 0),
                    'status': 'success',
                    'required': is_required
                })
                successful_backups += 1
            else:
                status_text = "❌ Не удалось скопировать" if is_required else "⚠️  Файл отсутствует (необязательный)"
                print(f"{status_text}: {remote_path}")
                backup_info['files'].append({
                    'remote_path': remote_path,
                    'local_path': local_filename,
                    'description': file_info['description'],
                    'file_type': file_info.get('file_type'),
                    'size': file_info.get('size', 0),
                    'status': 'failed',
                    'required': is_required
                })
                # Увеличиваем счетчик failed_backups только для обязательных файлов
                if is_required:
                    failed_backups += 1
        
        # Сохраняем информацию о резервной копии
        info_file = backup_session_dir / "backup_info.json"
        with open(info_file, 'w', encoding='utf-8') as f:
            json.dump(backup_info, f, indent=2, ensure_ascii=False)
        
        print(f"\n" + "=" * 60)
        print(f"📊 Результат резервного копирования:")
        print(f"   ✅ Успешно скопированы: {successful_backups} файлов")
        print(f"   ❌ Критические ошибки: {failed_backups} файлов")
        print(f"   ⚠️  Необязательные файлы: {len(self.backup_list) - successful_backups - failed_backups}")
        print(f"   📄 Информация сохранена: {info_file}")
        print(f"   📁 Папка резервной копии: {backup_session_dir}")
        
        # Успешным считаем резервное копирование, если нет критических ошибок
        return failed_backups == 0
    
    def restore_backup(self, backup_session_name):
        """Восстанавливает файлы из резервной копии"""
        backup_session_dir = self.backup_dir / backup_session_name
        
        if not backup_session_dir.exists():
            print(f"❌ Резервная копия {backup_session_name} не найдена")
            return False
        
        info_file = backup_session_dir / "backup_info.json"
        if not info_file.exists():
            print(f"❌ Файл информации о резервной копии не найден")
            return False
        
        with open(info_file, 'r', encoding='utf-8') as f:
            backup_info = json.load(f)
        
        print(f"🔄 Восстановление из резервной копии: {backup_session_name}")
        print(f"📅 Дата создания: {backup_info['timestamp']}")
        print("-" * 60)
        
        # Здесь может быть логика восстановления файлов на сервер
        # Пока просто выводим информацию
        for file_info in backup_info['files']:
            if file_info['status'] == 'success':
                print(f"✅ Доступен для восстановления: {file_info['remote_path']}")
            else:
                print(f"❌ Не доступен: {file_info['remote_path']}")
        
        return True
    
    def list_backups(self):
        """Выводит список всех резервных копий"""
        if not self.backup_dir.exists():
            print("❌ Папка резервных копий не найдена")
            return
        
        backup_dirs = [d for d in self.backup_dir.iterdir() if d.is_dir() and d.name.startswith('backup_')]
        
        if not backup_dirs:
            print("ℹ️  Резервные копии не найдены")
            return
        
        print("📋 Список резервных копий:")
        print("-" * 60)
        
        for backup_dir in sorted(backup_dirs):
            info_file = backup_dir / "backup_info.json"
            if info_file.exists():
                with open(info_file, 'r', encoding='utf-8') as f:
                    backup_info = json.load(f)
                
                successful_files = sum(1 for f in backup_info['files'] if f['status'] == 'success')
                total_files = len(backup_info['files'])
                
                print(f"📦 {backup_dir.name}")
                print(f"   📅 Дата: {backup_info['timestamp']}")
                print(f"   📊 Файлов: {successful_files}/{total_files}")
                print(f"   🖥️  Сервер: {backup_info.get('server_info', {}).get('host', 'unknown')}")
                print()

def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python backup_manager.py create    - создать резервную копию")
        print("  python backup_manager.py list      - список резервных копий")
        print("  python backup_manager.py restore <name> - восстановить резервную копию")
        return 1
    
    manager = BitrixBackupManager()
    
    command = sys.argv[1].lower()
    
    if command == "create":
        success = manager.create_backup()
        return 0 if success else 1
    elif command == "list":
        manager.list_backups()
        return 0
    elif command == "restore" and len(sys.argv) > 2:
        backup_name = sys.argv[2]
        success = manager.restore_backup(backup_name)
        return 0 if success else 1
    else:
        print("❌ Неизвестная команда")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 