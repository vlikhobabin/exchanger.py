#!/usr/bin/env python3
"""
Скрипт для сбора информации о установке Bitrix24
Запускается на сервере и создает детальный отчет
"""

import os
import sys
import json
import subprocess
import datetime
import glob
import pwd
import grp
from pathlib import Path
import re

class BitrixInspector:
    def __init__(self):
        self.report = {
            'timestamp': datetime.datetime.now().isoformat(),
            'hostname': self.get_hostname(),
            'system_info': {},
            'bitrix_info': {},
            'web_server': {},
            'php_info': {},
            'database_info': {},
            'file_structure': {},
            'permissions': {},
            'custom_fields': {},
            'modules': {},
            'templates': {},
            'customization_files': {},
            'customization_places': {},
            'existing_customizations': {},
            'errors': []
        }
        
    def get_hostname(self):
        """Получает имя хоста"""
        try:
            return subprocess.check_output(['hostname']).decode().strip()
        except:
            return 'unknown'
    
    def collect_system_info(self):
        """Собирает системную информацию"""
        print("🔍 Сбор системной информации...")
        
        try:
            # Версия ОС
            with open('/etc/os-release', 'r') as f:
                os_info = f.read()
                for line in os_info.split('\n'):
                    if line.startswith('PRETTY_NAME='):
                        self.report['system_info']['os'] = line.split('=')[1].strip('"')
                        break
        except:
            self.report['system_info']['os'] = 'unknown'
        
        # Версия ядра
        try:
            self.report['system_info']['kernel'] = subprocess.check_output(['uname', '-r']).decode().strip()
        except:
            self.report['system_info']['kernel'] = 'unknown'
        
        # Загрузка системы
        try:
            with open('/proc/loadavg', 'r') as f:
                self.report['system_info']['load_avg'] = f.read().strip()
        except:
            pass
        
        # Использование диска
        try:
            df_output = subprocess.check_output(['df', '-h', '/']).decode()
            lines = df_output.strip().split('\n')
            if len(lines) > 1:
                self.report['system_info']['disk_usage'] = lines[1]
        except:
            pass
    
    def find_bitrix_paths(self):
        """Ищет возможные пути установки Bitrix24"""
        possible_paths = [
            '/home/bitrix/www',
            '/var/www/html',
            '/var/www/bitrix',
            '/usr/local/apache2/htdocs',
            '/opt/lampp/htdocs'
        ]
        
        found_paths = []
        for path in possible_paths:
            if os.path.exists(path) and os.path.exists(os.path.join(path, 'bitrix')):
                found_paths.append(path)
        
        return found_paths
    
    def collect_bitrix_info(self):
        """Собирает информацию о Bitrix24"""
        print("🔍 Сбор информации о Bitrix24...")
        
        bitrix_paths = self.find_bitrix_paths()
        self.report['bitrix_info']['possible_paths'] = bitrix_paths
        
        if not bitrix_paths:
            self.report['errors'].append("Не найдены пути установки Bitrix24")
            return
        
        # Используем первый найденный путь как основной
        main_path = bitrix_paths[0]
        self.report['bitrix_info']['main_path'] = main_path
        
        # Проверяем версию
        version_file = os.path.join(main_path, 'bitrix', 'modules', 'main', 'classes', 'general', 'version.php')
        if os.path.exists(version_file):
            try:
                with open(version_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Ищем версию в файле
                    version_match = re.search(r'\$arModuleVersion\s*=\s*array\s*\(\s*["\']VERSION["\']\s*=>\s*["\']([^"\']+)["\']', content)
                    if version_match:
                        self.report['bitrix_info']['version'] = version_match.group(1)
                    
                    # Ищем дату версии
                    date_match = re.search(r'["\']VERSION_DATE["\']\s*=>\s*["\']([^"\']+)["\']', content)
                    if date_match:
                        self.report['bitrix_info']['version_date'] = date_match.group(1)
            except Exception as e:
                self.report['errors'].append(f"Ошибка чтения версии: {e}")
        
        # Проверяем настройки
        settings_file = os.path.join(main_path, 'bitrix', '.settings.php')
        if os.path.exists(settings_file):
            self.report['bitrix_info']['has_settings'] = True
            try:
                # Читаем размер файла настроек (не содержимое для безопасности)
                self.report['bitrix_info']['settings_size'] = os.path.getsize(settings_file)
            except:
                pass
        
        # Проверяем dbconn.php
        dbconn_file = os.path.join(main_path, 'bitrix', 'php_interface', 'dbconn.php')
        if os.path.exists(dbconn_file):
            self.report['bitrix_info']['has_dbconn'] = True
        
        # Проверяем лицензионный ключ
        license_file = os.path.join(main_path, 'bitrix', 'license_key.php')
        if os.path.exists(license_file):
            self.report['bitrix_info']['has_license'] = True
    
    def collect_web_server_info(self):
        """Собирает информацию о веб-сервере"""
        print("🔍 Сбор информации о веб-сервере...")
        
        # Проверяем Apache
        try:
            apache_version = subprocess.check_output(['apache2', '-v'], stderr=subprocess.DEVNULL).decode()
            self.report['web_server']['apache'] = apache_version.split('\n')[0]
            
            # Проверяем модули Apache
            apache_modules = subprocess.check_output(['apache2ctl', '-M'], stderr=subprocess.DEVNULL).decode()
            modules = [line.strip() for line in apache_modules.split('\n') if line.strip()]
            self.report['web_server']['apache_modules'] = modules
        except:
            pass
        
        # Проверяем Nginx
        try:
            nginx_version = subprocess.check_output(['nginx', '-v'], stderr=subprocess.STDOUT).decode()
            self.report['web_server']['nginx'] = nginx_version.strip()
        except:
            pass
        
        # Проверяем конфигурацию Apache
        apache_configs = [
            '/etc/apache2/sites-enabled/',
            '/etc/httpd/conf.d/',
            '/usr/local/apache2/conf/'
        ]
        
        for config_dir in apache_configs:
            if os.path.exists(config_dir):
                configs = glob.glob(os.path.join(config_dir, '*.conf'))
                if configs:
                    self.report['web_server']['config_files'] = configs
                break
    
    def collect_php_info(self):
        """Собирает информацию о PHP"""
        print("🔍 Сбор информации о PHP...")
        
        try:
            # Версия PHP
            php_version = subprocess.check_output(['php', '-v']).decode()
            self.report['php_info']['version'] = php_version.split('\n')[0]
            
            # Конфигурация PHP
            php_ini = subprocess.check_output(['php', '--ini']).decode()
            for line in php_ini.split('\n'):
                if 'Loaded Configuration File' in line:
                    self.report['php_info']['config_file'] = line.split(':')[1].strip()
                elif 'Scan for additional' in line:
                    self.report['php_info']['additional_configs'] = line.split(':')[1].strip()
            
            # Модули PHP
            php_modules = subprocess.check_output(['php', '-m']).decode()
            self.report['php_info']['modules'] = [m.strip() for m in php_modules.split('\n') if m.strip()]
            
            # Важные настройки PHP
            php_settings = subprocess.check_output([
                'php', '-r', 
                'echo json_encode([' +
                '"memory_limit" => ini_get("memory_limit"),' +
                '"max_execution_time" => ini_get("max_execution_time"),' +
                '"upload_max_filesize" => ini_get("upload_max_filesize"),' +
                '"post_max_size" => ini_get("post_max_size"),' +
                '"max_input_vars" => ini_get("max_input_vars")' +
                ']);'
            ]).decode()
            
            self.report['php_info']['settings'] = json.loads(php_settings)
            
        except Exception as e:
            self.report['errors'].append(f"Ошибка сбора информации о PHP: {e}")
    
    def collect_file_structure(self):
        """Собирает информацию о структуре файлов"""
        print("🔍 Анализ структуры файлов...")
        
        if not self.report['bitrix_info'].get('main_path'):
            return
        
        main_path = self.report['bitrix_info']['main_path']
        
        # Ключевые директории
        key_dirs = [
            'bitrix',
            'local',
            'upload',
            'bitrix/modules',
            'bitrix/templates',
            'bitrix/components',
            'local/templates',
            'local/components',
            'local/php_interface'
        ]
        
        structure = {}
        for dir_name in key_dirs:
            full_path = os.path.join(main_path, dir_name)
            if os.path.exists(full_path):
                try:
                    # Подсчитываем файлы и папки
                    items = os.listdir(full_path)
                    dirs = [item for item in items if os.path.isdir(os.path.join(full_path, item))]
                    files = [item for item in items if os.path.isfile(os.path.join(full_path, item))]
                    
                    structure[dir_name] = {
                        'exists': True,
                        'dirs_count': len(dirs),
                        'files_count': len(files),
                        'dirs': dirs[:20],  # Первые 20 папок
                        'files': files[:20]  # Первые 20 файлов
                    }
                except Exception as e:
                    structure[dir_name] = {'exists': True, 'error': str(e)}
            else:
                structure[dir_name] = {'exists': False}
        
        self.report['file_structure'] = structure
    
    def collect_templates_info(self):
        """Собирает информацию о шаблонах"""
        print("🔍 Сбор информации о шаблонах...")
        
        if not self.report['bitrix_info'].get('main_path'):
            return
        
        main_path = self.report['bitrix_info']['main_path']
        templates = {}
        
        # Шаблоны в bitrix
        bitrix_templates_path = os.path.join(main_path, 'bitrix', 'templates')
        if os.path.exists(bitrix_templates_path):
            try:
                templates['bitrix'] = os.listdir(bitrix_templates_path)
            except:
                templates['bitrix'] = []
        
        # Шаблоны в local
        local_templates_path = os.path.join(main_path, 'local', 'templates')
        if os.path.exists(local_templates_path):
            try:
                templates['local'] = os.listdir(local_templates_path)
            except:
                templates['local'] = []
        
        self.report['templates'] = templates
    
    def collect_permissions(self):
        """Собирает информацию о правах доступа"""
        print("🔍 Проверка прав доступа...")
        
        if not self.report['bitrix_info'].get('main_path'):
            return
        
        main_path = self.report['bitrix_info']['main_path']
        permissions = {}
        
        # Ключевые файлы и папки для проверки
        key_paths = [
            '',  # корень
            'bitrix',
            'local',
            'upload',
            'bitrix/.settings.php',
            'bitrix/php_interface/dbconn.php'
        ]
        
        for rel_path in key_paths:
            full_path = os.path.join(main_path, rel_path)
            if os.path.exists(full_path):
                try:
                    stat = os.stat(full_path)
                    permissions[rel_path or '/'] = {
                        'mode': oct(stat.st_mode)[-3:],
                        'owner': pwd.getpwuid(stat.st_uid).pw_name,
                        'group': grp.getgrgid(stat.st_gid).gr_name,
                        'size': stat.st_size if os.path.isfile(full_path) else None
                    }
                except Exception as e:
                    permissions[rel_path or '/'] = {'error': str(e)}
        
        self.report['permissions'] = permissions
    
    def collect_database_info(self):
        """Собирает информацию о базе данных (без паролей)"""
        print("🔍 Сбор информации о базе данных...")
        
        # Проверяем MySQL
        try:
            mysql_version = subprocess.check_output(['mysql', '--version']).decode()
            self.report['database_info']['mysql_version'] = mysql_version.strip()
        except:
            pass
        
        # Проверяем процессы MySQL
        try:
            mysql_processes = subprocess.check_output(['pgrep', '-l', 'mysql']).decode()
            self.report['database_info']['mysql_running'] = bool(mysql_processes.strip())
        except:
            self.report['database_info']['mysql_running'] = False
    
    def collect_customization_files(self):
        """Собирает информацию о файлах кастомизации"""
        print("🔍 Анализ файлов кастомизации...")
        
        if not self.report['bitrix_info'].get('main_path'):
            return
        
        main_path = self.report['bitrix_info']['main_path']
        customization_files = {}
        
        # Ключевые файлы для кастомизации
        key_files = [
            {
                'path': 'local/php_interface/init.php',
                'type': 'init_file',
                'purpose': 'Локальная инициализация и обработчики событий',
                'required_for': 'custom_event_handlers'
            },
            {
                'path': 'bitrix/php_interface/init.php',
                'type': 'init_file',
                'purpose': 'Системная инициализация (не рекомендуется)',
                'required_for': 'system_event_handlers'
            },
            {
                'path': 'local/php_interface/dbconn.php',
                'type': 'db_config',
                'purpose': 'Локальные настройки базы данных',
                'required_for': 'database_customization'
            },
            {
                'path': 'bitrix/php_interface/dbconn.php',
                'type': 'db_config',
                'purpose': 'Основные настройки базы данных',
                'required_for': 'database_connection'
            },
            {
                'path': 'local/.settings.php',
                'type': 'settings',
                'purpose': 'Локальные настройки системы',
                'required_for': 'local_configuration'
            },
            {
                'path': 'bitrix/.settings.php',
                'type': 'settings',
                'purpose': 'Основные настройки системы',
                'required_for': 'system_configuration'
            }
        ]
        
        for file_info in key_files:
            full_path = os.path.join(main_path, file_info['path'])
            file_data = {
                'exists': os.path.exists(full_path),
                'path': file_info['path'],
                'full_path': full_path,
                'type': file_info['type'],
                'purpose': file_info['purpose'],
                'required_for': file_info['required_for']
            }
            
            if file_data['exists']:
                try:
                    stat = os.stat(full_path)
                    file_data['size'] = stat.st_size
                    file_data['mode'] = oct(stat.st_mode)[-3:]
                    file_data['owner'] = pwd.getpwuid(stat.st_uid).pw_name
                    file_data['group'] = grp.getgrgid(stat.st_gid).gr_name
                    file_data['modified'] = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
                    
                    # Проверяем содержимое для init.php файлов
                    if file_info['type'] == 'init_file':
                        file_data['content_analysis'] = self._analyze_init_file(full_path)
                        
                except Exception as e:
                    file_data['error'] = str(e)
                    self.report['errors'].append(f"Ошибка анализа файла {file_info['path']}: {e}")
            else:
                file_data['can_create'] = self._check_can_create_file(full_path)
                
            customization_files[file_info['path']] = file_data
        
        self.report['customization_files'] = customization_files
    
    def _analyze_init_file(self, file_path):
        """Анализирует содержимое init.php файла"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            analysis = {
                'lines_count': len(content.split('\n')),
                'has_event_handlers': 'AddEventHandler' in content,
                'has_tasks_handlers': 'AddEventHandler' in content and 'tasks' in content,
                'has_includes': any(keyword in content for keyword in ['include', 'require']),
                'has_custom_functions': 'function ' in content,
                'encoding': 'utf-8' if '<?php' in content else 'unknown'
            }
            
            # Ищем обработчики событий
            import re
            event_handlers = re.findall(r'AddEventHandler\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']', content)
            if event_handlers:
                analysis['event_handlers'] = event_handlers
            
            return analysis
        except Exception as e:
            return {'error': str(e)}
    
    def _check_can_create_file(self, file_path):
        """Проверяет, можно ли создать файл по указанному пути"""
        try:
            directory = os.path.dirname(file_path)
            
            # Проверяем, существует ли директория
            if not os.path.exists(directory):
                # Проверяем, можно ли создать директорию
                parent_dir = os.path.dirname(directory)
                if os.path.exists(parent_dir):
                    return {
                        'can_create': True,
                        'need_create_dir': True,
                        'directory': directory,
                        'parent_writable': os.access(parent_dir, os.W_OK)
                    }
                else:
                    return {
                        'can_create': False,
                        'reason': f'Родительская директория не существует: {parent_dir}'
                    }
            else:
                # Директория существует, проверяем права на запись
                return {
                    'can_create': True,
                    'need_create_dir': False,
                    'directory': directory,
                    'directory_writable': os.access(directory, os.W_OK)
                }
        except Exception as e:
            return {
                'can_create': False,
                'reason': f'Ошибка проверки: {e}'
            }
    
    def collect_customization_places(self):
        """Собирает информацию о местах для размещения кастомизаций"""
        print("🔍 Анализ мест для кастомизации...")
        
        if not self.report['bitrix_info'].get('main_path'):
            return
        
        main_path = self.report['bitrix_info']['main_path']
        customization_places = {}
        
        # Ключевые места для кастомизации
        places = [
            {
                'path': 'local/php_interface',
                'type': 'directory',
                'purpose': 'Локальные PHP файлы и обработчики',
                'priority': 'high',
                'recommended': True
            },
            {
                'path': 'local/components',
                'type': 'directory',
                'purpose': 'Кастомные компоненты',
                'priority': 'high',
                'recommended': True
            },
            {
                'path': 'local/templates',
                'type': 'directory',
                'purpose': 'Кастомные шаблоны',
                'priority': 'high',
                'recommended': True
            },
            {
                'path': 'local/modules',
                'type': 'directory',
                'purpose': 'Кастомные модули',
                'priority': 'medium',
                'recommended': True
            },
            {
                'path': 'local/js',
                'type': 'directory',
                'purpose': 'Кастомные JavaScript файлы',
                'priority': 'medium',
                'recommended': True
            },
            {
                'path': 'local/css',
                'type': 'directory',
                'purpose': 'Кастомные CSS файлы',
                'priority': 'medium',
                'recommended': True
            },
            {
                'path': 'upload',
                'type': 'directory',
                'purpose': 'Загружаемые файлы',
                'priority': 'low',
                'recommended': False
            }
        ]
        
        for place in places:
            full_path = os.path.join(main_path, place['path'])
            place_data = {
                'exists': os.path.exists(full_path),
                'path': place['path'],
                'full_path': full_path,
                'type': place['type'],
                'purpose': place['purpose'],
                'priority': place['priority'],
                'recommended': place['recommended']
            }
            
            if place_data['exists']:
                try:
                    stat = os.stat(full_path)
                    place_data['mode'] = oct(stat.st_mode)[-3:]
                    place_data['owner'] = pwd.getpwuid(stat.st_uid).pw_name
                    place_data['group'] = grp.getgrgid(stat.st_gid).gr_name
                    place_data['writable'] = os.access(full_path, os.W_OK)
                    
                    # Подсчитываем содержимое
                    if os.path.isdir(full_path):
                        try:
                            items = os.listdir(full_path)
                            place_data['items_count'] = len(items)
                            place_data['has_content'] = len(items) > 0
                        except:
                            place_data['items_count'] = 0
                            place_data['has_content'] = False
                    
                except Exception as e:
                    place_data['error'] = str(e)
            else:
                place_data['can_create'] = self._check_can_create_directory(full_path)
            
            customization_places[place['path']] = place_data
        
        self.report['customization_places'] = customization_places
    
    def _check_can_create_directory(self, dir_path):
        """Проверяет, можно ли создать директорию"""
        try:
            parent_dir = os.path.dirname(dir_path)
            
            if os.path.exists(parent_dir):
                return {
                    'can_create': True,
                    'parent_exists': True,
                    'parent_writable': os.access(parent_dir, os.W_OK)
                }
            else:
                return {
                    'can_create': False,
                    'reason': f'Родительская директория не существует: {parent_dir}'
                }
        except Exception as e:
            return {
                'can_create': False,
                'reason': f'Ошибка проверки: {e}'
            }
    
    def collect_existing_customizations(self):
        """Собирает информацию о существующих кастомизациях"""
        print("🔍 Поиск существующих кастомизаций...")
        
        if not self.report['bitrix_info'].get('main_path'):
            return
        
        main_path = self.report['bitrix_info']['main_path']
        existing_customizations = {}
        
        # Проверяем local директорию
        local_path = os.path.join(main_path, 'local')
        if os.path.exists(local_path):
            existing_customizations['local'] = self._scan_customizations_directory(local_path)
        
        # Проверяем upload директорию на кастомные файлы
        upload_path = os.path.join(main_path, 'upload')
        if os.path.exists(upload_path):
            existing_customizations['upload'] = self._scan_upload_customizations(upload_path)
        
        # Проверяем битриксовые шаблоны на модификации
        bitrix_templates = os.path.join(main_path, 'bitrix', 'templates')
        if os.path.exists(bitrix_templates):
            existing_customizations['bitrix_templates'] = self._scan_template_customizations(bitrix_templates)
        
        self.report['existing_customizations'] = existing_customizations
    
    def _scan_customizations_directory(self, directory):
        """Сканирует директорию на предмет кастомизаций"""
        customizations = {
            'components': [],
            'templates': [],
            'modules': [],
            'php_files': [],
            'js_files': [],
            'css_files': [],
            'other_files': []
        }
        
        try:
            for root, dirs, files in os.walk(directory):
                rel_path = os.path.relpath(root, directory)
                
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_file_path = os.path.relpath(file_path, directory)
                    
                    if file.endswith('.php'):
                        customizations['php_files'].append(rel_file_path)
                    elif file.endswith('.js'):
                        customizations['js_files'].append(rel_file_path)
                    elif file.endswith('.css'):
                        customizations['css_files'].append(rel_file_path)
                    else:
                        customizations['other_files'].append(rel_file_path)
                
                # Определяем типы кастомизаций по структуре
                if 'components' in rel_path:
                    customizations['components'].extend([d for d in dirs if d != '.'])
                elif 'templates' in rel_path:
                    customizations['templates'].extend([d for d in dirs if d != '.'])
                elif 'modules' in rel_path:
                    customizations['modules'].extend([d for d in dirs if d != '.'])
            
            # Ограничиваем количество элементов для отчета
            for key in customizations:
                if isinstance(customizations[key], list) and len(customizations[key]) > 20:
                    customizations[key] = customizations[key][:20] + ['... (truncated)']
        
        except Exception as e:
            self.report['errors'].append(f"Ошибка сканирования кастомизаций в {directory}: {e}")
        
        return customizations
    
    def _scan_upload_customizations(self, upload_directory):
        """Сканирует upload директорию на кастомные файлы"""
        upload_info = {
            'total_dirs': 0,
            'total_files': 0,
            'custom_dirs': [],
            'suspicious_files': []
        }
        
        try:
            for root, dirs, files in os.walk(upload_directory):
                upload_info['total_dirs'] += len(dirs)
                upload_info['total_files'] += len(files)
                
                # Ищем подозрительные файлы (PHP, JS в upload)
                for file in files:
                    if file.endswith(('.php', '.js')):
                        rel_path = os.path.relpath(os.path.join(root, file), upload_directory)
                        upload_info['suspicious_files'].append(rel_path)
                
                # Ищем кастомные директории
                for dir_name in dirs:
                    if dir_name.startswith('custom_') or dir_name.startswith('my_'):
                        rel_path = os.path.relpath(os.path.join(root, dir_name), upload_directory)
                        upload_info['custom_dirs'].append(rel_path)
            
            # Ограничиваем количество элементов
            for key in ['custom_dirs', 'suspicious_files']:
                if len(upload_info[key]) > 10:
                    upload_info[key] = upload_info[key][:10] + ['... (truncated)']
        
        except Exception as e:
            upload_info['error'] = str(e)
        
        return upload_info
    
    def _scan_template_customizations(self, templates_directory):
        """Сканирует шаблоны на модификации"""
        template_info = {
            'total_templates': 0,
            'modified_templates': [],
            'custom_files': []
        }
        
        try:
            for template_name in os.listdir(templates_directory):
                template_path = os.path.join(templates_directory, template_name)
                if not os.path.isdir(template_path):
                    continue
                
                template_info['total_templates'] += 1
                
                # Ищем модификации в шаблонах
                for root, dirs, files in os.walk(template_path):
                    for file in files:
                        if file.startswith('custom_') or file.startswith('my_'):
                            rel_path = os.path.relpath(os.path.join(root, file), templates_directory)
                            template_info['custom_files'].append(rel_path)
                        
                        # Проверяем на модификации стандартных файлов
                        if file in ['header.php', 'footer.php'] and 'custom' in open(os.path.join(root, file), 'r', encoding='utf-8', errors='ignore').read().lower():
                            template_info['modified_templates'].append(f"{template_name}/{file}")
            
            # Ограничиваем количество элементов
            for key in ['modified_templates', 'custom_files']:
                if len(template_info[key]) > 10:
                    template_info[key] = template_info[key][:10] + ['... (truncated)']
        
        except Exception as e:
            template_info['error'] = str(e)
        
        return template_info
    
    def save_report(self, filename='bitrix_inspection_report.json'):
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
        print("\n" + "="*50)
        print("📋 СВОДКА ИНСПЕКЦИИ")
        print("="*50)
        
        print(f"🕒 Время: {self.report['timestamp']}")
        print(f"🖥️  Хост: {self.report['hostname']}")
        print(f"🐧 ОС: {self.report['system_info'].get('os', 'unknown')}")
        
        if self.report['bitrix_info'].get('main_path'):
            print(f"📁 Путь Bitrix24: {self.report['bitrix_info']['main_path']}")
            if self.report['bitrix_info'].get('version'):
                print(f"📦 Версия: {self.report['bitrix_info']['version']}")
        else:
            print("❌ Bitrix24 не найден")
        
        if self.report['php_info'].get('version'):
            print(f"🐘 PHP: {self.report['php_info']['version']}")
        
        if self.report['web_server'].get('apache'):
            print(f"🌐 Apache: {self.report['web_server']['apache']}")
        elif self.report['web_server'].get('nginx'):
            print(f"🌐 Nginx: {self.report['web_server']['nginx']}")
        
        # Информация о кастомизации
        customization_files = self.report.get('customization_files', {})
        existing_init_files = [path for path, info in customization_files.items() if info.get('type') == 'init_file' and info.get('exists')]
        missing_init_files = [path for path, info in customization_files.items() if info.get('type') == 'init_file' and not info.get('exists')]
        
        print(f"\n🔧 Файлы кастомизации:")
        if existing_init_files:
            print(f"   ✅ Найдены init.php: {len(existing_init_files)}")
            for file_path in existing_init_files:
                print(f"      - {file_path}")
        
        if missing_init_files:
            print(f"   ❌ Отсутствуют init.php: {len(missing_init_files)}")
            for file_path in missing_init_files:
                can_create = customization_files[file_path].get('can_create', {})
                if can_create.get('can_create'):
                    print(f"      - {file_path} (можно создать)")
                else:
                    print(f"      - {file_path} (нельзя создать)")
        
        # Информация о местах кастомизации
        customization_places = self.report.get('customization_places', {})
        existing_places = [path for path, info in customization_places.items() if info.get('exists') and info.get('recommended')]
        missing_places = [path for path, info in customization_places.items() if not info.get('exists') and info.get('recommended')]
        
        print(f"\n📁 Места для кастомизации:")
        if existing_places:
            print(f"   ✅ Существуют: {len(existing_places)}")
            for place in existing_places[:3]:  # Показываем первые 3
                print(f"      - {place}")
        
        if missing_places:
            print(f"   ⚠️  Отсутствуют: {len(missing_places)}")
            for place in missing_places[:3]:  # Показываем первые 3
                can_create = customization_places[place].get('can_create', {})
                if can_create.get('can_create'):
                    print(f"      - {place} (можно создать)")
                else:
                    print(f"      - {place} (нельзя создать)")
        
        # Информация о существующих кастомизациях
        existing_customizations = self.report.get('existing_customizations', {})
        if existing_customizations:
            print(f"\n🎨 Существующие кастомизации:")
            for location, info in existing_customizations.items():
                if isinstance(info, dict):
                    if 'php_files' in info and info['php_files']:
                        print(f"   📄 {location}: {len(info['php_files'])} PHP файлов")
                    if 'js_files' in info and info['js_files']:
                        print(f"   📄 {location}: {len(info['js_files'])} JS файлов")
                    if 'components' in info and info['components']:
                        print(f"   🔧 {location}: {len(info['components'])} компонентов")
                    if 'templates' in info and info['templates']:
                        print(f"   🎨 {location}: {len(info['templates'])} шаблонов")
        
        if self.report['errors']:
            print(f"\n⚠️  Ошибки ({len(self.report['errors'])}):")
            for error in self.report['errors'][:5]:
                print(f"   - {error}")
        
        print("\n✅ Инспекция завершена!")

def main():
    """Основная функция"""
    print("🔍 Bitrix24 Inspector - Сбор информации об установке")
    print("="*60)
    
    # Проверяем права
    if os.geteuid() != 0:
        print("⚠️  Рекомендуется запускать от имени root для полного доступа")
    
    inspector = BitrixInspector()
    
    # Собираем информацию
    inspector.collect_system_info()
    inspector.collect_bitrix_info()
    inspector.collect_web_server_info()
    inspector.collect_php_info()
    inspector.collect_file_structure()
    inspector.collect_templates_info()
    inspector.collect_permissions()
    inspector.collect_database_info()
    inspector.collect_customization_files()
    inspector.collect_customization_places()
    inspector.collect_existing_customizations()
    
    # Сохраняем и выводим сводку
    inspector.save_report()
    inspector.print_summary()
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 