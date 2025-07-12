#!/usr/bin/env python3
"""
Специализированный инспектор для сбора информации о модуле задач Bitrix24
Собирает детальную информацию, необходимую для кастомизации задач
"""

import os
import sys
import json
import re
import glob
import datetime
from pathlib import Path

class BitrixTasksInspector:
    def __init__(self, bitrix_path):
        self.bitrix_path = Path(bitrix_path)
        self.report = {
            'timestamp': datetime.datetime.now().isoformat(),
            'bitrix_path': str(bitrix_path),
            'tasks_module': {},
            'user_fields': {},
            'templates_info': {},
            'events_handlers': {},
            'init_files': {},
            'custom_components': {},
            'task_statuses': {},
            'workflows': {},
            'errors': []
        }
    
    def collect_tasks_module_info(self):
        """Собирает информацию о модуле задач"""
        print("🔍 Анализ модуля задач...")
        
        tasks_module_path = self.bitrix_path / 'bitrix' / 'modules' / 'tasks'
        if not tasks_module_path.exists():
            self.report['errors'].append("Модуль задач не найден")
            return
        
        self.report['tasks_module']['path'] = str(tasks_module_path)
        self.report['tasks_module']['exists'] = True
        
        # Проверяем версию модуля задач
        version_file = tasks_module_path / 'install' / 'version.php'
        if version_file.exists():
            try:
                with open(version_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    version_match = re.search(r'\$arModuleVersion\s*=\s*array\s*\(\s*["\']VERSION["\']\s*=>\s*["\']([^"\']+)["\']', content)
                    if version_match:
                        self.report['tasks_module']['version'] = version_match.group(1)
            except Exception as e:
                self.report['errors'].append(f"Ошибка чтения версии модуля задач: {e}")
        
        # Проверяем ключевые файлы модуля
        key_files = [
            'classes/general/task.php',
            'classes/general/taskitem.php',
            'lib/item/task.php',
            'install/components/bitrix/tasks.task/component.php'
        ]
        
        found_files = []
        for file_path in key_files:
            full_path = tasks_module_path / file_path
            if full_path.exists():
                found_files.append(file_path)
        
        self.report['tasks_module']['key_files'] = found_files
    
    def collect_user_fields_info(self):
        """Собирает информацию о пользовательских полях задач"""
        print("🔍 Анализ пользовательских полей...")
        
        # Ищем определения пользовательских полей в PHP файлах
        search_paths = [
            self.bitrix_path / 'local' / 'php_interface',
            self.bitrix_path / 'bitrix' / 'php_interface'
        ]
        
        user_fields = {}
        
        for search_path in search_paths:
            if not search_path.exists():
                continue
                
            # Ищем файлы с определениями полей
            php_files = glob.glob(str(search_path / '**' / '*.php'), recursive=True)
            
            for php_file in php_files:
                try:
                    with open(php_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                        # Ищем определения UF полей
                        uf_matches = re.findall(r'UF_[A-Z_]+', content)
                        if uf_matches:
                            rel_path = str(Path(php_file).relative_to(self.bitrix_path))
                            user_fields[rel_path] = list(set(uf_matches))
                            
                except Exception as e:
                    self.report['errors'].append(f"Ошибка чтения файла {php_file}: {e}")
        
        self.report['user_fields'] = user_fields
    
    def collect_templates_structure(self):
        """Собирает детальную информацию о шаблонах"""
        print("🔍 Анализ структуры шаблонов...")
        
        templates_info = {}
        
        # Анализируем локальные шаблоны
        local_templates = self.bitrix_path / 'local' / 'templates'
        if local_templates.exists():
            templates_info['local'] = self._analyze_template_directory(local_templates)
        
        # Анализируем системные шаблоны
        bitrix_templates = self.bitrix_path / 'bitrix' / 'templates'
        if bitrix_templates.exists():
            templates_info['bitrix'] = self._analyze_template_directory(bitrix_templates)
        
        self.report['templates_info'] = templates_info
    
    def _analyze_template_directory(self, template_dir):
        """Анализирует конкретную директорию шаблонов"""
        template_info = {}
        
        try:
            for template_name in os.listdir(template_dir):
                template_path = template_dir / template_name
                if not template_path.is_dir():
                    continue
                
                info = {
                    'has_header': (template_path / 'header.php').exists(),
                    'has_footer': (template_path / 'footer.php').exists(),
                    'has_assets': (template_path / 'assets').exists(),
                    'js_files': [],
                    'css_files': []
                }
                
                # Ищем JS и CSS файлы
                assets_path = template_path / 'assets'
                if assets_path.exists():
                    js_path = assets_path / 'js'
                    css_path = assets_path / 'css'
                    
                    if js_path.exists():
                        info['js_files'] = [f.name for f in js_path.glob('*.js')]
                    
                    if css_path.exists():
                        info['css_files'] = [f.name for f in css_path.glob('*.css')]
                
                template_info[template_name] = info
                
        except Exception as e:
            self.report['errors'].append(f"Ошибка анализа шаблонов в {template_dir}: {e}")
        
        return template_info
    
    def collect_event_handlers(self):
        """Ищет обработчики событий задач"""
        print("🔍 Поиск обработчиков событий задач...")
        
        handlers = {}
        
        # Ищем init.php файлы
        init_files = [
            self.bitrix_path / 'local' / 'php_interface' / 'init.php',
            self.bitrix_path / 'bitrix' / 'php_interface' / 'init.php'
        ]
        
        for init_file in init_files:
            if not init_file.exists():
                continue
                
            try:
                with open(init_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Ищем AddEventHandler для модуля tasks
                    handler_matches = re.findall(
                        r'AddEventHandler\s*\(\s*["\']tasks["\']\s*,\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']',
                        content
                    )
                    
                    if handler_matches:
                        rel_path = str(init_file.relative_to(self.bitrix_path))
                        handlers[rel_path] = handler_matches
                        
            except Exception as e:
                self.report['errors'].append(f"Ошибка чтения {init_file}: {e}")
        
        self.report['events_handlers'] = handlers
    
    def collect_init_files_info(self):
        """Собирает информацию о файлах инициализации"""
        print("🔍 Анализ файлов инициализации...")
        
        init_files_info = {}
        
        init_paths = [
            ('local', self.bitrix_path / 'local' / 'php_interface' / 'init.php'),
            ('bitrix', self.bitrix_path / 'bitrix' / 'php_interface' / 'init.php')
        ]
        
        for location, init_path in init_paths:
            if not init_path.exists():
                init_files_info[location] = {'exists': False}
                continue
            
            try:
                with open(init_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                info = {
                    'exists': True,
                    'size': len(content),
                    'lines': len(content.split('\n')),
                    'has_task_handlers': 'tasks' in content and 'AddEventHandler' in content,
                    'includes_count': len(re.findall(r'(?:include|require)(?:_once)?\s*\(', content)),
                    'functions_count': len(re.findall(r'function\s+\w+\s*\(', content))
                }
                
                init_files_info[location] = info
                
            except Exception as e:
                init_files_info[location] = {'exists': True, 'error': str(e)}
                self.report['errors'].append(f"Ошибка анализа {init_path}: {e}")
        
        self.report['init_files'] = init_files_info
    
    def collect_custom_components(self):
        """Ищет кастомные компоненты для задач"""
        print("🔍 Поиск кастомных компонентов...")
        
        components = {}
        
        # Проверяем локальные компоненты
        local_components = self.bitrix_path / 'local' / 'components'
        if local_components.exists():
            components['local'] = self._find_task_components(local_components)
        
        self.report['custom_components'] = components
    
    def _find_task_components(self, components_dir):
        """Ищет компоненты, связанные с задачами"""
        task_components = {}
        
        try:
            for vendor_dir in components_dir.iterdir():
                if not vendor_dir.is_dir():
                    continue
                
                for component_dir in vendor_dir.iterdir():
                    if not component_dir.is_dir():
                        continue
                    
                    # Ищем компоненты со словом "task" в названии
                    if 'task' in component_dir.name.lower():
                        component_path = f"{vendor_dir.name}:{component_dir.name}"
                        
                        info = {
                            'path': str(component_dir.relative_to(self.bitrix_path)),
                            'has_component_php': (component_dir / 'component.php').exists(),
                            'has_class_php': (component_dir / 'class.php').exists(),
                            'templates': []
                        }
                        
                        # Ищем шаблоны компонента
                        templates_dir = component_dir / 'templates'
                        if templates_dir.exists():
                            info['templates'] = [t.name for t in templates_dir.iterdir() if t.is_dir()]
                        
                        task_components[component_path] = info
        
        except Exception as e:
            self.report['errors'].append(f"Ошибка поиска компонентов в {components_dir}: {e}")
        
        return task_components
    
    def collect_task_statuses(self):
        """Собирает информацию о статусах задач"""
        print("🔍 Анализ статусов задач...")
        
        # Ищем определения статусов в конфигурационных файлах
        status_info = {}
        
        # Проверяем .settings.php
        settings_file = self.bitrix_path / 'bitrix' / '.settings.php'
        if settings_file.exists():
            try:
                # Читаем только первые 1000 строк для безопасности
                with open(settings_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()[:1000]
                    content = ''.join(lines)
                
                # Ищем упоминания статусов задач
                if 'task' in content.lower():
                    status_info['has_task_config'] = True
                
            except Exception as e:
                self.report['errors'].append(f"Ошибка чтения настроек: {e}")
        
        self.report['task_statuses'] = status_info
    
    def save_report(self, filename='bitrix_tasks_inspection_report.json'):
        """Сохраняет отчет в файл"""
        print(f"💾 Сохранение отчета в {filename}...")
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.report, f, indent=2, ensure_ascii=False)
            print(f"✅ Отчет сохранен: {filename}")
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения отчета: {e}")
            return False
    
    def print_summary(self):
        """Выводит краткую сводку"""
        print("\n" + "="*60)
        print("📋 СВОДКА ИНСПЕКЦИИ МОДУЛЯ ЗАДАЧ")
        print("="*60)
        
        print(f"🕒 Время: {self.report['timestamp']}")
        print(f"📁 Путь Bitrix24: {self.report['bitrix_path']}")
        
        # Модуль задач
        tasks_module = self.report['tasks_module']
        if tasks_module.get('exists'):
            print(f"✅ Модуль задач найден")
            if tasks_module.get('version'):
                print(f"📦 Версия модуля: {tasks_module['version']}")
            print(f"🔧 Ключевые файлы: {len(tasks_module.get('key_files', []))}")
        else:
            print("❌ Модуль задач не найден")
        
        # Пользовательские поля
        user_fields = self.report['user_fields']
        total_uf_files = len(user_fields)
        total_uf_fields = sum(len(fields) for fields in user_fields.values())
        print(f"📝 UF поля: {total_uf_fields} в {total_uf_files} файлах")
        
        # Обработчики событий
        handlers = self.report['events_handlers']
        total_handlers = sum(len(h) for h in handlers.values())
        print(f"⚡ Обработчики событий: {total_handlers}")
        
        # Шаблоны
        templates = self.report['templates_info']
        local_templates = len(templates.get('local', {}))
        print(f"🎨 Локальные шаблоны: {local_templates}")
        
        # Компоненты
        components = self.report['custom_components']
        local_components = len(components.get('local', {}))
        print(f"🔧 Кастомные компоненты: {local_components}")
        
        if self.report['errors']:
            print(f"\n⚠️  Ошибки ({len(self.report['errors'])}):")
            for error in self.report['errors'][:5]:
                print(f"   - {error}")
        
        print("\n✅ Инспекция модуля задач завершена!")

def main():
    """Основная функция"""
    print("🔍 Bitrix24 Tasks Inspector - Детальный анализ модуля задач")
    print("="*70)
    
    # Ищем путь к Bitrix24
    possible_paths = [
        '/home/bitrix/www',
        '/var/www/html',
        '/var/www/bitrix'
    ]
    
    bitrix_path = None
    for path in possible_paths:
        if os.path.exists(path) and os.path.exists(os.path.join(path, 'bitrix')):
            bitrix_path = path
            break
    
    if not bitrix_path:
        print("❌ Не найден путь установки Bitrix24")
        return 1
    
    print(f"📁 Найден Bitrix24: {bitrix_path}")
    
    inspector = BitrixTasksInspector(bitrix_path)
    
    # Собираем информацию
    inspector.collect_tasks_module_info()
    inspector.collect_user_fields_info()
    inspector.collect_templates_structure()
    inspector.collect_event_handlers()
    inspector.collect_init_files_info()
    inspector.collect_custom_components()
    inspector.collect_task_statuses()
    
    # Сохраняем и выводим сводку
    inspector.save_report()
    inspector.print_summary()
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 