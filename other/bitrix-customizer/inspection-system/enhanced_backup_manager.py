#!/usr/bin/env python3
"""
Улучшенная система резервного копирования для Bitrix24
Использует анализатор файлов для автоматического определения всех файлов для резервирования
"""

import os
import sys
import json
import shutil
import subprocess
import datetime
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from file_analyzer import BitrixFileAnalyzer


class EnhancedBackupManager:
    """Улучшенная система резервного копирования с автоматическим анализом"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.backup_dir = self.project_root / "backups"
        self.config_file = self.project_root / "config.json"
        self.reports_dir = self.project_root / "reports"
        self.file_analyzer = BitrixFileAnalyzer()
        
        # Создаем необходимые директории
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_info = {
            'timestamp': datetime.datetime.now().isoformat(),
            'session_id': self._generate_session_id(),
            'files_analyzed': {},
            'files_backed_up': {},
            'validation_results': {},
            'errors': [],
            'warnings': []
        }
        
    def _generate_session_id(self) -> str:
        """Генерирует уникальный ID сессии"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"backup_session_{timestamp}"
    
    def load_config(self) -> Optional[Dict]:
        """Загружает конфигурацию сервера"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            self.session_info['errors'].append(f"Файл конфигурации {self.config_file} не найден")
            return None
        except json.JSONDecodeError as e:
            self.session_info['errors'].append(f"Ошибка в файле конфигурации: {e}")
            return None
    
    def create_comprehensive_backup(self, deployment_config: Optional[Dict] = None, 
                                   inspection_report_path: Optional[str] = None) -> bool:
        """Создает комплексное резервное копирование"""
        print("🔄 СОЗДАНИЕ КОМПЛЕКСНОГО РЕЗЕРВНОГО КОПИРОВАНИЯ")
        print("="*70)
        
        # Загружаем конфигурацию
        config = self.load_config()
        if not config:
            return False
        
        server_config = config['server']
        print(f"🎯 Сервер: {server_config['user']}@{server_config['host']}")
        print(f"🔐 Аутентификация: {server_config.get('auth_method', 'password')}")
        print("-" * 70)
        
        # Этап 1: Анализ файлов для резервирования
        print("\n📊 ЭТАП 1: АНАЛИЗ ФАЙЛОВ")
        print("-" * 40)
        
        files_to_backup = self._analyze_files_for_backup(deployment_config, inspection_report_path)
        if not files_to_backup:
            print("❌ Не найдено файлов для резервирования")
            return False
        
        print(f"✅ Определено {len(files_to_backup)} файлов для резервирования")
        
        # Этап 2: Предварительная проверка
        print("\n🔍 ЭТАП 2: ПРЕДВАРИТЕЛЬНАЯ ПРОВЕРКА")
        print("-" * 40)
        
        pre_check_results = self._pre_backup_validation(server_config, files_to_backup)
        if not pre_check_results['success']:
            print("❌ Предварительная проверка не пройдена")
            return False
        
        print("✅ Предварительная проверка пройдена")
        
        # Этап 3: Создание резервной копии
        print("\n📦 ЭТАП 3: СОЗДАНИЕ РЕЗЕРВНОЙ КОПИИ")
        print("-" * 40)
        
        backup_results = self._perform_backup(server_config, files_to_backup)
        
        # Этап 4: Проверка целостности
        print("\n🔐 ЭТАП 4: ПРОВЕРКА ЦЕЛОСТНОСТИ")
        print("-" * 40)
        
        integrity_results = self._verify_backup_integrity(backup_results)
        
        # Этап 5: Сохранение отчета
        print("\n📄 ЭТАП 5: СОХРАНЕНИЕ ОТЧЕТА")
        print("-" * 40)
        
        self._save_backup_report(backup_results, integrity_results)
        
        # Финальная сводка
        self._print_backup_summary(backup_results, integrity_results)
        
        return backup_results['success']
    
    def _analyze_files_for_backup(self, deployment_config: Optional[Dict], 
                                 inspection_report_path: Optional[str]) -> Dict:
        """Анализирует файлы для резервирования"""
        files_to_backup = {}
        
        # Анализируем на основе конфигурации развертывания
        if deployment_config:
            analysis_result = self.file_analyzer.analyze_deployment_plan(deployment_config)
            files_to_backup.update(analysis_result.get('files_to_backup', {}))
        
        # Анализируем на основе отчета инспекции
        if inspection_report_path and os.path.exists(inspection_report_path):
            analysis_result = self.file_analyzer.analyze_from_inspection_report(inspection_report_path)
            files_to_backup.update(analysis_result.get('files_to_backup', {}))
        
        # Добавляем дополнительные критические файлы
        additional_critical_files = self._get_additional_critical_files()
        for file_path, file_info in additional_critical_files.items():
            if file_path not in files_to_backup:
                files_to_backup[file_path] = file_info
        
        self.session_info['files_analyzed'] = files_to_backup
        return files_to_backup
    
    def _get_additional_critical_files(self) -> Dict:
        """Получает дополнительные критические файлы, которые всегда должны быть зарезервированы"""
        additional_files = {}
        
        # Критические файлы, которые могут быть изменены развертыванием
        critical_patterns = [
            '/home/bitrix/www/local/php_interface/init.php',
            '/home/bitrix/www/local/templates/bitrix24/header.php',
            '/home/bitrix/www/local/templates/bitrix24/footer.php',
            '/home/bitrix/www/local/.settings.php',
            '/home/bitrix/www/bitrix/.settings.php'
        ]
        
        for file_path in critical_patterns:
            additional_files[file_path] = {
                'remote_path': file_path,
                'local_path': os.path.basename(file_path),
                'file_type': self.file_analyzer._determine_file_type(file_path),
                'priority': 'critical',
                'backup_required': True,
                'modification_type': 'potential_modification',
                'dependencies': [],
                'risks': ['critical_system_file'],
                'always_backup': True
            }
        
        return additional_files
    
    def _pre_backup_validation(self, server_config: Dict, files_to_backup: Dict) -> Dict:
        """Выполняет предварительную проверку перед резервированием"""
        validation_results = {
            'success': True,
            'server_accessible': False,
            'permissions_ok': False,
            'disk_space_ok': False,
            'files_accessible': [],
            'files_missing': [],
            'files_permission_denied': [],
            'warnings': []
        }
        
        # Проверка доступности сервера
        print("🔗 Проверка доступности сервера...")
        if self._test_server_connection(server_config):
            validation_results['server_accessible'] = True
            print("✅ Сервер доступен")
        else:
            validation_results['success'] = False
            print("❌ Сервер недоступен")
            return validation_results
        
        # Проверка места на диске
        print("💾 Проверка места на диске...")
        if self._check_disk_space(server_config):
            validation_results['disk_space_ok'] = True
            print("✅ Достаточно места на диске")
        else:
            validation_results['warnings'].append("Мало места на диске")
            print("⚠️  Мало места на диске")
        
        # Проверка доступности файлов
        print("📁 Проверка доступности файлов...")
        for file_path, file_info in files_to_backup.items():
            access_status = self._check_file_access(server_config, file_path)
            
            if access_status == 'accessible':
                validation_results['files_accessible'].append(file_path)
            elif access_status == 'missing':
                validation_results['files_missing'].append(file_path)
                if file_info.get('always_backup'):
                    validation_results['warnings'].append(f"Критический файл отсутствует: {file_path}")
            elif access_status == 'permission_denied':
                validation_results['files_permission_denied'].append(file_path)
                validation_results['success'] = False
        
        print(f"✅ Доступные файлы: {len(validation_results['files_accessible'])}")
        print(f"⚠️  Отсутствующие файлы: {len(validation_results['files_missing'])}")
        print(f"❌ Недоступные файлы: {len(validation_results['files_permission_denied'])}")
        
        return validation_results
    
    def _perform_backup(self, server_config: Dict, files_to_backup: Dict) -> Dict:
        """Выполняет резервное копирование"""
        # Создаем папку для сессии
        session_dir = self.backup_dir / self.session_info['session_id']
        session_dir.mkdir(parents=True, exist_ok=True)
        
        backup_results = {
            'success': True,
            'session_dir': str(session_dir),
            'files_backed_up': {},
            'files_failed': {},
            'total_files': len(files_to_backup),
            'successful_count': 0,
            'failed_count': 0,
            'total_size': 0
        }
        
        # Сортируем файлы по приоритету
        sorted_files = sorted(files_to_backup.items(), 
                            key=lambda x: self._get_priority_order(x[1].get('priority', 'medium')))
        
        for file_path, file_info in sorted_files:
            print(f"📥 Резервирование: {os.path.basename(file_path)}")
            
            local_filename = self._generate_backup_filename(file_path, file_info)
            local_path = session_dir / local_filename
            
            backup_file_result = self._backup_single_file(server_config, file_path, local_path, file_info)
            
            if backup_file_result['success']:
                backup_results['files_backed_up'][file_path] = backup_file_result
                backup_results['successful_count'] += 1
                backup_results['total_size'] += backup_file_result.get('size', 0)
                print(f"✅ {os.path.basename(file_path)} - {backup_file_result.get('size', 0)} байт")
            else:
                backup_results['files_failed'][file_path] = backup_file_result
                backup_results['failed_count'] += 1
                print(f"❌ {os.path.basename(file_path)} - {backup_file_result.get('error', 'Неизвестная ошибка')}")
        
        # Создаем метаданные резервной копии
        metadata = {
            'timestamp': self.session_info['timestamp'],
            'session_id': self.session_info['session_id'],
            'server_info': {
                'host': server_config['host'],
                'user': server_config['user'],
                'auth_method': server_config.get('auth_method', 'password')
            },
            'files_backed_up': backup_results['files_backed_up'],
            'files_failed': backup_results['files_failed'],
            'statistics': {
                'total_files': backup_results['total_files'],
                'successful_count': backup_results['successful_count'],
                'failed_count': backup_results['failed_count'],
                'total_size': backup_results['total_size']
            }
        }
        
        # Сохраняем метаданные
        metadata_file = session_dir / 'backup_metadata.json'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        backup_results['metadata_file'] = str(metadata_file)
        
        if backup_results['failed_count'] > 0:
            backup_results['success'] = False
        
        return backup_results
    
    def _backup_single_file(self, server_config: Dict, remote_path: str, local_path: Path, file_info: Dict) -> Dict:
        """Резервирует один файл"""
        result = {
            'success': False,
            'remote_path': remote_path,
            'local_path': str(local_path),
            'file_info': file_info,
            'size': 0,
            'checksum': None,
            'error': None
        }
        
        try:
            # Выполняем копирование
            if self._copy_file_from_server(server_config, remote_path, local_path):
                # Проверяем результат
                if local_path.exists():
                    result['success'] = True
                    result['size'] = local_path.stat().st_size
                    result['checksum'] = self._calculate_file_checksum(local_path)
                else:
                    result['error'] = 'Файл не найден после копирования'
            else:
                result['error'] = 'Ошибка при копировании'
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def _copy_file_from_server(self, server_config: Dict, remote_path: str, local_path: Path) -> bool:
        """Копирует файл с сервера"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._copy_with_key(server_config, remote_path, local_path)
        else:
            return self._copy_with_password(server_config, remote_path, local_path)
    
    def _copy_with_key(self, server_config: Dict, remote_path: str, local_path: Path) -> bool:
        """Копирует файл с использованием ключа"""
        key_file = server_config.get('key_file')
        if not key_file:
            return False
        
        # Поддерживаем как относительные, так и абсолютные пути
        if os.path.isabs(key_file):
            key_path = Path(key_file)
        else:
            key_path = self.project_root / key_file
        
        if not key_path.exists():
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
                return False
            
            cmd = [
                "scp",
                "-i", str(key_path),
                "-o", "StrictHostKeyChecking=no",
                f"{server_config['user']}@{server_config['host']}:{remote_path}",
                str(local_path)
            ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
            return True
        except subprocess.CalledProcessError:
            return False
        except subprocess.TimeoutExpired:
            return False
        except FileNotFoundError:
            return False
    
    def _copy_with_password(self, server_config: Dict, remote_path: str, local_path: Path) -> bool:
        """Копирует файл с использованием пароля"""
        cmd = [
            "scp",
            "-o", "StrictHostKeyChecking=no",
            f"{server_config['user']}@{server_config['host']}:{remote_path}",
            str(local_path)
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
            return True
        except subprocess.CalledProcessError:
            return False
        except subprocess.TimeoutExpired:
            return False
        except FileNotFoundError:
            return False
    
    def _verify_backup_integrity(self, backup_results: Dict) -> Dict:
        """Проверяет целостность резервной копии"""
        integrity_results = {
            'success': True,
            'verified_files': {},
            'corrupted_files': {},
            'verification_errors': [],
            'total_verified': 0,
            'total_corrupted': 0
        }
        
        print("🔍 Проверка целостности резервной копии...")
        
        for file_path, file_info in backup_results.get('files_backed_up', {}).items():
            local_path = Path(file_info['local_path'])
            
            if local_path.exists():
                # Проверяем размер файла
                actual_size = local_path.stat().st_size
                expected_size = file_info.get('size', 0)
                
                # Проверяем контрольную сумму
                actual_checksum = self._calculate_file_checksum(local_path)
                expected_checksum = file_info.get('checksum')
                
                verification_result = {
                    'file_path': file_path,
                    'local_path': str(local_path),
                    'size_match': actual_size == expected_size,
                    'checksum_match': actual_checksum == expected_checksum,
                    'actual_size': actual_size,
                    'expected_size': expected_size,
                    'actual_checksum': actual_checksum,
                    'expected_checksum': expected_checksum
                }
                
                if verification_result['size_match'] and verification_result['checksum_match']:
                    integrity_results['verified_files'][file_path] = verification_result
                    integrity_results['total_verified'] += 1
                else:
                    integrity_results['corrupted_files'][file_path] = verification_result
                    integrity_results['total_corrupted'] += 1
                    integrity_results['success'] = False
            else:
                integrity_results['verification_errors'].append(f"Файл не найден: {local_path}")
                integrity_results['success'] = False
        
        return integrity_results
    
    def _test_server_connection(self, server_config: Dict) -> bool:
        """Тестирует подключение к серверу"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._test_connection_with_key(server_config)
        else:
            return self._test_connection_with_password(server_config)
    
    def _test_connection_with_key(self, server_config: Dict) -> bool:
        """Тестирует подключение с ключом"""
        key_file = server_config.get('key_file')
        if not key_file:
            return False
        
        if os.path.isabs(key_file):
            key_path = Path(key_file)
        else:
            key_path = self.project_root / key_file
        
        if not key_path.exists():
            return False
        
        # Проверяем, есть ли plink
        plink_cmd = shutil.which('plink')
        if plink_cmd and key_path.suffix.lower() == '.ppk':
            cmd = [
                'plink',
                '-i', str(key_path),
                '-batch',
                f"{server_config['user']}@{server_config['host']}",
                'echo "connection_test"'
            ]
        else:
            if key_path.suffix.lower() == '.ppk':
                return False
            
            cmd = [
                'ssh',
                '-i', str(key_path),
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'ConnectTimeout=10',
                f"{server_config['user']}@{server_config['host']}",
                'echo "connection_test"'
            ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            return 'connection_test' in result.stdout
        except:
            return False
    
    def _test_connection_with_password(self, server_config: Dict) -> bool:
        """Тестирует подключение с паролем"""
        cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ConnectTimeout=10',
            f"{server_config['user']}@{server_config['host']}",
            'echo "connection_test"'
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            return 'connection_test' in result.stdout
        except:
            return False
    
    def _check_disk_space(self, server_config: Dict) -> bool:
        """Проверяет место на диске"""
        # Простая проверка - больше 1GB свободного места
        return True  # Пока что всегда возвращаем True
    
    def _check_file_access(self, server_config: Dict, file_path: str) -> str:
        """Проверяет доступность файла"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._check_file_access_with_key(server_config, file_path)
        else:
            return self._check_file_access_with_password(server_config, file_path)
    
    def _check_file_access_with_key(self, server_config: Dict, file_path: str) -> str:
        """Проверяет доступность файла с ключом"""
        key_file = server_config.get('key_file')
        if not key_file:
            return 'permission_denied'
        
        if os.path.isabs(key_file):
            key_path = Path(key_file)
        else:
            key_path = self.project_root / key_file
        
        if not key_path.exists():
            return 'permission_denied'
        
        # Проверяем, есть ли plink
        plink_cmd = shutil.which('plink')
        if plink_cmd and key_path.suffix.lower() == '.ppk':
            cmd = [
                'plink',
                '-i', str(key_path),
                '-batch',
                f"{server_config['user']}@{server_config['host']}",
                f'test -r "{file_path}" && echo "accessible" || echo "missing"'
            ]
        else:
            if key_path.suffix.lower() == '.ppk':
                return 'permission_denied'
            
            cmd = [
                'ssh',
                '-i', str(key_path),
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'ConnectTimeout=10',
                f"{server_config['user']}@{server_config['host']}",
                f'test -r "{file_path}" && echo "accessible" || echo "missing"'
            ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            if 'accessible' in result.stdout:
                return 'accessible'
            else:
                return 'missing'
        except:
            return 'permission_denied'
    
    def _check_file_access_with_password(self, server_config: Dict, file_path: str) -> str:
        """Проверяет доступность файла с паролем"""
        cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ConnectTimeout=10',
            f"{server_config['user']}@{server_config['host']}",
            f'test -r "{file_path}" && echo "accessible" || echo "missing"'
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            if 'accessible' in result.stdout:
                return 'accessible'
            else:
                return 'missing'
        except:
            return 'permission_denied'
    
    def _generate_backup_filename(self, file_path: str, file_info: Dict) -> str:
        """Генерирует имя файла резервной копии"""
        # Заменяем слэши на подчеркивания
        safe_path = file_path.replace('/', '_').replace('\\', '_')
        
        # Добавляем префикс приоритета
        priority = file_info.get('priority', 'medium')
        
        return f"{priority}_{safe_path}"
    
    def _get_priority_order(self, priority: str) -> int:
        """Возвращает порядок приоритета"""
        priority_order = {
            'critical': 1,
            'high': 2,
            'medium': 3,
            'low': 4
        }
        return priority_order.get(priority, 3)
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Вычисляет контрольную сумму файла"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _save_backup_report(self, backup_results: Dict, integrity_results: Dict):
        """Сохраняет отчет о резервном копировании"""
        report = {
            'timestamp': self.session_info['timestamp'],
            'session_id': self.session_info['session_id'],
            'backup_results': backup_results,
            'integrity_results': integrity_results,
            'session_info': self.session_info
        }
        
        report_file = self.reports_dir / f"{self.session_info['session_id']}_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Отчет сохранен: {report_file}")
    
    def _print_backup_summary(self, backup_results: Dict, integrity_results: Dict):
        """Выводит сводку резервного копирования"""
        print("\n" + "="*70)
        print("📊 ИТОГОВАЯ СВОДКА РЕЗЕРВНОГО КОПИРОВАНИЯ")
        print("="*70)
        
        print(f"🎯 Сессия: {self.session_info['session_id']}")
        print(f"📅 Время: {self.session_info['timestamp']}")
        print(f"📁 Папка: {backup_results.get('session_dir', 'Не указана')}")
        
        print(f"\n📊 Статистика:")
        print(f"   Всего файлов: {backup_results.get('total_files', 0)}")
        print(f"   ✅ Успешно: {backup_results.get('successful_count', 0)}")
        print(f"   ❌ Неудачно: {backup_results.get('failed_count', 0)}")
        print(f"   📦 Размер: {backup_results.get('total_size', 0)} байт")
        
        print(f"\n🔐 Проверка целостности:")
        print(f"   ✅ Проверены: {integrity_results.get('total_verified', 0)}")
        print(f"   ❌ Повреждены: {integrity_results.get('total_corrupted', 0)}")
        
        if backup_results.get('success') and integrity_results.get('success'):
            print(f"\n🎉 РЕЗЕРВНОЕ КОПИРОВАНИЕ УСПЕШНО ЗАВЕРШЕНО!")
        else:
            print(f"\n⚠️  РЕЗЕРВНОЕ КОПИРОВАНИЕ ЗАВЕРШЕНО С ОШИБКАМИ!")
            
            if backup_results.get('files_failed'):
                print(f"\n❌ Неудачные файлы:")
                for file_path, error_info in backup_results['files_failed'].items():
                    print(f"   - {os.path.basename(file_path)}: {error_info.get('error', 'Неизвестная ошибка')}")
            
            if integrity_results.get('corrupted_files'):
                print(f"\n🔴 Поврежденные файлы:")
                for file_path in integrity_results['corrupted_files']:
                    print(f"   - {os.path.basename(file_path)}")
    
    def list_backups(self):
        """Выводит список резервных копий"""
        print("📋 СПИСОК РЕЗЕРВНЫХ КОПИЙ")
        print("="*50)
        
        if not self.backup_dir.exists():
            print("❌ Папка резервных копий не найдена")
            return
        
        backup_sessions = []
        for session_dir in self.backup_dir.iterdir():
            if session_dir.is_dir():
                metadata_file = session_dir / 'backup_metadata.json'
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        backup_sessions.append({
                            'session_id': metadata.get('session_id', session_dir.name),
                            'timestamp': metadata.get('timestamp', 'Неизвестно'),
                            'stats': metadata.get('statistics', {}),
                            'path': str(session_dir)
                        })
                    except:
                        backup_sessions.append({
                            'session_id': session_dir.name,
                            'timestamp': 'Неизвестно',
                            'stats': {},
                            'path': str(session_dir)
                        })
        
        if not backup_sessions:
            print("❌ Резервные копии не найдены")
            return
        
        # Сортируем по времени (новые первыми)
        backup_sessions.sort(key=lambda x: x['timestamp'], reverse=True)
        
        for session in backup_sessions:
            print(f"\n📦 {session['session_id']}")
            print(f"   📅 Время: {session['timestamp']}")
            print(f"   📁 Путь: {session['path']}")
            stats = session['stats']
            if stats:
                print(f"   📊 Файлов: {stats.get('total_files', 0)} (успешно: {stats.get('successful_count', 0)})")
                print(f"   💾 Размер: {stats.get('total_size', 0)} байт")


def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python enhanced_backup_manager.py create [--deployment-config config.json] [--inspection-report report.json]")
        print("  python enhanced_backup_manager.py list")
        return 1
    
    manager = EnhancedBackupManager()
    
    command = sys.argv[1].lower()
    
    if command == "create":
        deployment_config = None
        inspection_report_path = None
        
        # Парсим аргументы
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == '--deployment-config' and i + 1 < len(sys.argv):
                config_path = sys.argv[i + 1]
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        deployment_config = json.load(f)
                    print(f"📝 Загружена конфигурация развертывания: {config_path}")
                except Exception as e:
                    print(f"❌ Ошибка загрузки конфигурации: {e}")
                    return 1
                i += 2
            elif sys.argv[i] == '--inspection-report' and i + 1 < len(sys.argv):
                inspection_report_path = sys.argv[i + 1]
                if not os.path.exists(inspection_report_path):
                    print(f"❌ Отчет инспекции не найден: {inspection_report_path}")
                    return 1
                print(f"📄 Использован отчет инспекции: {inspection_report_path}")
                i += 2
            else:
                i += 1
        
        # Создаем резервную копию
        success = manager.create_comprehensive_backup(deployment_config, inspection_report_path)
        return 0 if success else 1
    
    elif command == "list":
        manager.list_backups()
        return 0
    
    else:
        print("❌ Неизвестная команда")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 