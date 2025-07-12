#!/usr/bin/env python3
"""
Скрипт для развертывания блокировщика завершения задач на сервер Bitrix24
"""

import os
import sys
import json
import shutil
import subprocess
import datetime
from pathlib import Path

class TaskBlockerDeployer:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.modifications_dir = self.project_root / "modifications"
        self.config_file = self.project_root.parent / "config.json"
        self.deployment_map = [
            {
                "local_file": "task_completion_blocker.php",
                "remote_path": "/home/bitrix/www/local/php_interface/task_completion_blocker.php",
                "description": "PHP обработчик событий для блокировки завершения задач"
            },
            {
                "local_file": "init.php",
                "remote_path": "/home/bitrix/www/local/php_interface/init.php",
                "description": "Файл инициализации локальных модификаций",
                "backup_required": True
            },
            {
                "local_file": "enhanced_task_modifier.js",
                "remote_path": "/home/bitrix/www/local/templates/bitrix24/assets/js/enhanced_task_modifier.js",
                "description": "JavaScript модификатор интерфейса задач"
            },
            {
                "local_file": "task_modifier_connector.php",
                "remote_path": "/home/bitrix/www/local/templates/bitrix24/task_modifier_connector.php",
                "description": "Коннектор для безопасного подключения JavaScript к шаблону"
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
    
    def create_remote_directory(self, server_config, remote_path):
        """Создает удаленную директорию"""
        remote_dir = os.path.dirname(remote_path)
        command = f"mkdir -p {remote_dir}"
        
        return self._execute_remote_command(server_config, command)
    
    def _execute_remote_command(self, server_config, command):
        """Выполняет команду на удаленном сервере"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._execute_with_key(server_config, command)
        else:
            return self._execute_with_password(server_config, command)
    
    def _execute_with_key(self, server_config, command):
        """Выполняет команду с использованием ключа"""
        key_file = server_config.get('key_file')
        if not key_file:
            return False
        
        if os.path.isabs(key_file):
            key_path = Path(key_file)
        else:
            key_path = self.project_root.parent / key_file
        
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
    
    def _execute_with_password(self, server_config, command):
        """Выполняет команду с использованием пароля"""
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
    
    def deploy_file(self, server_config, file_info):
        """Развертывает один файл на сервер"""
        local_file = self.modifications_dir / file_info['local_file']
        remote_path = file_info['remote_path']
        
        if not local_file.exists():
            print(f"❌ Локальный файл не найден: {local_file}")
            return False
        
        print(f"📤 Развертывание: {file_info['local_file']} -> {remote_path}")
        
        # Создаем удаленную директорию
        if not self.create_remote_directory(server_config, remote_path):
            print(f"⚠️  Не удалось создать удаленную директорию для {remote_path}")
        
        # Копируем файл
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            success = self._deploy_with_key(server_config, local_file, remote_path)
        else:
            success = self._deploy_with_password(server_config, local_file, remote_path)
        
        if success:
            print(f"✅ Успешно развернут: {file_info['local_file']}")
            return True
        else:
            print(f"❌ Не удалось развернуть: {file_info['local_file']}")
            return False
    
    def _deploy_with_key(self, server_config, local_file, remote_path):
        """Развертывание с использованием ключа"""
        key_file = server_config.get('key_file')
        if not key_file:
            return False
        
        if os.path.isabs(key_file):
            key_path = Path(key_file)
        else:
            key_path = self.project_root.parent / key_file
        
        if not key_path.exists():
            return False
        
        # Проверяем, есть ли pscp
        pscp_cmd = shutil.which('pscp')
        if pscp_cmd and key_path.suffix.lower() == '.ppk':
            cmd = [
                "pscp",
                "-i", str(key_path),
                "-batch",
                str(local_file),
                f"{server_config['user']}@{server_config['host']}:{remote_path}"
            ]
        else:
            if key_path.suffix.lower() == '.ppk':
                return False
            
            cmd = [
                "scp",
                "-i", str(key_path),
                "-o", "StrictHostKeyChecking=no",
                str(local_file),
                f"{server_config['user']}@{server_config['host']}:{remote_path}"
            ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"   Ошибка: {e.stderr}")
            return False
        except FileNotFoundError:
            print("   Ошибка: Команда scp/pscp не найдена")
            return False
    
    def _deploy_with_password(self, server_config, local_file, remote_path):
        """Развертывание с использованием пароля"""
        cmd = [
            "scp",
            str(local_file),
            f"{server_config['user']}@{server_config['host']}:{remote_path}"
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"   Ошибка: {e.stderr}")
            return False
        except FileNotFoundError:
            print("   Ошибка: Команда scp не найдена")
            return False
    
    def set_file_permissions(self, server_config, remote_path, permissions='644'):
        """Устанавливает права доступа на файл"""
        command = f"chmod {permissions} {remote_path}"
        
        if self._execute_remote_command(server_config, command):
            print(f"✅ Права доступа установлены: {remote_path} ({permissions})")
            return True
        else:
            print(f"⚠️  Не удалось установить права доступа: {remote_path}")
            return False
    
    def deploy_all(self):
        """Развертывает все файлы блокировщика задач"""
        print("🚀 Развертывание блокировщика завершения задач на сервер Bitrix24")
        print("=" * 70)
        
        # Загружаем конфигурацию
        config = self.load_config()
        if not config:
            return False
        
        server_config = config['server']
        print(f"🎯 Сервер: {server_config['user']}@{server_config['host']}")
        print(f"🔐 Аутентификация: {server_config.get('auth_method', 'password')}")
        print("-" * 70)
        
        # Создаем резервную копию перед развертыванием
        print("📦 Создание резервной копии...")
        backup_script = self.project_root.parent / "backup-restore-system" / "backup_manager.py"
        if backup_script.exists():
            try:
                subprocess.run([sys.executable, str(backup_script), "create"], check=True)
                print("✅ Резервная копия создана")
            except subprocess.CalledProcessError:
                print("⚠️  Не удалось создать резервную копию")
        
        # Развертываем файлы
        successful_deployments = 0
        failed_deployments = 0
        
        for file_info in self.deployment_map:
            print(f"\n📁 {file_info['description']}")
            
            if self.deploy_file(server_config, file_info):
                # Устанавливаем права доступа
                if file_info['local_file'].endswith('.php'):
                    self.set_file_permissions(server_config, file_info['remote_path'], '644')
                elif file_info['local_file'].endswith('.js'):
                    self.set_file_permissions(server_config, file_info['remote_path'], '644')
                
                successful_deployments += 1
            else:
                failed_deployments += 1
        
        # Подключаем JavaScript файл к шаблону
        if successful_deployments > 0:
            print(f"\n🔗 Подключение JavaScript к шаблону...")
            js_success = self.inject_javascript_to_template(server_config)
            if not js_success:
                print("⚠️  Не удалось подключить JavaScript к шаблону")
                print("💡 Файлы развернуты, но JavaScript нужно подключить вручную")
        
        # Результат
        print(f"\n" + "=" * 70)
        print(f"📊 Результат развертывания:")
        print(f"   ✅ Успешно развернуто: {successful_deployments} файлов")
        print(f"   ❌ Не удалось развернуть: {failed_deployments} файлов")
        
        if successful_deployments > 0:
            print(f"\n🎉 Блокировщик задач успешно развернут!")
            print(f"📋 Следующие шаги:")
            print(f"   1. Проверьте работоспособность в интерфейсе Bitrix24")
            print(f"   2. Создайте тестовую задачу с полем 'Ожидается результат = Да'")
            print(f"   3. Попробуйте завершить задачу без заполнения ответа")
            print(f"   4. Проверьте логи в /bitrix/logs/")
        else:
            print(f"\n❌ Развертывание не удалось")
        
        return successful_deployments > 0
    
    def inject_javascript_to_template(self, server_config):
        """
        Безопасно подключает JavaScript файл к шаблону
        ИСПРАВЛЕНО: Теперь использует безопасный подход через коннектор
        """
        print("🔗 Безопасное подключение JavaScript к шаблону...")
        
        # Путь к файлу header.php
        header_path = "/home/bitrix/www/local/templates/bitrix24/header.php"
        connector_path = "/home/bitrix/www/local/templates/bitrix24/task_modifier_connector.php"
        
        # Шаг 1: Создаем резервную копию header.php ДО изменения (если существует)
        if self._check_file_exists(server_config, header_path):
            print("📦 Создание резервной копии header.php...")
            backup_success = self._backup_header_file(server_config, header_path)
            
            if not backup_success:
                print("⚠️  Не удалось создать резервную копию header.php")
        
        # Шаг 2: Проверяем существование header.php
        header_exists = self._check_file_exists(server_config, header_path)
        
        if header_exists:
            # Шаг 3: Проверяем, не подключен ли уже коннектор
            if self._is_connector_already_included(server_config, header_path):
                print("ℹ️  JavaScript коннектор уже подключен к шаблону")
                return True
            
            # Шаг 4: Добавляем подключение коннектора к существующему файлу
            return self._add_connector_to_existing_header(server_config, header_path, connector_path)
        else:
            # Шаг 5: Создаем новый header.php с коннектором
            return self._create_new_header_with_connector(server_config, header_path, connector_path)
    
    def _backup_header_file(self, server_config, header_path):
        """Создает резервную копию header.php"""
        backup_path = header_path + ".backup_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        copy_command = f"cp '{header_path}' '{backup_path}' 2>/dev/null || true"
        
        success, output = self._execute_remote_command_with_output(server_config, copy_command)
        
        if success:
            print(f"✅ Резервная копия создана: {backup_path}")
            return True
        else:
            print(f"⚠️  Не удалось создать резервную копию: {header_path}")
            return False
    
    def _check_file_exists(self, server_config, file_path):
        """Проверяет существование файла на сервере"""
        check_command = f"test -f '{file_path}'"
        return self._execute_remote_command(server_config, check_command)
    
    def _is_connector_already_included(self, server_config, header_path):
        """Проверяет, подключен ли уже коннектор"""
        check_command = f"grep -q 'task_modifier_connector.php' '{header_path}' 2>/dev/null"
        return self._execute_remote_command(server_config, check_command)
    
    def _add_connector_to_existing_header(self, server_config, header_path, connector_path):
        """Добавляет подключение коннектора к существующему header.php"""
        add_connector_command = f"""
# Добавляем подключение коннектора к существующему header.php
echo '' >> '{header_path}'
echo '<?php' >> '{header_path}'
echo '// Подключение модификатора задач через безопасный коннектор' >> '{header_path}'
echo 'require_once(__DIR__ . "/task_modifier_connector.php");' >> '{header_path}'
echo '?>' >> '{header_path}'
"""
        
        success, output = self._execute_remote_command_with_output(server_config, add_connector_command)
        
        if success:
            print("✅ Коннектор добавлен к существующему header.php")
            return True
        else:
            print(f"❌ Не удалось добавить коннектор: {output}")
            return False
    
    def _create_new_header_with_connector(self, server_config, header_path, connector_path):
        """Создает новый header.php с подключением коннектора"""
        # Создаем директорию если её нет
        create_dir_command = f"mkdir -p '{os.path.dirname(header_path)}'"
        self._execute_remote_command(server_config, create_dir_command)
        
        # Создаем новый header.php
        create_header_command = f"""
cat > '{header_path}' << 'EOF'
<?php
/**
 * Заголовок локального шаблона Bitrix24
 * Создан автоматически системой блокировки задач
 */

// Подключение модификатора задач через безопасный коннектор
require_once(__DIR__ . "/task_modifier_connector.php");
?>
EOF
"""
        
        success, output = self._execute_remote_command_with_output(server_config, create_header_command)
        
        if success:
            print("✅ Создан новый header.php с подключением коннектора")
            return True
        else:
            print(f"❌ Не удалось создать header.php: {output}")
            return False
    
    def _execute_remote_command_with_output(self, server_config, command):
        """Выполняет команду на удаленном сервере и возвращает результат и вывод"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._execute_with_key_and_output(server_config, command)
        else:
            return self._execute_with_password_and_output(server_config, command)
    
    def _execute_with_key_and_output(self, server_config, command):
        """Выполняет команду с ключом и возвращает результат"""
        key_file = server_config.get('key_file')
        if not key_file:
            return False, "No key file specified"
        
        if os.path.isabs(key_file):
            key_path = Path(key_file)
        else:
            key_path = self.project_root.parent / key_file
        
        if not key_path.exists():
            return False, f"Key file not found: {key_path}"
        
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
            if key_path.suffix.lower() == '.ppk':
                return False, "PPK key requires PuTTY utilities"
            
            cmd = [
                'ssh',
                '-i', str(key_path),
                '-o', 'StrictHostKeyChecking=no',
                f"{server_config['user']}@{server_config['host']}",
                command
            ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timeout"
        except Exception as e:
            return False, str(e)
    
    def _execute_with_password_and_output(self, server_config, command):
        """Выполняет команду с паролем и возвращает результат"""
        cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            f"{server_config['user']}@{server_config['host']}",
            command
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30)
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timeout"
        except Exception as e:
            return False, str(e)
    
    def test_deployment(self):
        """Тестирует развертывание"""
        print("🧪 Тестирование развертывания...")
        
        config = self.load_config()
        if not config:
            return False
        
        server_config = config['server']
        
        # Проверяем доступность файлов
        test_commands = [
            "ls -la /home/bitrix/www/local/php_interface/task_completion_blocker.php",
            "ls -la /home/bitrix/www/local/php_interface/init.php",
            "ls -la /home/bitrix/www/local/templates/bitrix24/assets/js/enhanced_task_modifier.js"
        ]
        
        print("📋 Проверка развернутых файлов:")
        for cmd in test_commands:
            if self._execute_remote_command(server_config, cmd):
                print(f"   ✅ {cmd.split('/')[-1]}")
            else:
                print(f"   ❌ {cmd.split('/')[-1]}")
        
        # Проверяем синтаксис PHP
        php_check = "php -l /home/bitrix/www/local/php_interface/task_completion_blocker.php"
        if self._execute_remote_command(server_config, php_check):
            print("   ✅ Синтаксис PHP корректен")
        else:
            print("   ⚠️  Проблемы с синтаксисом PHP")
        
        return True

def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python deploy_task_blocker.py deploy  - развернуть все файлы")
        print("  python deploy_task_blocker.py test    - протестировать развертывание")
        return 1
    
    deployer = TaskBlockerDeployer()
    
    command = sys.argv[1].lower()
    
    if command == "deploy":
        success = deployer.deploy_all()
        return 0 if success else 1
    elif command == "test":
        success = deployer.test_deployment()
        return 0 if success else 1
    else:
        print("❌ Неизвестная команда")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 