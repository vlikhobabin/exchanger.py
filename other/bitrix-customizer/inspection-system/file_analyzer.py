#!/usr/bin/env python3
"""
Анализатор файлов для автоматического определения зависимостей
и файлов для резервного копирования при кастомизации Bitrix24
"""

import os
import sys
import json
import re
import datetime
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple


class BitrixFileAnalyzer:
    """Анализатор файлов Bitrix24 для определения зависимостей и резервного копирования"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.analysis_report = {
            'timestamp': datetime.datetime.now().isoformat(),
            'files_to_backup': {},
            'file_dependencies': {},
            'modification_risks': {},
            'deployment_order': [],
            'validation_checks': {},
            'errors': []
        }
        
        # Определяем шаблоны файлов, которые могут быть изменены
        self.file_patterns = {
            'init_files': [
                'local/php_interface/init.php',
                'bitrix/php_interface/init.php'
            ],
            'template_files': [
                'local/templates/*/header.php',
                'local/templates/*/footer.php',
                'local/templates/*/template_styles.css',
                'bitrix/templates/*/header.php',
                'bitrix/templates/*/footer.php'
            ],
            'component_files': [
                'local/components/*/*/templates/*/template.php',
                'local/components/*/*/component.php',
                'bitrix/components/*/*/templates/*/template.php'
            ],
            'js_css_files': [
                'local/templates/*/assets/js/*.js',
                'local/templates/*/assets/css/*.css',
                'bitrix/templates/*/assets/js/*.js',
                'bitrix/templates/*/assets/css/*.css'
            ],
            'config_files': [
                'local/.settings.php',
                'bitrix/.settings.php',
                'local/php_interface/dbconn.php',
                'bitrix/php_interface/dbconn.php'
            ]
        }
        
        # Приоритеты для резервного копирования
        self.backup_priorities = {
            'critical': ['init.php', 'header.php', 'footer.php', '.settings.php'],
            'high': ['component.php', 'template.php', 'dbconn.php'],
            'medium': ['*.js', '*.css', 'class.php'],
            'low': ['*.txt', '*.md', '*.log']
        }
        
    def analyze_deployment_plan(self, deployment_config: Dict) -> Dict:
        """Анализирует план развертывания и определяет файлы для резервирования"""
        print("🔍 Анализ плана развертывания...")
        
        if not deployment_config:
            return self.analysis_report
            
        # Анализируем каждый файл в плане развертывания
        for file_info in deployment_config.get('files', []):
            remote_path = file_info.get('remote', '')
            local_path = file_info.get('local', '')
            
            if remote_path:
                self._analyze_file_for_backup(remote_path, local_path, file_info)
        
        # Определяем зависимости
        self._analyze_dependencies()
        
        # Создаем порядок развертывания
        self._create_deployment_order()
        
        # Создаем проверки валидации
        self._create_validation_checks()
        
        return self.analysis_report
    
    def _analyze_file_for_backup(self, remote_path: str, local_path: str, file_info: Dict):
        """Анализирует отдельный файл для резервного копирования"""
        file_analysis = {
            'remote_path': remote_path,
            'local_path': local_path,
            'file_type': self._determine_file_type(remote_path),
            'priority': self._determine_backup_priority(remote_path),
            'backup_required': True,
            'modification_type': file_info.get('modification_type', 'unknown'),
            'dependencies': [],
            'risks': []
        }
        
        # Определяем риски модификации
        risks = self._analyze_modification_risks(remote_path, file_info)
        file_analysis['risks'] = risks
        
        # Определяем зависимости
        dependencies = self._find_file_dependencies(remote_path, local_path)
        file_analysis['dependencies'] = dependencies
        
        # Проверяем, является ли файл критическим
        if self._is_critical_file(remote_path):
            file_analysis['critical'] = True
            file_analysis['backup_required'] = True
        
        # Добавляем дополнительные файлы, которые могут быть затронуты
        additional_files = self._find_additional_affected_files(remote_path, file_info)
        for add_file in additional_files:
            if add_file not in self.analysis_report['files_to_backup']:
                self.analysis_report['files_to_backup'][add_file] = {
                    'remote_path': add_file,
                    'local_path': os.path.basename(add_file),
                    'file_type': self._determine_file_type(add_file),
                    'priority': self._determine_backup_priority(add_file),
                    'backup_required': True,
                    'modification_type': 'indirect',
                    'dependencies': [],
                    'risks': ['indirect_modification']
                }
        
        self.analysis_report['files_to_backup'][remote_path] = file_analysis
    
    def _determine_file_type(self, file_path: str) -> str:
        """Определяет тип файла"""
        file_path = file_path.lower()
        
        if file_path.endswith('init.php'):
            return 'init_file'
        elif file_path.endswith('header.php'):
            return 'template_header'
        elif file_path.endswith('footer.php'):
            return 'template_footer'
        elif file_path.endswith('.php'):
            return 'php_file'
        elif file_path.endswith('.js'):
            return 'javascript'
        elif file_path.endswith('.css'):
            return 'stylesheet'
        elif file_path.endswith('.settings.php'):
            return 'config_file'
        else:
            return 'unknown'
    
    def _determine_backup_priority(self, file_path: str) -> str:
        """Определяет приоритет резервного копирования"""
        file_name = os.path.basename(file_path.lower())
        
        for priority, patterns in self.backup_priorities.items():
            for pattern in patterns:
                if pattern.replace('*', '') in file_name or file_name == pattern:
                    return priority
        
        return 'medium'
    
    def _analyze_modification_risks(self, remote_path: str, file_info: Dict) -> List[str]:
        """Анализирует риски модификации файла"""
        risks = []
        
        # Проверяем, является ли файл системным
        if '/bitrix/' in remote_path and not '/local/' in remote_path:
            risks.append('system_file_modification')
        
        # Проверяем критические файлы
        if any(critical in remote_path for critical in ['init.php', 'header.php', '.settings.php']):
            risks.append('critical_file_modification')
        
        # Проверяем шаблоны
        if '/templates/' in remote_path:
            risks.append('template_modification')
        
        # Проверяем тип модификации
        mod_type = file_info.get('modification_type', 'unknown')
        if mod_type == 'create':
            risks.append('new_file_creation')
        elif mod_type == 'modify':
            risks.append('existing_file_modification')
        elif mod_type == 'append':
            risks.append('file_content_append')
        
        return risks
    
    def _find_file_dependencies(self, remote_path: str, local_path: str) -> List[str]:
        """Находит зависимости файла"""
        dependencies = []
        
        # Если это init.php, он может зависеть от других файлов
        if remote_path.endswith('init.php'):
            # Проверяем, есть ли другие файлы в том же проекте
            if local_path and os.path.exists(local_path):
                try:
                    with open(local_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Ищем include/require
                    includes = re.findall(r'(?:include|require)(?:_once)?\s*\(\s*["\']([^"\']+)["\']', content)
                    dependencies.extend(includes)
                    
                except Exception as e:
                    self.analysis_report['errors'].append(f"Error analyzing {local_path}: {e}")
        
        # Если это header.php, может зависеть от CSS/JS файлов
        if remote_path.endswith('header.php'):
            # Добавляем возможные зависимости от assets
            template_dir = os.path.dirname(remote_path)
            potential_assets = [
                f"{template_dir}/assets/js/enhanced_task_modifier.js",
                f"{template_dir}/assets/css/custom_styles.css"
            ]
            dependencies.extend(potential_assets)
        
        return dependencies
    
    def _find_additional_affected_files(self, remote_path: str, file_info: Dict) -> List[str]:
        """Находит дополнительные файлы, которые могут быть затронуты"""
        additional_files = []
        
        # Если модифицируется init.php, может потребоваться бэкап header.php
        if remote_path.endswith('init.php'):
            # Проверяем, есть ли шаблоны в том же проекте
            if '/local/' in remote_path:
                template_header = remote_path.replace('/php_interface/init.php', '/templates/bitrix24/header.php')
                additional_files.append(template_header)
        
        # Если создается JS файл, может потребоваться бэкап header.php
        if remote_path.endswith('.js') and '/assets/js/' in remote_path:
            template_dir = remote_path.split('/assets/js/')[0]
            header_file = f"{template_dir}/header.php"
            additional_files.append(header_file)
        
        return additional_files
    
    def _is_critical_file(self, file_path: str) -> bool:
        """Проверяет, является ли файл критическим"""
        critical_patterns = [
            'init.php',
            'header.php',
            'footer.php',
            '.settings.php',
            'dbconn.php'
        ]
        
        return any(pattern in file_path for pattern in critical_patterns)
    
    def _analyze_dependencies(self):
        """Анализирует зависимости между файлами"""
        print("🔍 Анализ зависимостей между файлами...")
        
        for file_path, file_info in self.analysis_report['files_to_backup'].items():
            dependencies = file_info.get('dependencies', [])
            
            # Создаем граф зависимостей
            if dependencies:
                self.analysis_report['file_dependencies'][file_path] = {
                    'depends_on': dependencies,
                    'dependency_type': 'include' if any('include' in str(dep) for dep in dependencies) else 'reference'
                }
    
    def _create_deployment_order(self):
        """Создает оптимальный порядок развертывания"""
        print("📋 Создание порядка развертывания...")
        
        # Сортируем файлы по приоритету и зависимостям
        files_by_priority = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': []
        }
        
        for file_path, file_info in self.analysis_report['files_to_backup'].items():
            priority = file_info.get('priority', 'medium')
            files_by_priority[priority].append(file_path)
        
        # Создаем порядок развертывания
        deployment_order = []
        
        # Сначала критические файлы
        for priority in ['critical', 'high', 'medium', 'low']:
            for file_path in files_by_priority[priority]:
                deployment_order.append({
                    'file': file_path,
                    'priority': priority,
                    'order': len(deployment_order) + 1
                })
        
        self.analysis_report['deployment_order'] = deployment_order
    
    def _create_validation_checks(self):
        """Создает проверки валидации для каждого файла"""
        print("✅ Создание проверок валидации...")
        
        for file_path, file_info in self.analysis_report['files_to_backup'].items():
            checks = []
            
            file_type = file_info.get('file_type', 'unknown')
            
            if file_type == 'init_file':
                checks.extend([
                    'check_php_syntax',
                    'check_file_permissions',
                    'check_file_encoding',
                    'check_includes_exist'
                ])
            elif file_type in ['template_header', 'template_footer']:
                checks.extend([
                    'check_php_syntax',
                    'check_html_structure',
                    'check_css_js_links',
                    'check_file_permissions'
                ])
            elif file_type == 'php_file':
                checks.extend([
                    'check_php_syntax',
                    'check_file_permissions'
                ])
            elif file_type == 'javascript':
                checks.extend([
                    'check_js_syntax',
                    'check_file_permissions'
                ])
            elif file_type == 'stylesheet':
                checks.extend([
                    'check_css_syntax',
                    'check_file_permissions'
                ])
            elif file_type == 'config_file':
                checks.extend([
                    'check_php_syntax',
                    'check_config_structure',
                    'check_file_permissions',
                    'check_sensitive_data'
                ])
            
            self.analysis_report['validation_checks'][file_path] = checks
    
    def analyze_from_inspection_report(self, inspection_report_path: str) -> Dict:
        """Анализирует файлы на основе отчета инспекции"""
        print("🔍 Анализ на основе отчета инспекции...")
        
        try:
            with open(inspection_report_path, 'r', encoding='utf-8') as f:
                inspection_report = json.load(f)
        except Exception as e:
            self.analysis_report['errors'].append(f"Error loading inspection report: {e}")
            return self.analysis_report
        
        # Анализируем файлы кастомизации из отчета
        customization_files = inspection_report.get('customization_files', {})
        
        for file_path, file_info in customization_files.items():
            if file_info.get('exists'):
                self._analyze_existing_file_for_backup(file_path, file_info)
        
        # Анализируем места для кастомизации
        customization_places = inspection_report.get('customization_places', {})
        
        for place_path, place_info in customization_places.items():
            if place_info.get('exists') and place_info.get('recommended'):
                self._analyze_customization_place(place_path, place_info)
        
        # Анализируем существующие кастомизации
        existing_customizations = inspection_report.get('existing_customizations', {})
        self._analyze_existing_customizations(existing_customizations)
        
        return self.analysis_report
    
    def _analyze_existing_file_for_backup(self, file_path: str, file_info: Dict):
        """Анализирует существующий файл для резервного копирования"""
        backup_info = {
            'remote_path': file_info.get('full_path', file_path),
            'local_path': os.path.basename(file_path),
            'file_type': file_info.get('type', 'unknown'),
            'priority': self._determine_backup_priority(file_path),
            'backup_required': True,
            'modification_type': 'existing',
            'size': file_info.get('size', 0),
            'exists': True,
            'dependencies': [],
            'risks': []
        }
        
        # Добавляем риски
        if file_info.get('type') == 'init_file':
            backup_info['risks'].append('critical_init_file')
        
        if file_info.get('size', 0) > 0:
            backup_info['risks'].append('non_empty_file')
        
        self.analysis_report['files_to_backup'][file_path] = backup_info
    
    def _analyze_customization_place(self, place_path: str, place_info: Dict):
        """Анализирует место для кастомизации"""
        # Если это место для кастомизации существует, возможно там есть файлы
        if place_info.get('exists'):
            # Добавляем информацию о месте
            self.analysis_report['customization_places'] = self.analysis_report.get('customization_places', {})
            self.analysis_report['customization_places'][place_path] = place_info
    
    def _analyze_existing_customizations(self, existing_customizations: Dict):
        """Анализирует существующие кастомизации"""
        for location, customizations in existing_customizations.items():
            if isinstance(customizations, dict):
                # Анализируем файлы кастомизации
                for file_type, files in customizations.items():
                    if isinstance(files, list):
                        for file_name in files:
                            if file_name != '... (truncated)':
                                full_path = f"/home/bitrix/www/local/{file_name}"
                                self.analysis_report['files_to_backup'][full_path] = {
                                    'remote_path': full_path,
                                    'local_path': os.path.basename(file_name),
                                    'file_type': file_type,
                                    'priority': 'medium',
                                    'backup_required': True,
                                    'modification_type': 'existing_customization',
                                    'dependencies': [],
                                    'risks': ['existing_customization']
                                }
    
    def save_analysis_report(self, output_path: Optional[str] = None):
        """Сохраняет отчет анализа"""
        if not output_path:
            output_path = self.project_root / "reports" / f"file_analysis_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.analysis_report, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Отчет анализа сохранен: {output_path}")
        return output_path
    
    def print_analysis_summary(self):
        """Выводит краткую сводку анализа"""
        print("\n" + "="*60)
        print("📊 СВОДКА АНАЛИЗА ФАЙЛОВ")
        print("="*60)
        
        files_to_backup = self.analysis_report.get('files_to_backup', {})
        
        if not files_to_backup:
            print("❌ Не найдено файлов для резервного копирования")
            return
        
        print(f"📁 Всего файлов для резервирования: {len(files_to_backup)}")
        
        # Группируем по приоритетам
        by_priority = {}
        for file_path, file_info in files_to_backup.items():
            priority = file_info.get('priority', 'medium')
            if priority not in by_priority:
                by_priority[priority] = []
            by_priority[priority].append(file_path)
        
        print("\n📊 По приоритетам:")
        for priority in ['critical', 'high', 'medium', 'low']:
            if priority in by_priority:
                print(f"   {priority.upper()}: {len(by_priority[priority])} файлов")
                for file_path in by_priority[priority][:3]:  # Показываем первые 3
                    print(f"      - {os.path.basename(file_path)}")
                if len(by_priority[priority]) > 3:
                    print(f"      ... и еще {len(by_priority[priority]) - 3}")
        
        # Показываем файлы с рисками
        risky_files = [f for f, info in files_to_backup.items() if info.get('risks')]
        if risky_files:
            print(f"\n⚠️  Файлы с рисками: {len(risky_files)}")
            for file_path in risky_files[:5]:  # Показываем первые 5
                risks = files_to_backup[file_path].get('risks', [])
                print(f"   - {os.path.basename(file_path)}: {', '.join(risks)}")
        
        # Показываем порядок развертывания
        deployment_order = self.analysis_report.get('deployment_order', [])
        if deployment_order:
            print(f"\n📋 Порядок развертывания: {len(deployment_order)} файлов")
            for i, item in enumerate(deployment_order[:5]):  # Показываем первые 5
                print(f"   {i+1}. {os.path.basename(item['file'])} ({item['priority']})")
        
        # Показываем ошибки
        errors = self.analysis_report.get('errors', [])
        if errors:
            print(f"\n❌ Ошибки: {len(errors)}")
            for error in errors[:3]:  # Показываем первые 3
                print(f"   - {error}")


def main():
    """Основная функция для тестирования анализатора"""
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python file_analyzer.py deployment_config.json")
        print("  python file_analyzer.py --inspection-report report.json")
        return 1
    
    analyzer = BitrixFileAnalyzer()
    
    if sys.argv[1] == '--inspection-report':
        if len(sys.argv) < 3:
            print("❌ Не указан путь к отчету инспекции")
            return 1
        
        inspection_report_path = sys.argv[2]
        print(f"🔍 Анализ на основе отчета инспекции: {inspection_report_path}")
        
        analyzer.analyze_from_inspection_report(inspection_report_path)
    else:
        # Анализ конфигурации развертывания
        config_path = sys.argv[1]
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                deployment_config = json.load(f)
        except Exception as e:
            print(f"❌ Ошибка загрузки конфигурации: {e}")
            return 1
        
        print(f"🔍 Анализ конфигурации развертывания: {config_path}")
        analyzer.analyze_deployment_plan(deployment_config)
    
    # Сохраняем и выводим результат
    report_path = analyzer.save_analysis_report()
    analyzer.print_analysis_summary()
    
    print(f"\n📄 Полный отчет сохранен: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 