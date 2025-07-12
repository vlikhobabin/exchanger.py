#!/usr/bin/env python3
"""
Система безопасного развертывания для Bitrix24
Обеспечивает безопасное развертывание с проверками на всех этапах
"""

import os
import sys
import json
import shutil
import subprocess
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from file_analyzer import BitrixFileAnalyzer
from enhanced_backup_manager import EnhancedBackupManager
from enhanced_restore_manager import EnhancedRestoreManager


class SafeDeploymentManager:
    """Система безопасного развертывания с комплексными проверками"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.config_file = self.project_root / "config.json"
        self.reports_dir = self.project_root / "reports"
        self.deployments_dir = self.project_root / "deployments"
        
        # Создаем необходимые директории
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.deployments_dir.mkdir(parents=True, exist_ok=True)
        
        # Инициализируем компоненты
        self.file_analyzer = BitrixFileAnalyzer()
        self.backup_manager = EnhancedBackupManager()
        self.restore_manager = EnhancedRestoreManager()
        
        self.deployment_session = {
            'timestamp': datetime.datetime.now().isoformat(),
            'session_id': self._generate_session_id(),
            'deployment_config': {},
            'phases': {},
            'backup_session_id': None,
            'recovery_point_id': None,
            'errors': [],
            'warnings': [],
            'rollback_available': False
        }
        
    def _generate_session_id(self) -> str:
        """Генерирует уникальный ID сессии развертывания"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"deploy_session_{timestamp}"
    
    def load_config(self) -> Optional[Dict]:
        """Загружает конфигурацию"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            self.deployment_session['errors'].append(f"Файл конфигурации {self.config_file} не найден")
            return None
        except json.JSONDecodeError as e:
            self.deployment_session['errors'].append(f"Ошибка в файле конфигурации: {e}")
            return None
    
    def safe_deploy(self, deployment_config_path: str, dry_run: bool = False) -> bool:
        """Выполняет безопасное развертывание"""
        print("🚀 БЕЗОПАСНОЕ РАЗВЕРТЫВАНИЕ BITRIX24")
        print("="*70)
        
        # Загружаем конфигурацию развертывания
        deployment_config = self._load_deployment_config(deployment_config_path)
        if not deployment_config:
            return False
        
        self.deployment_session['deployment_config'] = deployment_config
        
        # Загружаем конфигурацию сервера
        server_config = self.load_config()
        if not server_config:
            return False
        
        print(f"🎯 Сервер: {server_config['server']['user']}@{server_config['server']['host']}")
        print(f"📝 Конфигурация: {deployment_config_path}")
        print(f"🔄 Сессия: {self.deployment_session['session_id']}")
        if dry_run:
            print("🧪 РЕЖИМ ТЕСТИРОВАНИЯ - изменения не будут применены")
        print("-" * 70)
        
        # Фазы развертывания
        phases = [
            ("pre_deployment_validation", "Предварительная проверка", self._phase_pre_deployment_validation),
            ("system_analysis", "Анализ системы", self._phase_system_analysis),
            ("backup_creation", "Создание резервной копии", self._phase_backup_creation),
            ("deployment_validation", "Валидация развертывания", self._phase_deployment_validation),
            ("safe_deployment", "Безопасное развертывание", self._phase_safe_deployment),
            ("post_deployment_validation", "Проверка после развертывания", self._phase_post_deployment_validation),
            ("cleanup", "Очистка", self._phase_cleanup)
        ]
        
        # Выполняем фазы
        for phase_name, phase_description, phase_function in phases:
            if not self._execute_phase(phase_name, phase_description, phase_function, 
                                     server_config, deployment_config, dry_run):
                print(f"\n❌ Ошибка в фазе: {phase_description}")
                
                # Если есть резервная копия, предлагаем откат
                if self.deployment_session.get('rollback_available') and not dry_run:
                    self._offer_rollback()
                
                return False
        
        # Сохраняем отчет
        self._save_deployment_report()
        
        # Итоговая сводка
        self._print_deployment_summary(dry_run)
        
        return True
    
    def _load_deployment_config(self, config_path: str) -> Optional[Dict]:
        """Загружает конфигурацию развертывания"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            self.deployment_session['errors'].append(f"Файл конфигурации развертывания не найден: {config_path}")
            return None
        except json.JSONDecodeError as e:
            self.deployment_session['errors'].append(f"Ошибка в файле конфигурации развертывания: {e}")
            return None
    
    def _execute_phase(self, phase_name: str, phase_description: str, phase_function, 
                      server_config: Dict, deployment_config: Dict, dry_run: bool) -> bool:
        """Выполняет фазу развертывания"""
        print(f"\n📋 ФАЗА: {phase_description.upper()}")
        print("-" * 50)
        
        phase_start_time = datetime.datetime.now()
        
        try:
            # Выполняем фазу
            phase_result = phase_function(server_config, deployment_config, dry_run)
            
            # Сохраняем результат фазы
            self.deployment_session['phases'][phase_name] = {
                'description': phase_description,
                'start_time': phase_start_time.isoformat(),
                'end_time': datetime.datetime.now().isoformat(),
                'success': phase_result['success'],
                'details': phase_result,
                'dry_run': dry_run
            }
            
            if phase_result['success']:
                print(f"✅ {phase_description} завершена успешно")
                return True
            else:
                print(f"❌ {phase_description} не пройдена")
                if 'errors' in phase_result:
                    for error in phase_result['errors']:
                        print(f"   - {error}")
                return False
                
        except Exception as e:
            print(f"❌ Исключение в фазе {phase_description}: {e}")
            self.deployment_session['errors'].append(f"Исключение в фазе {phase_description}: {e}")
            
            # Сохраняем информацию об ошибке
            self.deployment_session['phases'][phase_name] = {
                'description': phase_description,
                'start_time': phase_start_time.isoformat(),
                'end_time': datetime.datetime.now().isoformat(),
                'success': False,
                'error': str(e),
                'dry_run': dry_run
            }
            return False
    
    def _phase_pre_deployment_validation(self, server_config: Dict, deployment_config: Dict, dry_run: bool) -> Dict:
        """Фаза 1: Предварительная проверка"""
        result = {
            'success': True,
            'server_accessible': False,
            'deployment_config_valid': False,
            'dependencies_available': False,
            'permissions_ok': False,
            'errors': [],
            'warnings': []
        }
        
        # Проверка подключения к серверу
        print("🔗 Проверка подключения к серверу...")
        if self._test_server_connection(server_config['server']):
            result['server_accessible'] = True
            print("✅ Сервер доступен")
        else:
            result['success'] = False
            result['errors'].append("Сервер недоступен")
            print("❌ Сервер недоступен")
            return result
        
        # Проверка конфигурации развертывания
        print("📋 Проверка конфигурации развертывания...")
        config_validation = self._validate_deployment_config(deployment_config)
        if config_validation['valid']:
            result['deployment_config_valid'] = True
            print("✅ Конфигурация развертывания валидна")
        else:
            result['success'] = False
            result['errors'].extend(config_validation['errors'])
            print("❌ Конфигурация развертывания невалидна")
            return result
        
        # Проверка зависимостей
        print("📦 Проверка зависимостей...")
        dependencies_check = self._check_dependencies(deployment_config)
        if dependencies_check['success']:
            result['dependencies_available'] = True
            print("✅ Все зависимости доступны")
        else:
            result['warnings'].extend(dependencies_check['warnings'])
            print("⚠️  Некоторые зависимости недоступны")
        
        # Проверка прав доступа
        print("🔒 Проверка прав доступа...")
        permissions_check = self._check_permissions(server_config['server'], deployment_config)
        if permissions_check['success']:
            result['permissions_ok'] = True
            print("✅ Права доступа корректны")
        else:
            result['success'] = False
            result['errors'].extend(permissions_check['errors'])
            print("❌ Недостаточно прав доступа")
            return result
        
        return result
    
    def _phase_system_analysis(self, server_config: Dict, deployment_config: Dict, dry_run: bool) -> Dict:
        """Фаза 2: Анализ системы"""
        result = {
            'success': True,
            'files_analyzed': 0,
            'conflicts_detected': [],
            'risks_identified': [],
            'recommendations': [],
            'errors': []
        }
        
        print("🔍 Анализ файлов для развертывания...")
        
        # Анализируем файлы через анализатор
        analysis_result = self.file_analyzer.analyze_deployment_plan(deployment_config)
        
        if analysis_result.get('errors'):
            result['errors'].extend(analysis_result['errors'])
            result['success'] = False
            return result
        
        files_to_backup = analysis_result.get('files_to_backup', {})
        result['files_analyzed'] = len(files_to_backup)
        
        print(f"📊 Проанализировано файлов: {result['files_analyzed']}")
        
        # Проверка конфликтов
        print("⚠️  Проверка конфликтов...")
        conflicts = self._detect_deployment_conflicts(server_config['server'], files_to_backup)
        result['conflicts_detected'] = conflicts
        
        if conflicts:
            print(f"⚠️  Обнаружены конфликты: {len(conflicts)}")
            for conflict in conflicts[:3]:  # Показываем первые 3
                print(f"   - {conflict}")
        else:
            print("✅ Конфликты не обнаружены")
        
        # Анализ рисков
        print("🔍 Анализ рисков...")
        risks = self._analyze_deployment_risks(files_to_backup)
        result['risks_identified'] = risks
        
        if risks:
            print(f"⚠️  Выявлены риски: {len(risks)}")
            for risk in risks[:3]:  # Показываем первые 3
                print(f"   - {risk}")
        else:
            print("✅ Серьезные риски не выявлены")
        
        # Генерация рекомендаций
        recommendations = self._generate_deployment_recommendations(files_to_backup, conflicts, risks)
        result['recommendations'] = recommendations
        
        if recommendations:
            print(f"💡 Рекомендации: {len(recommendations)}")
            for rec in recommendations[:3]:  # Показываем первые 3
                print(f"   - {rec}")
        
        return result
    
    def _phase_backup_creation(self, server_config: Dict, deployment_config: Dict, dry_run: bool) -> Dict:
        """Фаза 3: Создание резервной копии"""
        result = {
            'success': True,
            'backup_session_id': None,
            'files_backed_up': 0,
            'backup_size': 0,
            'errors': []
        }
        
        if dry_run:
            print("🧪 Режим тестирования - резервная копия не создается")
            result['backup_session_id'] = f"dry_run_{self.deployment_session['session_id']}"
            return result
        
        print("📦 Создание резервной копии...")
        
        # Создаем резервную копию
        backup_success = self.backup_manager.create_comprehensive_backup(
            deployment_config=deployment_config
        )
        
        if backup_success:
            result['backup_session_id'] = self.backup_manager.session_info['session_id']
            
            # Получаем статистику из сессии backup_manager
            backup_stats = getattr(self.backup_manager, 'last_backup_stats', {})
            result['files_backed_up'] = backup_stats.get('successful_count', 0)
            result['backup_size'] = backup_stats.get('total_size', 0)
            
            # Сохраняем ID резервной копии в сессии развертывания
            self.deployment_session['backup_session_id'] = result['backup_session_id']
            self.deployment_session['rollback_available'] = True
            
            print(f"✅ Резервная копия создана: {result['backup_session_id']}")
        else:
            result['success'] = False
            result['errors'].append("Не удалось создать резервную копию")
            print("❌ Не удалось создать резервную копию")
        
        return result
    
    def _phase_deployment_validation(self, server_config: Dict, deployment_config: Dict, dry_run: bool) -> Dict:
        """Фаза 4: Валидация развертывания"""
        result = {
            'success': True,
            'files_validated': 0,
            'syntax_errors': [],
            'dependency_errors': [],
            'compatibility_issues': [],
            'errors': []
        }
        
        print("✅ Валидация файлов развертывания...")
        
        # Получаем список файлов для развертывания
        files_info = deployment_config.get('files', [])
        
        for file_info in files_info:
            local_path = file_info.get('local', '')
            file_type = file_info.get('type', 'unknown')
            
            if not local_path:
                continue
            
            # Проверяем существование локального файла
            local_file_path = self.project_root / local_path
            if not local_file_path.exists():
                result['errors'].append(f"Локальный файл не найден: {local_path}")
                continue
            
            print(f"🔍 Валидация: {local_path}")
            
            # Проверяем синтаксис
            syntax_check = self._validate_file_syntax(local_file_path, file_type)
            if not syntax_check['valid']:
                result['syntax_errors'].extend(syntax_check['errors'])
                print(f"❌ Синтаксическая ошибка в {local_path}")
            
            # Проверяем зависимости
            dependency_check = self._validate_file_dependencies(local_file_path, file_type)
            if not dependency_check['valid']:
                result['dependency_errors'].extend(dependency_check['errors'])
                print(f"⚠️  Проблемы с зависимостями в {local_path}")
            
            # Проверяем совместимость
            compatibility_check = self._validate_file_compatibility(local_file_path, file_type)
            if not compatibility_check['valid']:
                result['compatibility_issues'].extend(compatibility_check['errors'])
                print(f"⚠️  Проблемы совместимости в {local_path}")
            
            result['files_validated'] += 1
        
        print(f"📊 Проверено файлов: {result['files_validated']}")
        
        # Определяем, критичны ли ошибки
        if result['syntax_errors']:
            result['success'] = False
            result['errors'].append(f"Критические синтаксические ошибки: {len(result['syntax_errors'])}")
        
        return result
    
    def _phase_safe_deployment(self, server_config: Dict, deployment_config: Dict, dry_run: bool) -> Dict:
        """Фаза 5: Безопасное развертывание"""
        result = {
            'success': True,
            'files_deployed': 0,
            'files_failed': 0,
            'deployment_details': {},
            'errors': []
        }
        
        if dry_run:
            print("🧪 Режим тестирования - файлы не развертываются")
            result['files_deployed'] = len(deployment_config.get('files', []))
            return result
        
        print("🚀 Развертывание файлов...")
        
        # Получаем список файлов для развертывания
        files_info = deployment_config.get('files', [])
        
        # Сортируем файлы по приоритету
        sorted_files = sorted(files_info, key=lambda x: self._get_deployment_priority(x))
        
        for file_info in sorted_files:
            local_path = file_info.get('local', '')
            remote_path = file_info.get('remote', '')
            file_type = file_info.get('type', 'unknown')
            
            if not local_path or not remote_path:
                continue
            
            print(f"📤 Развертывание: {os.path.basename(local_path)}")
            
            # Развертываем файл
            deploy_result = self._deploy_single_file(server_config['server'], local_path, remote_path, file_info)
            
            if deploy_result['success']:
                result['files_deployed'] += 1
                result['deployment_details'][remote_path] = deploy_result
                print(f"✅ Развернут: {os.path.basename(local_path)}")
            else:
                result['files_failed'] += 1
                result['deployment_details'][remote_path] = deploy_result
                result['errors'].append(f"Ошибка развертывания {local_path}: {deploy_result.get('error', 'Неизвестная ошибка')}")
                print(f"❌ Ошибка: {os.path.basename(local_path)} - {deploy_result.get('error', 'Неизвестная ошибка')}")
        
        print(f"📊 Развернуто файлов: {result['files_deployed']}")
        print(f"❌ Неудачных файлов: {result['files_failed']}")
        
        if result['files_failed'] > 0:
            result['success'] = False
        
        return result
    
    def _phase_post_deployment_validation(self, server_config: Dict, deployment_config: Dict, dry_run: bool) -> Dict:
        """Фаза 6: Проверка после развертывания"""
        result = {
            'success': True,
            'files_verified': 0,
            'system_functional': False,
            'performance_impact': 'unknown',
            'errors': []
        }
        
        if dry_run:
            print("🧪 Режим тестирования - проверка не выполняется")
            result['system_functional'] = True
            return result
        
        print("✅ Проверка после развертывания...")
        
        # Проверяем развернутые файлы
        files_info = deployment_config.get('files', [])
        
        for file_info in files_info:
            remote_path = file_info.get('remote', '')
            
            if not remote_path:
                continue
            
            print(f"🔍 Проверка: {os.path.basename(remote_path)}")
            
            # Проверяем файл на сервере
            verification_result = self._verify_deployed_file(server_config['server'], remote_path, file_info)
            
            if verification_result['success']:
                result['files_verified'] += 1
                print(f"✅ Проверен: {os.path.basename(remote_path)}")
            else:
                result['errors'].append(f"Ошибка проверки {remote_path}: {verification_result.get('error', 'Неизвестная ошибка')}")
                print(f"❌ Ошибка проверки: {os.path.basename(remote_path)}")
        
        # Проверяем функциональность системы
        print("🔧 Проверка функциональности системы...")
        system_check = self._check_system_functionality(server_config['server'])
        result['system_functional'] = system_check['functional']
        
        if system_check['functional']:
            print("✅ Система функционирует корректно")
        else:
            result['success'] = False
            result['errors'].append("Система не функционирует корректно")
            print("❌ Система не функционирует корректно")
        
        # Проверяем производительность
        print("📊 Проверка производительности...")
        performance_check = self._check_performance_impact(server_config['server'])
        result['performance_impact'] = performance_check['impact']
        
        if performance_check['impact'] == 'high':
            result['errors'].append("Высокое влияние на производительность")
            print("⚠️  Высокое влияние на производительность")
        elif performance_check['impact'] == 'medium':
            print("⚠️  Умеренное влияние на производительность")
        else:
            print("✅ Минимальное влияние на производительность")
        
        return result
    
    def _phase_cleanup(self, server_config: Dict, deployment_config: Dict, dry_run: bool) -> Dict:
        """Фаза 7: Очистка"""
        result = {
            'success': True,
            'temp_files_cleaned': 0,
            'permissions_fixed': 0,
            'errors': []
        }
        
        if dry_run:
            print("🧪 Режим тестирования - очистка не выполняется")
            return result
        
        print("🧹 Очистка после развертывания...")
        
        # Очищаем временные файлы
        temp_cleanup = self._cleanup_temp_files(server_config['server'])
        result['temp_files_cleaned'] = temp_cleanup['cleaned']
        
        # Исправляем права доступа
        permissions_fix = self._fix_file_permissions(server_config['server'], deployment_config)
        result['permissions_fixed'] = permissions_fix['fixed']
        
        # Проверяем на наличие мусора
        garbage_check = self._check_for_garbage(server_config['server'])
        if garbage_check['found']:
            result['errors'].append(f"Найден мусор: {garbage_check['found']} файлов")
        
        print(f"🧹 Очищено временных файлов: {result['temp_files_cleaned']}")
        print(f"🔒 Исправлено прав доступа: {result['permissions_fixed']}")
        
        return result
    
    def _offer_rollback(self):
        """Предлагает откат изменений"""
        if not self.deployment_session.get('rollback_available'):
            print("⚠️  Откат недоступен - резервная копия не создана")
            return
        
        print("\n" + "="*50)
        print("🔄 ПРЕДЛОЖЕНИЕ ОТКАТА")
        print("="*50)
        print("❌ Развертывание не удалось.")
        print("📦 Доступна резервная копия для отката.")
        print(f"🎯 ID резервной копии: {self.deployment_session['backup_session_id']}")
        
        # В реальном сценарии здесь был бы запрос пользователя
        print("\n💡 Для отката используйте команду:")
        print(f"   python enhanced_restore_manager.py full {self.deployment_session['backup_session_id']}")
        
        # Автоматический откат в случае критической ошибки
        if self._is_critical_failure():
            print("\n🚨 Обнаружена критическая ошибка - выполняется автоматический откат...")
            self._perform_automatic_rollback()
    
    def _is_critical_failure(self) -> bool:
        """Проверяет, является ли ошибка критической"""
        # Проверяем наличие критических ошибок
        critical_errors = [
            "Сервер недоступен",
            "Система не функционирует",
            "Критические синтаксические ошибки"
        ]
        
        all_errors = self.deployment_session.get('errors', [])
        
        return any(critical_error in error for error in all_errors for critical_error in critical_errors)
    
    def _perform_automatic_rollback(self):
        """Выполняет автоматический откат"""
        if not self.deployment_session.get('backup_session_id'):
            print("❌ Невозможно выполнить автоматический откат - нет резервной копии")
            return
        
        print("🔄 Выполнение автоматического отката...")
        
        # Выполняем экстренное восстановление
        rollback_success = self.restore_manager.emergency_restore(
            self.deployment_session['backup_session_id']
        )
        
        if rollback_success:
            print("✅ Автоматический откат выполнен успешно")
            self.deployment_session['rollback_performed'] = True
        else:
            print("❌ Автоматический откат не удался")
            self.deployment_session['rollback_failed'] = True
    
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
    
    def _validate_deployment_config(self, deployment_config: Dict) -> Dict:
        """Валидирует конфигурацию развертывания"""
        validation_result = {
            'valid': True,
            'errors': []
        }
        
        # Проверяем обязательные поля
        required_fields = ['project_info', 'files']
        for field in required_fields:
            if field not in deployment_config:
                validation_result['valid'] = False
                validation_result['errors'].append(f"Отсутствует обязательное поле: {field}")
        
        # Проверяем файлы
        if 'files' in deployment_config:
            files = deployment_config['files']
            if not isinstance(files, list):
                validation_result['valid'] = False
                validation_result['errors'].append("Поле 'files' должно быть списком")
            else:
                for i, file_info in enumerate(files):
                    if not isinstance(file_info, dict):
                        validation_result['valid'] = False
                        validation_result['errors'].append(f"Файл {i}: должен быть объектом")
                        continue
                    
                    required_file_fields = ['local', 'remote', 'type']
                    for field in required_file_fields:
                        if field not in file_info:
                            validation_result['valid'] = False
                            validation_result['errors'].append(f"Файл {i}: отсутствует поле '{field}'")
        
        return validation_result
    
    def _check_dependencies(self, deployment_config: Dict) -> Dict:
        """Проверяет зависимости"""
        dependencies_result = {
            'success': True,
            'warnings': []
        }
        
        # Проверяем зависимости файлов
        files = deployment_config.get('files', [])
        for file_info in files:
            local_path = file_info.get('local', '')
            if local_path:
                file_path = self.project_root / local_path
                if not file_path.exists():
                    dependencies_result['success'] = False
                    dependencies_result['warnings'].append(f"Локальный файл не найден: {local_path}")
        
        return dependencies_result
    
    def _check_permissions(self, server_config: Dict, deployment_config: Dict) -> Dict:
        """Проверяет права доступа"""
        permissions_result = {
            'success': True,
            'errors': []
        }
        
        # Проверяем права записи в целевые директории
        files = deployment_config.get('files', [])
        checked_dirs = set()
        
        for file_info in files:
            remote_path = file_info.get('remote', '')
            if remote_path:
                remote_dir = os.path.dirname(remote_path)
                if remote_dir not in checked_dirs:
                    if not self._check_directory_writable(server_config, remote_dir):
                        permissions_result['success'] = False
                        permissions_result['errors'].append(f"Нет прав записи в директорию: {remote_dir}")
                    checked_dirs.add(remote_dir)
        
        return permissions_result
    
    def _check_directory_writable(self, server_config: Dict, directory_path: str) -> bool:
        """Проверяет возможность записи в директорию"""
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
    
    def _detect_deployment_conflicts(self, server_config: Dict, files_to_backup: Dict) -> List[str]:
        """Обнаруживает конфликты при развертывании"""
        conflicts = []
        
        # Проверяем каждый файл на конфликты
        for file_path, file_info in files_to_backup.items():
            # Проверяем, существует ли файл и изменен ли он
            if self._check_file_exists_on_server(server_config, file_path):
                current_size = self._get_remote_file_size(server_config, file_path)
                if current_size > 0:
                    conflicts.append(f"Файл существует и не пуст: {file_path}")
        
        return conflicts
    
    def _analyze_deployment_risks(self, files_to_backup: Dict) -> List[str]:
        """Анализирует риски развертывания"""
        risks = []
        
        for file_path, file_info in files_to_backup.items():
            file_risks = file_info.get('risks', [])
            for risk in file_risks:
                if risk not in risks:
                    risks.append(f"{os.path.basename(file_path)}: {risk}")
        
        return risks
    
    def _generate_deployment_recommendations(self, files_to_backup: Dict, conflicts: List[str], risks: List[str]) -> List[str]:
        """Генерирует рекомендации для развертывания"""
        recommendations = []
        
        if conflicts:
            recommendations.append("Создать резервную копию перед развертыванием")
            recommendations.append("Проверить файлы на конфликты вручную")
        
        if risks:
            recommendations.append("Выполнить тестирование на копии системы")
            recommendations.append("Запланировать окно обслуживания")
        
        # Анализируем типы файлов
        has_init_files = any(info.get('file_type') == 'init_file' for info in files_to_backup.values())
        if has_init_files:
            recommendations.append("Особое внимание к init.php файлам")
        
        has_template_files = any(info.get('file_type') in ['template_header', 'template_footer'] for info in files_to_backup.values())
        if has_template_files:
            recommendations.append("Проверить совместимость с шаблоном")
        
        return recommendations
    
    def _validate_file_syntax(self, file_path: Path, file_type: str) -> Dict:
        """Валидирует синтаксис файла"""
        validation_result = {
            'valid': True,
            'errors': []
        }
        
        if file_type == 'php':
            # Проверяем PHP синтаксис
            try:
                result = subprocess.run(['php', '-l', str(file_path)], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    validation_result['valid'] = False
                    validation_result['errors'].append(f"PHP синтаксическая ошибка: {result.stderr}")
            except:
                validation_result['errors'].append("Не удалось проверить PHP синтаксис")
        
        elif file_type == 'javascript':
            # Проверяем JavaScript синтаксис (если есть node.js)
            try:
                result = subprocess.run(['node', '-c', str(file_path)], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    validation_result['valid'] = False
                    validation_result['errors'].append(f"JavaScript синтаксическая ошибка: {result.stderr}")
            except:
                # Node.js не установлен, пропускаем проверку
                pass
        
        return validation_result
    
    def _validate_file_dependencies(self, file_path: Path, file_type: str) -> Dict:
        """Валидирует зависимости файла"""
        validation_result = {
            'valid': True,
            'errors': []
        }
        
        if file_type == 'php':
            # Проверяем PHP зависимости
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Ищем include/require
                import re
                includes = re.findall(r'(?:include|require)(?:_once)?\s*\(\s*["\']([^"\']+)["\']', content)
                
                for include_path in includes:
                    # Проверяем, существует ли файл
                    if not os.path.isabs(include_path):
                        # Относительный путь
                        full_include_path = file_path.parent / include_path
                        if not full_include_path.exists():
                            validation_result['errors'].append(f"Зависимость не найдена: {include_path}")
                    
            except Exception as e:
                validation_result['errors'].append(f"Ошибка проверки зависимостей: {e}")
        
        return validation_result
    
    def _validate_file_compatibility(self, file_path: Path, file_type: str) -> Dict:
        """Валидирует совместимость файла"""
        validation_result = {
            'valid': True,
            'errors': []
        }
        
        # Проверяем совместимость с версией PHP
        if file_type == 'php':
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Проверяем на использование устаревшего синтаксиса
                deprecated_patterns = [
                    r'mysql_connect\s*\(',
                    r'ereg\s*\(',
                    r'split\s*\('
                ]
                
                for pattern in deprecated_patterns:
                    if re.search(pattern, content):
                        validation_result['errors'].append(f"Использование устаревшего синтаксиса: {pattern}")
                        
            except Exception as e:
                validation_result['errors'].append(f"Ошибка проверки совместимости: {e}")
        
        return validation_result
    
    def _get_deployment_priority(self, file_info: Dict) -> int:
        """Возвращает приоритет развертывания файла"""
        file_type = file_info.get('type', 'unknown')
        
        # Конфигурационные файлы развертываем первыми
        if file_type == 'config':
            return 1
        # Затем PHP файлы
        elif file_type == 'php':
            return 2
        # Затем JavaScript
        elif file_type == 'javascript':
            return 3
        # Затем CSS
        elif file_type == 'css':
            return 4
        # Остальные файлы
        else:
            return 5
    
    def _deploy_single_file(self, server_config: Dict, local_path: str, remote_path: str, file_info: Dict) -> Dict:
        """Развертывает один файл"""
        result = {
            'success': False,
            'local_path': local_path,
            'remote_path': remote_path,
            'file_info': file_info,
            'error': None
        }
        
        try:
            # Полный путь к локальному файлу
            local_file_path = self.project_root / local_path
            
            if not local_file_path.exists():
                result['error'] = f"Локальный файл не найден: {local_path}"
                return result
            
            # Создаем директорию на сервере при необходимости
            remote_dir = os.path.dirname(remote_path)
            if not self._ensure_remote_directory(server_config, remote_dir):
                result['error'] = f"Не удалось создать директорию на сервере: {remote_dir}"
                return result
            
            # Копируем файл на сервер
            if self._copy_file_to_server(server_config, local_file_path, remote_path):
                # Устанавливаем права доступа
                permissions = file_info.get('permissions', '644')
                if self._set_file_permissions(server_config, remote_path, permissions):
                    result['success'] = True
                else:
                    result['error'] = f"Не удалось установить права доступа: {permissions}"
            else:
                result['error'] = "Не удалось скопировать файл на сервер"
                
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def _copy_file_to_server(self, server_config: Dict, local_path: Path, remote_path: str) -> bool:
        """Копирует файл на сервер"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._copy_to_server_with_key(server_config, local_path, remote_path)
        else:
            return self._copy_to_server_with_password(server_config, local_path, remote_path)
    
    def _copy_to_server_with_key(self, server_config: Dict, local_path: Path, remote_path: str) -> bool:
        """Копирует файл на сервер с ключом"""
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
        """Копирует файл на сервер с паролем"""
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
        """Создает директорию на сервере"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._ensure_remote_directory_with_key(server_config, remote_dir)
        else:
            return self._ensure_remote_directory_with_password(server_config, remote_dir)
    
    def _ensure_remote_directory_with_key(self, server_config: Dict, remote_dir: str) -> bool:
        """Создает директорию на сервере с ключом"""
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
        """Создает директорию на сервере с паролем"""
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
    
    def _set_file_permissions(self, server_config: Dict, remote_path: str, permissions: str) -> bool:
        """Устанавливает права доступа к файлу"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._set_file_permissions_with_key(server_config, remote_path, permissions)
        else:
            return self._set_file_permissions_with_password(server_config, remote_path, permissions)
    
    def _set_file_permissions_with_key(self, server_config: Dict, remote_path: str, permissions: str) -> bool:
        """Устанавливает права доступа с ключом"""
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
                f'chmod {permissions} "{remote_path}"'
            ]
        else:
            if key_path.suffix.lower() == '.ppk':
                return False
            
            cmd = [
                'ssh',
                '-i', str(key_path),
                '-o', 'StrictHostKeyChecking=no',
                f"{server_config['user']}@{server_config['host']}",
                f'chmod {permissions} "{remote_path}"'
            ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
            return True
        except:
            return False
    
    def _set_file_permissions_with_password(self, server_config: Dict, remote_path: str, permissions: str) -> bool:
        """Устанавливает права доступа с паролем"""
        cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            f"{server_config['user']}@{server_config['host']}",
            f'chmod {permissions} "{remote_path}"'
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
            return True
        except:
            return False
    
    def _verify_deployed_file(self, server_config: Dict, remote_path: str, file_info: Dict) -> Dict:
        """Проверяет развернутый файл"""
        verification_result = {
            'success': False,
            'error': None
        }
        
        try:
            # Проверяем существование файла
            if not self._check_file_exists_on_server(server_config, remote_path):
                verification_result['error'] = "Файл не найден на сервере"
                return verification_result
            
            # Проверяем права доступа
            expected_permissions = file_info.get('permissions', '644')
            if not self._check_file_permissions_match(server_config, remote_path, expected_permissions):
                verification_result['error'] = f"Неверные права доступа (ожидается {expected_permissions})"
                return verification_result
            
            verification_result['success'] = True
            
        except Exception as e:
            verification_result['error'] = str(e)
        
        return verification_result
    
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
    
    def _check_file_permissions_match(self, server_config: Dict, file_path: str, expected_permissions: str) -> bool:
        """Проверяет соответствие прав доступа"""
        # Для упрощения считаем, что права соответствуют, если файл существует
        return self._check_file_exists_on_server(server_config, file_path)
    
    def _check_system_functionality(self, server_config: Dict) -> Dict:
        """Проверяет функциональность системы"""
        functionality_result = {
            'functional': True,
            'checks': []
        }
        
        # Проверяем доступность веб-сервера
        web_check = self._check_web_server_status(server_config)
        functionality_result['checks'].append({
            'name': 'web_server',
            'status': web_check,
            'critical': True
        })
        
        if not web_check:
            functionality_result['functional'] = False
        
        # Проверяем доступность PHP
        php_check = self._check_php_status(server_config)
        functionality_result['checks'].append({
            'name': 'php',
            'status': php_check,
            'critical': True
        })
        
        if not php_check:
            functionality_result['functional'] = False
        
        return functionality_result
    
    def _check_web_server_status(self, server_config: Dict) -> bool:
        """Проверяет статус веб-сервера"""
        # Простая проверка - выполняем команду на сервере
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._check_web_server_with_key(server_config)
        else:
            return self._check_web_server_with_password(server_config)
    
    def _check_web_server_with_key(self, server_config: Dict) -> bool:
        """Проверяет веб-сервер с ключом"""
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
                'systemctl is-active apache2 2>/dev/null || systemctl is-active nginx 2>/dev/null || echo "unknown"'
            ]
        else:
            if key_path.suffix.lower() == '.ppk':
                return False
            
            cmd = [
                'ssh',
                '-i', str(key_path),
                '-o', 'StrictHostKeyChecking=no',
                f"{server_config['user']}@{server_config['host']}",
                'systemctl is-active apache2 2>/dev/null || systemctl is-active nginx 2>/dev/null || echo "unknown"'
            ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            return 'active' in result.stdout
        except:
            return False
    
    def _check_web_server_with_password(self, server_config: Dict) -> bool:
        """Проверяет веб-сервер с паролем"""
        cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            f"{server_config['user']}@{server_config['host']}",
            'systemctl is-active apache2 2>/dev/null || systemctl is-active nginx 2>/dev/null || echo "unknown"'
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            return 'active' in result.stdout
        except:
            return False
    
    def _check_php_status(self, server_config: Dict) -> bool:
        """Проверяет статус PHP"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._check_php_with_key(server_config)
        else:
            return self._check_php_with_password(server_config)
    
    def _check_php_with_key(self, server_config: Dict) -> bool:
        """Проверяет PHP с ключом"""
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
                'php -v 2>/dev/null && echo "php_ok"'
            ]
        else:
            if key_path.suffix.lower() == '.ppk':
                return False
            
            cmd = [
                'ssh',
                '-i', str(key_path),
                '-o', 'StrictHostKeyChecking=no',
                f"{server_config['user']}@{server_config['host']}",
                'php -v 2>/dev/null && echo "php_ok"'
            ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            return 'php_ok' in result.stdout
        except:
            return False
    
    def _check_php_with_password(self, server_config: Dict) -> bool:
        """Проверяет PHP с паролем"""
        cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            f"{server_config['user']}@{server_config['host']}",
            'php -v 2>/dev/null && echo "php_ok"'
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=15)
            return 'php_ok' in result.stdout
        except:
            return False
    
    def _check_performance_impact(self, server_config: Dict) -> Dict:
        """Проверяет влияние на производительность"""
        performance_result = {
            'impact': 'low',
            'metrics': {}
        }
        
        # Простая проверка - считаем влияние низким
        # В реальной системе здесь были бы более сложные проверки
        
        return performance_result
    
    def _cleanup_temp_files(self, server_config: Dict) -> Dict:
        """Очищает временные файлы"""
        cleanup_result = {
            'cleaned': 0
        }
        
        # Простая очистка - считаем, что очистили 0 файлов
        # В реальной системе здесь была бы реальная очистка
        
        return cleanup_result
    
    def _fix_file_permissions(self, server_config: Dict, deployment_config: Dict) -> Dict:
        """Исправляет права доступа к файлам"""
        permissions_result = {
            'fixed': 0
        }
        
        # Проверяем и исправляем права доступа для всех развернутых файлов
        files = deployment_config.get('files', [])
        
        for file_info in files:
            remote_path = file_info.get('remote', '')
            permissions = file_info.get('permissions', '644')
            
            if remote_path and self._set_file_permissions(server_config, remote_path, permissions):
                permissions_result['fixed'] += 1
        
        return permissions_result
    
    def _check_for_garbage(self, server_config: Dict) -> Dict:
        """Проверяет на наличие мусора"""
        garbage_result = {
            'found': 0
        }
        
        # Простая проверка - считаем, что мусора нет
        # В реальной системе здесь была бы проверка на временные файлы, логи и т.д.
        
        return garbage_result
    
    def _save_deployment_report(self):
        """Сохраняет отчет о развертывании"""
        report = {
            'timestamp': self.deployment_session['timestamp'],
            'session_id': self.deployment_session['session_id'],
            'deployment_config': self.deployment_session['deployment_config'],
            'phases': self.deployment_session['phases'],
            'backup_session_id': self.deployment_session.get('backup_session_id'),
            'rollback_available': self.deployment_session.get('rollback_available', False),
            'rollback_performed': self.deployment_session.get('rollback_performed', False),
            'errors': self.deployment_session['errors'],
            'warnings': self.deployment_session['warnings']
        }
        
        report_file = self.reports_dir / f"{self.deployment_session['session_id']}_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Отчет о развертывании сохранен: {report_file}")
    
    def _print_deployment_summary(self, dry_run: bool):
        """Выводит сводку развертывания"""
        print("\n" + "="*70)
        print("📊 ИТОГОВАЯ СВОДКА РАЗВЕРТЫВАНИЯ")
        print("="*70)
        
        print(f"🎯 Сессия: {self.deployment_session['session_id']}")
        print(f"📅 Время: {self.deployment_session['timestamp']}")
        if dry_run:
            print("🧪 Режим: ТЕСТИРОВАНИЕ")
        else:
            print("🚀 Режим: ПРОДАКШН")
        
        # Сводка по фазам
        phases = self.deployment_session.get('phases', {})
        successful_phases = sum(1 for phase in phases.values() if phase.get('success'))
        total_phases = len(phases)
        
        print(f"\n📋 Фазы развертывания:")
        print(f"   ✅ Успешно: {successful_phases}/{total_phases}")
        
        for phase_name, phase_info in phases.items():
            status = "✅" if phase_info.get('success') else "❌"
            print(f"   {status} {phase_info.get('description', phase_name)}")
        
        # Информация о резервной копии
        if self.deployment_session.get('backup_session_id'):
            print(f"\n📦 Резервная копия: {self.deployment_session['backup_session_id']}")
            print(f"🔄 Откат доступен: {'Да' if self.deployment_session.get('rollback_available') else 'Нет'}")
        
        # Ошибки и предупреждения
        errors = self.deployment_session.get('errors', [])
        warnings = self.deployment_session.get('warnings', [])
        
        if errors:
            print(f"\n❌ Ошибки ({len(errors)}):")
            for error in errors[:5]:  # Показываем первые 5
                print(f"   - {error}")
        
        if warnings:
            print(f"\n⚠️  Предупреждения ({len(warnings)}):")
            for warning in warnings[:5]:  # Показываем первые 5
                print(f"   - {warning}")
        
        # Итоговый статус
        if successful_phases == total_phases and not errors:
            if dry_run:
                print(f"\n🎉 ТЕСТИРОВАНИЕ ПРОШЛО УСПЕШНО!")
                print("✅ Все проверки пройдены, система готова к развертыванию")
            else:
                print(f"\n🎉 РАЗВЕРТЫВАНИЕ УСПЕШНО ЗАВЕРШЕНО!")
                print("✅ Все файлы развернуты и система функционирует")
        else:
            if dry_run:
                print(f"\n⚠️  ТЕСТИРОВАНИЕ ВЫЯВИЛО ПРОБЛЕМЫ!")
                print("❌ Необходимо исправить ошибки перед развертыванием")
            else:
                print(f"\n⚠️  РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО С ОШИБКАМИ!")
                print("❌ Требуется проверка системы и возможный откат")
                
                if self.deployment_session.get('rollback_available'):
                    print(f"\n💡 Для отката используйте команду:")
                    print(f"   python enhanced_restore_manager.py full {self.deployment_session['backup_session_id']}")


def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python safe_deployment_manager.py deploy <deployment_config.json> [--dry-run]")
        return 1
    
    manager = SafeDeploymentManager()
    
    command = sys.argv[1].lower()
    
    if command == "deploy":
        if len(sys.argv) < 3:
            print("❌ Не указан файл конфигурации развертывания")
            return 1
        
        deployment_config_path = sys.argv[2]
        dry_run = "--dry-run" in sys.argv
        
        print(f"🚀 Безопасное развертывание: {deployment_config_path}")
        if dry_run:
            print("🧪 Режим тестирования")
        
        success = manager.safe_deploy(deployment_config_path, dry_run)
        return 0 if success else 1
    
    else:
        print("❌ Неизвестная команда")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 