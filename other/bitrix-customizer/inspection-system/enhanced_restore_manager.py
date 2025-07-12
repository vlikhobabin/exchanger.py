#!/usr/bin/env python3
"""
Улучшенная система восстановления для Bitrix24
Обеспечивает безопасное восстановление файлов с проверкой целостности
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


class EnhancedRestoreManager:
    """Улучшенная система восстановления с проверкой целостности и валидацией"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.backup_dir = self.project_root / "backups"
        self.config_file = self.project_root / "config.json"
        self.reports_dir = self.project_root / "reports"
        
        # Создаем необходимые директории
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_info = {
            'timestamp': datetime.datetime.now().isoformat(),
            'session_id': self._generate_session_id(),
            'restore_type': 'unknown',
            'backup_session_id': None,
            'files_restored': {},
            'files_failed': {},
            'validation_results': {},
            'errors': [],
            'warnings': []
        }
        
    def _generate_session_id(self) -> str:
        """Генерирует уникальный ID сессии восстановления"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"restore_session_{timestamp}"
    
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
    
    def full_system_restore(self, backup_session_id: str) -> bool:
        """Выполняет полное восстановление системы"""
        print("🔄 ПОЛНОЕ ВОССТАНОВЛЕНИЕ СИСТЕМЫ BITRIX24")
        print("="*70)
        
        self.session_info['restore_type'] = 'full_system'
        self.session_info['backup_session_id'] = backup_session_id
        
        # Загружаем конфигурацию
        config = self.load_config()
        if not config:
            return False
        
        server_config = config['server']
        print(f"🎯 Сервер: {server_config['user']}@{server_config['host']}")
        print(f"🔐 Аутентификация: {server_config.get('auth_method', 'password')}")
        print(f"📦 Сессия резервной копии: {backup_session_id}")
        print("-" * 70)
        
        # Этап 1: Загрузка и проверка резервной копии
        print("\n📊 ЭТАП 1: ЗАГРУЗКА РЕЗЕРВНОЙ КОПИИ")
        print("-" * 40)
        
        backup_info = self._load_backup_metadata(backup_session_id)
        if not backup_info:
            print("❌ Не удалось загрузить информацию о резервной копии")
            return False
        
        print(f"✅ Загружена информация о резервной копии")
        print(f"   📅 Дата создания: {backup_info.get('timestamp', 'Неизвестно')}")
        print(f"   📁 Файлов: {len(backup_info.get('files_backed_up', {}))}")
        
        # Этап 2: Предварительная проверка
        print("\n🔍 ЭТАП 2: ПРЕДВАРИТЕЛЬНАЯ ПРОВЕРКА")
        print("-" * 40)
        
        pre_check_results = self._pre_restore_validation(server_config, backup_info)
        if not pre_check_results['success']:
            print("❌ Предварительная проверка не пройдена")
            return False
        
        print("✅ Предварительная проверка пройдена")
        
        # Этап 3: Создание точки восстановления
        print("\n💾 ЭТАП 3: СОЗДАНИЕ ТОЧКИ ВОССТАНОВЛЕНИЯ")
        print("-" * 40)
        
        recovery_point = self._create_recovery_point(server_config, backup_info)
        if not recovery_point['success']:
            print("❌ Не удалось создать точку восстановления")
            return False
        
        print("✅ Точка восстановления создана")
        
        # Этап 4: Восстановление файлов
        print("\n🔄 ЭТАП 4: ВОССТАНОВЛЕНИЕ ФАЙЛОВ")
        print("-" * 40)
        
        restore_results = self._perform_restore(server_config, backup_info, recovery_point)
        
        # Этап 5: Проверка восстановления
        print("\n✅ ЭТАП 5: ПРОВЕРКА ВОССТАНОВЛЕНИЯ")
        print("-" * 40)
        
        verification_results = self._verify_restore(server_config, backup_info, restore_results)
        
        # Этап 6: Сохранение отчета
        print("\n📄 ЭТАП 6: СОХРАНЕНИЕ ОТЧЕТА")
        print("-" * 40)
        
        self._save_restore_report(restore_results, verification_results, recovery_point)
        
        # Финальная сводка
        self._print_restore_summary(restore_results, verification_results)
        
        return restore_results['success'] and verification_results['success']
    
    def selective_restore(self, backup_session_id: str, files_to_restore: List[str]) -> bool:
        """Выполняет селективное восстановление указанных файлов"""
        print("🔄 СЕЛЕКТИВНОЕ ВОССТАНОВЛЕНИЕ ФАЙЛОВ")
        print("="*70)
        
        self.session_info['restore_type'] = 'selective'
        self.session_info['backup_session_id'] = backup_session_id
        
        # Загружаем конфигурацию
        config = self.load_config()
        if not config:
            return False
        
        server_config = config['server']
        print(f"🎯 Сервер: {server_config['user']}@{server_config['host']}")
        print(f"📦 Сессия резервной копии: {backup_session_id}")
        print(f"📁 Файлов для восстановления: {len(files_to_restore)}")
        print("-" * 70)
        
        # Загружаем информацию о резервной копии
        backup_info = self._load_backup_metadata(backup_session_id)
        if not backup_info:
            return False
        
        # Фильтруем файлы для восстановления
        available_files = backup_info.get('files_backed_up', {})
        filtered_files = {}
        
        for file_path in files_to_restore:
            if file_path in available_files:
                filtered_files[file_path] = available_files[file_path]
            else:
                print(f"⚠️  Файл не найден в резервной копии: {file_path}")
                self.session_info['warnings'].append(f"Файл не найден в резервной копии: {file_path}")
        
        if not filtered_files:
            print("❌ Нет доступных файлов для восстановления")
            return False
        
        # Создаем временную информацию о резервной копии
        temp_backup_info = backup_info.copy()
        temp_backup_info['files_backed_up'] = filtered_files
        
        # Выполняем восстановление
        restore_results = self._perform_restore(server_config, temp_backup_info, None)
        verification_results = self._verify_restore(server_config, temp_backup_info, restore_results)
        
        self._save_restore_report(restore_results, verification_results, None)
        self._print_restore_summary(restore_results, verification_results)
        
        return restore_results['success'] and verification_results['success']
    
    def emergency_restore(self, backup_session_id: str) -> bool:
        """Выполняет экстренное восстановление без дополнительных проверок"""
        print("🚨 ЭКСТРЕННОЕ ВОССТАНОВЛЕНИЕ СИСТЕМЫ")
        print("="*70)
        print("⚠️  ВНИМАНИЕ: Экстренное восстановление пропускает некоторые проверки!")
        print("⚠️  Используйте только в критических ситуациях!")
        print("-" * 70)
        
        self.session_info['restore_type'] = 'emergency'
        self.session_info['backup_session_id'] = backup_session_id
        
        # Загружаем конфигурацию
        config = self.load_config()
        if not config:
            return False
        
        server_config = config['server']
        
        # Загружаем информацию о резервной копии
        backup_info = self._load_backup_metadata(backup_session_id)
        if not backup_info:
            return False
        
        # Минимальная проверка доступности сервера
        if not self._test_server_connection(server_config):
            print("❌ Сервер недоступен")
            return False
        
        # Экстренное восстановление
        restore_results = self._perform_emergency_restore(server_config, backup_info)
        
        # Минимальная проверка
        verification_results = self._minimal_verification(server_config, restore_results)
        
        self._save_restore_report(restore_results, verification_results, None)
        self._print_restore_summary(restore_results, verification_results)
        
        return restore_results['success']
    
    def _load_backup_metadata(self, backup_session_id: str) -> Optional[Dict]:
        """Загружает метаданные резервной копии"""
        backup_session_dir = self.backup_dir / backup_session_id
        
        if not backup_session_dir.exists():
            self.session_info['errors'].append(f"Папка резервной копии не найдена: {backup_session_dir}")
            return None
        
        metadata_file = backup_session_dir / 'backup_metadata.json'
        if not metadata_file.exists():
            self.session_info['errors'].append(f"Файл метаданных не найден: {metadata_file}")
            return None
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            return metadata
        except Exception as e:
            self.session_info['errors'].append(f"Ошибка загрузки метаданных: {e}")
            return None
    
    def _pre_restore_validation(self, server_config: Dict, backup_info: Dict) -> Dict:
        """Выполняет предварительную проверку перед восстановлением"""
        validation_results = {
            'success': True,
            'server_accessible': False,
            'backup_integrity_ok': False,
            'target_paths_accessible': False,
            'conflicts_detected': [],
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
        
        # Проверка целостности резервной копии
        print("🔐 Проверка целостности резервной копии...")
        backup_integrity = self._check_backup_integrity(backup_info)
        if backup_integrity['success']:
            validation_results['backup_integrity_ok'] = True
            print("✅ Резервная копия целостна")
        else:
            validation_results['success'] = False
            print("❌ Резервная копия повреждена")
            print(f"   Поврежденные файлы: {len(backup_integrity.get('corrupted_files', []))}")
            return validation_results
        
        # Проверка доступности целевых путей
        print("📁 Проверка доступности целевых путей...")
        target_paths_check = self._check_target_paths(server_config, backup_info)
        if target_paths_check['success']:
            validation_results['target_paths_accessible'] = True
            print("✅ Целевые пути доступны")
        else:
            validation_results['warnings'].append("Некоторые целевые пути недоступны")
            print("⚠️  Некоторые целевые пути недоступны")
        
        # Проверка конфликтов
        print("⚠️  Проверка конфликтов...")
        conflicts = self._detect_conflicts(server_config, backup_info)
        if conflicts:
            validation_results['conflicts_detected'] = conflicts
            print(f"⚠️  Обнаружены конфликты: {len(conflicts)}")
            for conflict in conflicts[:3]:  # Показываем первые 3
                print(f"   - {conflict}")
        else:
            print("✅ Конфликты не обнаружены")
        
        return validation_results
    
    def _create_recovery_point(self, server_config: Dict, backup_info: Dict) -> Dict:
        """Создает точку восстановления текущего состояния"""
        recovery_point = {
            'success': False,
            'timestamp': datetime.datetime.now().isoformat(),
            'recovery_point_id': f"recovery_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'files_saved': {},
            'files_failed': {},
            'recovery_dir': None
        }
        
        # Создаем папку для точки восстановления
        recovery_dir = self.backup_dir / recovery_point['recovery_point_id']
        recovery_dir.mkdir(parents=True, exist_ok=True)
        recovery_point['recovery_dir'] = str(recovery_dir)
        
        print(f"💾 Создание точки восстановления: {recovery_point['recovery_point_id']}")
        
        # Сохраняем текущее состояние файлов, которые будут восстановлены
        files_to_backup = backup_info.get('files_backed_up', {})
        
        for file_path, file_info in files_to_backup.items():
            print(f"📥 Сохранение текущего состояния: {os.path.basename(file_path)}")
            
            # Создаем имя файла для точки восстановления
            recovery_filename = f"current_{os.path.basename(file_path)}"
            recovery_file_path = recovery_dir / recovery_filename
            
            # Копируем текущий файл с сервера
            if self._copy_file_from_server(server_config, file_path, recovery_file_path):
                recovery_point['files_saved'][file_path] = {
                    'recovery_path': str(recovery_file_path),
                    'size': recovery_file_path.stat().st_size if recovery_file_path.exists() else 0,
                    'checksum': self._calculate_file_checksum(recovery_file_path) if recovery_file_path.exists() else None
                }
                print(f"✅ Сохранен: {os.path.basename(file_path)}")
            else:
                recovery_point['files_failed'][file_path] = 'Не удалось скопировать текущий файл'
                print(f"⚠️  Не удалось сохранить: {os.path.basename(file_path)} (файл может не существовать)")
        
        # Сохраняем метаданные точки восстановления
        recovery_metadata = {
            'timestamp': recovery_point['timestamp'],
            'recovery_point_id': recovery_point['recovery_point_id'],
            'restore_session_id': self.session_info['session_id'],
            'backup_session_id': self.session_info['backup_session_id'],
            'files_saved': recovery_point['files_saved'],
            'files_failed': recovery_point['files_failed']
        }
        
        recovery_metadata_file = recovery_dir / 'recovery_metadata.json'
        with open(recovery_metadata_file, 'w', encoding='utf-8') as f:
            json.dump(recovery_metadata, f, indent=2, ensure_ascii=False)
        
        recovery_point['success'] = True
        print(f"✅ Точка восстановления создана: {recovery_point['recovery_point_id']}")
        
        return recovery_point
    
    def _perform_restore(self, server_config: Dict, backup_info: Dict, recovery_point: Optional[Dict]) -> Dict:
        """Выполняет восстановление файлов"""
        restore_results = {
            'success': True,
            'files_restored': {},
            'files_failed': {},
            'total_files': 0,
            'successful_count': 0,
            'failed_count': 0,
            'total_size': 0
        }
        
        files_to_restore = backup_info.get('files_backed_up', {})
        restore_results['total_files'] = len(files_to_restore)
        
        # Загружаем папку резервной копии
        backup_session_dir = self.backup_dir / self.session_info['backup_session_id']
        
        # Сортируем файлы по приоритету (критические файлы восстанавливаем первыми)
        sorted_files = sorted(files_to_restore.items(), 
                            key=lambda x: self._get_restore_priority_order(x[1]))
        
        for file_path, file_info in sorted_files:
            print(f"🔄 Восстановление: {os.path.basename(file_path)}")
            
            # Определяем локальный путь к файлу резервной копии
            backup_file_path = backup_session_dir / file_info['local_path']
            
            if not backup_file_path.exists():
                restore_results['files_failed'][file_path] = 'Файл резервной копии не найден'
                restore_results['failed_count'] += 1
                print(f"❌ Файл резервной копии не найден: {file_info['local_path']}")
                continue
            
            # Восстанавливаем файл
            restore_file_result = self._restore_single_file(server_config, file_path, backup_file_path, file_info)
            
            if restore_file_result['success']:
                restore_results['files_restored'][file_path] = restore_file_result
                restore_results['successful_count'] += 1
                restore_results['total_size'] += restore_file_result.get('size', 0)
                print(f"✅ Восстановлен: {os.path.basename(file_path)}")
            else:
                restore_results['files_failed'][file_path] = restore_file_result
                restore_results['failed_count'] += 1
                print(f"❌ Ошибка восстановления: {os.path.basename(file_path)} - {restore_file_result.get('error', 'Неизвестная ошибка')}")
        
        if restore_results['failed_count'] > 0:
            restore_results['success'] = False
        
        return restore_results
    
    def _perform_emergency_restore(self, server_config: Dict, backup_info: Dict) -> Dict:
        """Выполняет экстренное восстановление с минимальными проверками"""
        restore_results = {
            'success': True,
            'files_restored': {},
            'files_failed': {},
            'total_files': 0,
            'successful_count': 0,
            'failed_count': 0,
            'emergency_mode': True
        }
        
        files_to_restore = backup_info.get('files_backed_up', {})
        restore_results['total_files'] = len(files_to_restore)
        
        backup_session_dir = self.backup_dir / self.session_info['backup_session_id']
        
        # В экстренном режиме восстанавливаем все файлы без дополнительных проверок
        for file_path, file_info in files_to_restore.items():
            print(f"🚨 Экстренное восстановление: {os.path.basename(file_path)}")
            
            backup_file_path = backup_session_dir / file_info['local_path']
            
            if backup_file_path.exists():
                # Прямое копирование без проверок
                if self._copy_file_to_server(server_config, backup_file_path, file_path):
                    restore_results['files_restored'][file_path] = {
                        'success': True,
                        'emergency_mode': True,
                        'size': backup_file_path.stat().st_size
                    }
                    restore_results['successful_count'] += 1
                    print(f"✅ Восстановлен: {os.path.basename(file_path)}")
                else:
                    restore_results['files_failed'][file_path] = 'Ошибка копирования'
                    restore_results['failed_count'] += 1
                    print(f"❌ Ошибка: {os.path.basename(file_path)}")
            else:
                restore_results['files_failed'][file_path] = 'Файл резервной копии не найден'
                restore_results['failed_count'] += 1
                print(f"❌ Файл не найден: {os.path.basename(file_path)}")
        
        if restore_results['failed_count'] > 0:
            restore_results['success'] = False
        
        return restore_results
    
    def _restore_single_file(self, server_config: Dict, remote_path: str, backup_file_path: Path, file_info: Dict) -> Dict:
        """Восстанавливает один файл"""
        result = {
            'success': False,
            'remote_path': remote_path,
            'backup_file_path': str(backup_file_path),
            'file_info': file_info,
            'size': 0,
            'checksum': None,
            'error': None
        }
        
        try:
            # Проверяем целостность файла резервной копии
            backup_checksum = self._calculate_file_checksum(backup_file_path)
            expected_checksum = file_info.get('checksum')
            
            if expected_checksum and backup_checksum != expected_checksum:
                result['error'] = 'Контрольная сумма файла резервной копии не совпадает'
                return result
            
            # Создаем директорию на сервере при необходимости
            remote_dir = os.path.dirname(remote_path)
            if not self._ensure_remote_directory(server_config, remote_dir):
                result['error'] = 'Не удалось создать директорию на сервере'
                return result
            
            # Копируем файл на сервер
            if self._copy_file_to_server(server_config, backup_file_path, remote_path):
                result['success'] = True
                result['size'] = backup_file_path.stat().st_size
                result['checksum'] = backup_checksum
            else:
                result['error'] = 'Ошибка при копировании файла на сервер'
                
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def _copy_file_from_server(self, server_config: Dict, remote_path: str, local_path: Path) -> bool:
        """Копирует файл с сервера"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._copy_from_server_with_key(server_config, remote_path, local_path)
        else:
            return self._copy_from_server_with_password(server_config, remote_path, local_path)
    
    def _copy_file_to_server(self, server_config: Dict, local_path: Path, remote_path: str) -> bool:
        """Копирует файл на сервер"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._copy_to_server_with_key(server_config, local_path, remote_path)
        else:
            return self._copy_to_server_with_password(server_config, local_path, remote_path)
    
    def _copy_from_server_with_key(self, server_config: Dict, remote_path: str, local_path: Path) -> bool:
        """Копирует файл с сервера с использованием ключа"""
        key_file = server_config.get('key_file')
        if not key_file:
            return False
        
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
        except:
            return False
    
    def _copy_from_server_with_password(self, server_config: Dict, remote_path: str, local_path: Path) -> bool:
        """Копирует файл с сервера с использованием пароля"""
        cmd = [
            "scp",
            "-o", "StrictHostKeyChecking=no",
            f"{server_config['user']}@{server_config['host']}:{remote_path}",
            str(local_path)
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
            return True
        except:
            return False
    
    def _copy_to_server_with_key(self, server_config: Dict, local_path: Path, remote_path: str) -> bool:
        """Копирует файл на сервер с использованием ключа"""
        key_file = server_config.get('key_file')
        if not key_file:
            return False
        
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
                str(local_path),
                f"{server_config['user']}@{server_config['host']}:{remote_path}"
            ]
        else:
            if key_path.suffix.lower() == '.ppk':
                return False
            
            cmd = [
                "scp",
                "-i", str(key_path),
                "-o", "StrictHostKeyChecking=no",
                str(local_path),
                f"{server_config['user']}@{server_config['host']}:{remote_path}"
            ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
            return True
        except:
            return False
    
    def _copy_to_server_with_password(self, server_config: Dict, local_path: Path, remote_path: str) -> bool:
        """Копирует файл на сервер с использованием пароля"""
        cmd = [
            "scp",
            "-o", "StrictHostKeyChecking=no",
            str(local_path),
            f"{server_config['user']}@{server_config['host']}:{remote_path}"
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
            return True
        except:
            return False
    
    def _ensure_remote_directory(self, server_config: Dict, remote_dir: str) -> bool:
        """Создает директорию на сервере при необходимости"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._ensure_remote_directory_with_key(server_config, remote_dir)
        else:
            return self._ensure_remote_directory_with_password(server_config, remote_dir)
    
    def _ensure_remote_directory_with_key(self, server_config: Dict, remote_dir: str) -> bool:
        """Создает директорию на сервере с использованием ключа"""
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
                f'mkdir -p "{remote_dir}"'
            ]
        else:
            if key_path.suffix.lower() == '.ppk':
                return False
            
            cmd = [
                'ssh',
                '-i', str(key_path),
                '-o', 'StrictHostKeyChecking=no',
                f"{server_config['user']}@{server_config['host']}",
                f'mkdir -p "{remote_dir}"'
            ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
            return True
        except:
            return False
    
    def _ensure_remote_directory_with_password(self, server_config: Dict, remote_dir: str) -> bool:
        """Создает директорию на сервере с использованием пароля"""
        cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            f"{server_config['user']}@{server_config['host']}",
            f'mkdir -p "{remote_dir}"'
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
            return True
        except:
            return False
    
    def _verify_restore(self, server_config: Dict, backup_info: Dict, restore_results: Dict) -> Dict:
        """Проверяет результаты восстановления"""
        verification_results = {
            'success': True,
            'files_verified': {},
            'files_failed_verification': {},
            'total_verified': 0,
            'total_failed': 0,
            'verification_errors': []
        }
        
        print("🔍 Проверка результатов восстановления...")
        
        for file_path, restore_info in restore_results.get('files_restored', {}).items():
            print(f"✅ Проверка: {os.path.basename(file_path)}")
            
            # Проверяем файл на сервере
            verification_result = self._verify_remote_file(server_config, file_path, restore_info)
            
            if verification_result['success']:
                verification_results['files_verified'][file_path] = verification_result
                verification_results['total_verified'] += 1
                print(f"✅ Проверен: {os.path.basename(file_path)}")
            else:
                verification_results['files_failed_verification'][file_path] = verification_result
                verification_results['total_failed'] += 1
                verification_results['success'] = False
                print(f"❌ Ошибка проверки: {os.path.basename(file_path)} - {verification_result.get('error', 'Неизвестная ошибка')}")
        
        return verification_results
    
    def _minimal_verification(self, server_config: Dict, restore_results: Dict) -> Dict:
        """Выполняет минимальную проверку для экстренного восстановления"""
        verification_results = {
            'success': True,
            'files_verified': {},
            'total_verified': 0,
            'minimal_check': True
        }
        
        # Проверяем только существование файлов
        for file_path in restore_results.get('files_restored', {}).keys():
            if self._check_file_exists_on_server(server_config, file_path):
                verification_results['files_verified'][file_path] = {'exists': True}
                verification_results['total_verified'] += 1
            else:
                verification_results['success'] = False
        
        return verification_results
    
    def _verify_remote_file(self, server_config: Dict, file_path: str, restore_info: Dict) -> Dict:
        """Проверяет файл на сервере"""
        verification_result = {
            'success': False,
            'file_path': file_path,
            'exists': False,
            'size_match': False,
            'permissions_ok': False,
            'error': None
        }
        
        try:
            # Проверяем существование файла
            if not self._check_file_exists_on_server(server_config, file_path):
                verification_result['error'] = 'Файл не найден на сервере'
                return verification_result
            
            verification_result['exists'] = True
            
            # Проверяем размер файла
            remote_size = self._get_remote_file_size(server_config, file_path)
            expected_size = restore_info.get('size', 0)
            
            if remote_size == expected_size:
                verification_result['size_match'] = True
            else:
                verification_result['error'] = f'Размер не совпадает: {remote_size} != {expected_size}'
                return verification_result
            
            # Проверяем права доступа
            if self._check_file_permissions(server_config, file_path):
                verification_result['permissions_ok'] = True
            else:
                verification_result['error'] = 'Неверные права доступа'
                return verification_result
            
            verification_result['success'] = True
            
        except Exception as e:
            verification_result['error'] = str(e)
        
        return verification_result
    
    def _check_backup_integrity(self, backup_info: Dict) -> Dict:
        """Проверяет целостность резервной копии"""
        integrity_results = {
            'success': True,
            'total_files': 0,
            'verified_files': 0,
            'corrupted_files': [],
            'missing_files': []
        }
        
        backup_session_dir = self.backup_dir / self.session_info['backup_session_id']
        files_backed_up = backup_info.get('files_backed_up', {})
        
        integrity_results['total_files'] = len(files_backed_up)
        
        for file_path, file_info in files_backed_up.items():
            backup_file_path = backup_session_dir / file_info['local_path']
            
            if not backup_file_path.exists():
                integrity_results['missing_files'].append(file_path)
                continue
            
            # Проверяем контрольную сумму
            actual_checksum = self._calculate_file_checksum(backup_file_path)
            expected_checksum = file_info.get('checksum')
            
            if expected_checksum and actual_checksum != expected_checksum:
                integrity_results['corrupted_files'].append(file_path)
                continue
            
            integrity_results['verified_files'] += 1
        
        if integrity_results['missing_files'] or integrity_results['corrupted_files']:
            integrity_results['success'] = False
        
        return integrity_results
    
    def _check_target_paths(self, server_config: Dict, backup_info: Dict) -> Dict:
        """Проверяет доступность целевых путей"""
        target_paths_results = {
            'success': True,
            'accessible_paths': [],
            'inaccessible_paths': []
        }
        
        files_backed_up = backup_info.get('files_backed_up', {})
        
        for file_path in files_backed_up.keys():
            target_dir = os.path.dirname(file_path)
            
            if self._check_directory_writable(server_config, target_dir):
                target_paths_results['accessible_paths'].append(target_dir)
            else:
                target_paths_results['inaccessible_paths'].append(target_dir)
        
        if target_paths_results['inaccessible_paths']:
            target_paths_results['success'] = False
        
        return target_paths_results
    
    def _detect_conflicts(self, server_config: Dict, backup_info: Dict) -> List[str]:
        """Обнаруживает конфликты при восстановлении"""
        conflicts = []
        
        files_backed_up = backup_info.get('files_backed_up', {})
        
        for file_path in files_backed_up.keys():
            # Проверяем, существует ли файл на сервере
            if self._check_file_exists_on_server(server_config, file_path):
                # Проверяем, изменился ли файл с момента резервного копирования
                current_size = self._get_remote_file_size(server_config, file_path)
                backup_size = files_backed_up[file_path].get('size', 0)
                
                if current_size != backup_size:
                    conflicts.append(f"Файл изменен: {file_path} ({current_size} != {backup_size} байт)")
        
        return conflicts
    
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
    
    def _check_file_exists_on_server(self, server_config: Dict, file_path: str) -> bool:
        """Проверяет существование файла на сервере"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._check_file_exists_with_key(server_config, file_path)
        else:
            return self._check_file_exists_with_password(server_config, file_path)
    
    def _check_file_exists_with_key(self, server_config: Dict, file_path: str) -> bool:
        """Проверяет существование файла с ключом"""
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
                f'test -f "{file_path}" && echo "exists"'
            ]
        else:
            if key_path.suffix.lower() == '.ppk':
                return False
            
            cmd = [
                'ssh',
                '-i', str(key_path),
                '-o', 'StrictHostKeyChecking=no',
                f"{server_config['user']}@{server_config['host']}",
                f'test -f "{file_path}" && echo "exists"'
            ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            return 'exists' in result.stdout
        except:
            return False
    
    def _check_file_exists_with_password(self, server_config: Dict, file_path: str) -> bool:
        """Проверяет существование файла с паролем"""
        cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            f"{server_config['user']}@{server_config['host']}",
            f'test -f "{file_path}" && echo "exists"'
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            return 'exists' in result.stdout
        except:
            return False
    
    def _get_remote_file_size(self, server_config: Dict, file_path: str) -> int:
        """Получает размер файла на сервере"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._get_remote_file_size_with_key(server_config, file_path)
        else:
            return self._get_remote_file_size_with_password(server_config, file_path)
    
    def _get_remote_file_size_with_key(self, server_config: Dict, file_path: str) -> int:
        """Получает размер файла с ключом"""
        key_file = server_config.get('key_file')
        if not key_file:
            return 0
        
        if os.path.isabs(key_file):
            key_path = Path(key_file)
        else:
            key_path = self.project_root / key_file
        
        if not key_path.exists():
            return 0
        
        # Проверяем, есть ли plink
        plink_cmd = shutil.which('plink')
        if plink_cmd and key_path.suffix.lower() == '.ppk':
            cmd = [
                'plink',
                '-i', str(key_path),
                '-batch',
                f"{server_config['user']}@{server_config['host']}",
                f'stat -c%s "{file_path}" 2>/dev/null || echo "0"'
            ]
        else:
            if key_path.suffix.lower() == '.ppk':
                return 0
            
            cmd = [
                'ssh',
                '-i', str(key_path),
                '-o', 'StrictHostKeyChecking=no',
                f"{server_config['user']}@{server_config['host']}",
                f'stat -c%s "{file_path}" 2>/dev/null || echo "0"'
            ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            return int(result.stdout.strip())
        except:
            return 0
    
    def _get_remote_file_size_with_password(self, server_config: Dict, file_path: str) -> int:
        """Получает размер файла с паролем"""
        cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            f"{server_config['user']}@{server_config['host']}",
            f'stat -c%s "{file_path}" 2>/dev/null || echo "0"'
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            return int(result.stdout.strip())
        except:
            return 0
    
    def _check_file_permissions(self, server_config: Dict, file_path: str) -> bool:
        """Проверяет права доступа к файлу"""
        # Простая проверка - файл доступен для чтения
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._check_file_permissions_with_key(server_config, file_path)
        else:
            return self._check_file_permissions_with_password(server_config, file_path)
    
    def _check_file_permissions_with_key(self, server_config: Dict, file_path: str) -> bool:
        """Проверяет права доступа с ключом"""
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
                f'test -r "{file_path}" && echo "readable"'
            ]
        else:
            if key_path.suffix.lower() == '.ppk':
                return False
            
            cmd = [
                'ssh',
                '-i', str(key_path),
                '-o', 'StrictHostKeyChecking=no',
                f"{server_config['user']}@{server_config['host']}",
                f'test -r "{file_path}" && echo "readable"'
            ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            return 'readable' in result.stdout
        except:
            return False
    
    def _check_file_permissions_with_password(self, server_config: Dict, file_path: str) -> bool:
        """Проверяет права доступа с паролем"""
        cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            f"{server_config['user']}@{server_config['host']}",
            f'test -r "{file_path}" && echo "readable"'
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            return 'readable' in result.stdout
        except:
            return False
    
    def _check_directory_writable(self, server_config: Dict, directory_path: str) -> bool:
        """Проверяет, можно ли записывать в директорию"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._check_directory_writable_with_key(server_config, directory_path)
        else:
            return self._check_directory_writable_with_password(server_config, directory_path)
    
    def _check_directory_writable_with_key(self, server_config: Dict, directory_path: str) -> bool:
        """Проверяет запись в директорию с ключом"""
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
                f'test -w "{directory_path}" && echo "writable"'
            ]
        else:
            if key_path.suffix.lower() == '.ppk':
                return False
            
            cmd = [
                'ssh',
                '-i', str(key_path),
                '-o', 'StrictHostKeyChecking=no',
                f"{server_config['user']}@{server_config['host']}",
                f'test -w "{directory_path}" && echo "writable"'
            ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            return 'writable' in result.stdout
        except:
            return False
    
    def _check_directory_writable_with_password(self, server_config: Dict, directory_path: str) -> bool:
        """Проверяет запись в директорию с паролем"""
        cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            f"{server_config['user']}@{server_config['host']}",
            f'test -w "{directory_path}" && echo "writable"'
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            return 'writable' in result.stdout
        except:
            return False
    
    def _get_restore_priority_order(self, file_info: Dict) -> int:
        """Возвращает порядок приоритета для восстановления"""
        # Критические файлы восстанавливаем первыми
        file_type = file_info.get('file_type', 'unknown')
        
        if file_type == 'init_file':
            return 1
        elif file_type == 'config_file':
            return 2
        elif file_type in ['template_header', 'template_footer']:
            return 3
        elif file_type == 'php_file':
            return 4
        elif file_type in ['javascript', 'stylesheet']:
            return 5
        else:
            return 6
    
    def _calculate_file_checksum(self, file_path: Path) -> str:
        """Вычисляет контрольную сумму файла"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _save_restore_report(self, restore_results: Dict, verification_results: Dict, recovery_point: Optional[Dict]):
        """Сохраняет отчет о восстановлении"""
        report = {
            'timestamp': self.session_info['timestamp'],
            'session_id': self.session_info['session_id'],
            'restore_type': self.session_info['restore_type'],
            'backup_session_id': self.session_info['backup_session_id'],
            'restore_results': restore_results,
            'verification_results': verification_results,
            'recovery_point': recovery_point,
            'session_info': self.session_info
        }
        
        report_file = self.reports_dir / f"{self.session_info['session_id']}_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Отчет о восстановлении сохранен: {report_file}")
    
    def _print_restore_summary(self, restore_results: Dict, verification_results: Dict):
        """Выводит сводку восстановления"""
        print("\n" + "="*70)
        print("📊 ИТОГОВАЯ СВОДКА ВОССТАНОВЛЕНИЯ")
        print("="*70)
        
        print(f"🎯 Сессия: {self.session_info['session_id']}")
        print(f"📦 Резервная копия: {self.session_info['backup_session_id']}")
        print(f"🔄 Тип восстановления: {self.session_info['restore_type']}")
        print(f"📅 Время: {self.session_info['timestamp']}")
        
        print(f"\n📊 Статистика восстановления:")
        print(f"   Всего файлов: {restore_results.get('total_files', 0)}")
        print(f"   ✅ Успешно восстановлено: {restore_results.get('successful_count', 0)}")
        print(f"   ❌ Неудачно: {restore_results.get('failed_count', 0)}")
        print(f"   📦 Размер: {restore_results.get('total_size', 0)} байт")
        
        print(f"\n✅ Статистика проверки:")
        print(f"   ✅ Проверены: {verification_results.get('total_verified', 0)}")
        print(f"   ❌ Не прошли проверку: {verification_results.get('total_failed', 0)}")
        
        if restore_results.get('success') and verification_results.get('success'):
            print(f"\n🎉 ВОССТАНОВЛЕНИЕ УСПЕШНО ЗАВЕРШЕНО!")
        else:
            print(f"\n⚠️  ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО С ОШИБКАМИ!")
            
            if restore_results.get('files_failed'):
                print(f"\n❌ Файлы с ошибками восстановления:")
                for file_path, error_info in restore_results['files_failed'].items():
                    error_msg = error_info.get('error', 'Неизвестная ошибка') if isinstance(error_info, dict) else str(error_info)
                    print(f"   - {os.path.basename(file_path)}: {error_msg}")
            
            if verification_results.get('files_failed_verification'):
                print(f"\n🔴 Файлы с ошибками проверки:")
                for file_path, error_info in verification_results['files_failed_verification'].items():
                    error_msg = error_info.get('error', 'Неизвестная ошибка')
                    print(f"   - {os.path.basename(file_path)}: {error_msg}")
    
    def list_backups(self):
        """Выводит список доступных резервных копий"""
        print("📋 СПИСОК ДОСТУПНЫХ РЕЗЕРВНЫХ КОПИЙ")
        print("="*50)
        
        if not self.backup_dir.exists():
            print("❌ Папка резервных копий не найдена")
            return
        
        backup_sessions = []
        for session_dir in self.backup_dir.iterdir():
            if session_dir.is_dir() and session_dir.name.startswith('backup_session_'):
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
    
    def list_recovery_points(self):
        """Выводит список точек восстановления"""
        print("📋 СПИСОК ТОЧЕК ВОССТАНОВЛЕНИЯ")
        print("="*50)
        
        if not self.backup_dir.exists():
            print("❌ Папка резервных копий не найдена")
            return
        
        recovery_points = []
        for session_dir in self.backup_dir.iterdir():
            if session_dir.is_dir() and session_dir.name.startswith('recovery_'):
                metadata_file = session_dir / 'recovery_metadata.json'
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        recovery_points.append({
                            'recovery_point_id': metadata.get('recovery_point_id', session_dir.name),
                            'timestamp': metadata.get('timestamp', 'Неизвестно'),
                            'restore_session_id': metadata.get('restore_session_id', 'Неизвестно'),
                            'backup_session_id': metadata.get('backup_session_id', 'Неизвестно'),
                            'files_count': len(metadata.get('files_saved', {})),
                            'path': str(session_dir)
                        })
                    except:
                        recovery_points.append({
                            'recovery_point_id': session_dir.name,
                            'timestamp': 'Неизвестно',
                            'restore_session_id': 'Неизвестно',
                            'backup_session_id': 'Неизвестно',
                            'files_count': 0,
                            'path': str(session_dir)
                        })
        
        if not recovery_points:
            print("❌ Точки восстановления не найдены")
            return
        
        # Сортируем по времени (новые первыми)
        recovery_points.sort(key=lambda x: x['timestamp'], reverse=True)
        
        for rp in recovery_points:
            print(f"\n📍 {rp['recovery_point_id']}")
            print(f"   📅 Время: {rp['timestamp']}")
            print(f"   🔄 Сессия восстановления: {rp['restore_session_id']}")
            print(f"   📦 Резервная копия: {rp['backup_session_id']}")
            print(f"   📊 Файлов: {rp['files_count']}")
            print(f"   📁 Путь: {rp['path']}")


def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python enhanced_restore_manager.py full <backup_session_id>")
        print("  python enhanced_restore_manager.py selective <backup_session_id> <file1> [file2] ...")
        print("  python enhanced_restore_manager.py emergency <backup_session_id>")
        print("  python enhanced_restore_manager.py list-backups")
        print("  python enhanced_restore_manager.py list-recovery-points")
        return 1
    
    manager = EnhancedRestoreManager()
    
    command = sys.argv[1].lower()
    
    if command == "full":
        if len(sys.argv) < 3:
            print("❌ Не указан ID сессии резервной копии")
            return 1
        
        backup_session_id = sys.argv[2]
        success = manager.full_system_restore(backup_session_id)
        return 0 if success else 1
    
    elif command == "selective":
        if len(sys.argv) < 4:
            print("❌ Не указан ID сессии резервной копии или файлы для восстановления")
            return 1
        
        backup_session_id = sys.argv[2]
        files_to_restore = sys.argv[3:]
        success = manager.selective_restore(backup_session_id, files_to_restore)
        return 0 if success else 1
    
    elif command == "emergency":
        if len(sys.argv) < 3:
            print("❌ Не указан ID сессии резервной копии")
            return 1
        
        backup_session_id = sys.argv[2]
        success = manager.emergency_restore(backup_session_id)
        return 0 if success else 1
    
    elif command == "list-backups":
        manager.list_backups()
        return 0
    
    elif command == "list-recovery-points":
        manager.list_recovery_points()
        return 0
    
    else:
        print("❌ Неизвестная команда")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 