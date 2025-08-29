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
                "description": "JavaScript модификатор интерфейса задач (подключается напрямую через footer.php)"
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
    
    def copy_system_template(self, server_config):
        """
        Копирует системный шаблон bitrix24 в local для кастомизации
        КРИТИЧЕСКИ ВАЖНО: Этот шаг необходим перед любыми модификациями!
        """
        print("🔄 Копирование системного шаблона bitrix24 в local...")
        print("-" * 50)
        
        system_template_path = "/home/bitrix/www/bitrix/templates/bitrix24"
        local_template_path = "/home/bitrix/www/local/templates/bitrix24"
        
        # Проверяем, существует ли системный шаблон
        if not self._check_template_exists(server_config, system_template_path):
            print(f"❌ Системный шаблон не найден: {system_template_path}")
            print("💡 Возможные варианты:")
            print("   - Используется другой шаблон")
            print("   - Шаблон находится в другой папке")
            print("   - Нестандартная установка Bitrix24")
            return False
        
        # Проверяем, есть ли уже локальная копия
        if self._check_template_exists(server_config, local_template_path):
            print(f"ℹ️  Локальная копия шаблона уже существует: {local_template_path}")
            
            # Проверяем, есть ли footer.php для модификаций
            footer_path = f"{local_template_path}/footer.php"
            if self._check_file_exists(server_config, footer_path):
                print("✅ footer.php найден - готов для модификаций")
            else:
                print("⚠️  footer.php не найден - создаем из системного шаблона")
                if not self._copy_footer_from_system(server_config, system_template_path, local_template_path):
                    print("❌ Не удалось скопировать footer.php")
                    return False
            
            return True
        
        # Копируем системный шаблон
        print(f"📂 Копирование {system_template_path} → {local_template_path}")
        
        copy_command = f"""
        # Создаем директорию local/templates если её нет
        mkdir -p /home/bitrix/www/local/templates
        
        # Копируем системный шаблон
        cp -r {system_template_path} {local_template_path}
        
        # Устанавливаем права доступа
        chown -R bitrix:bitrix {local_template_path}
        chmod -R 755 {local_template_path}
        
        # Проверяем успешность копирования
        test -f {local_template_path}/footer.php && echo "SUCCESS" || echo "FAILED"
        """
        
        success, output = self._execute_remote_command_with_output(server_config, copy_command)
        
        if success and "SUCCESS" in output:
            print("✅ Системный шаблон успешно скопирован в local")
            print(f"📁 Создана структура: {local_template_path}")
            print("🎯 Теперь можно безопасно модифицировать footer.php")
            return True
        else:
            print(f"❌ Не удалось скопировать системный шаблон: {output}")
            return False
    
    def _copy_footer_from_system(self, server_config, system_path, local_path):
        """Копирует footer.php из системного шаблона в локальный"""
        copy_command = f"cp {system_path}/footer.php {local_path}/footer.php"
        
        if self._execute_remote_command(server_config, copy_command):
            print("✅ footer.php скопирован из системного шаблона")
            return True
        else:
            print("❌ Не удалось скопировать footer.php")
            return False
    
    def _check_template_exists(self, server_config, template_path):
        """Проверяет существование шаблона"""
        check_command = f"test -d '{template_path}' && test -f '{template_path}/footer.php'"
        return self._execute_remote_command(server_config, check_command)
    
    def _check_file_exists(self, server_config, file_path):
        """Проверяет существование файла"""
        check_command = f"test -f '{file_path}'"
        return self._execute_remote_command(server_config, check_command)
    
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
    
    def _execute_remote_command_with_output(self, server_config, command):
        """Выполняет команду на удаленном сервере и возвращает результат и вывод"""
        auth_method = server_config.get('auth_method', 'password')
        
        if auth_method == 'key':
            return self._execute_with_key_and_output(server_config, command)
        else:
            return self._execute_with_password_and_output(server_config, command)
    
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
        
        # КРИТИЧЕСКИ ВАЖНО: Копирование системного шаблона
        print("\n" + "=" * 70)
        print("🔄 ЭТАП 1: Подготовка шаблона для модификаций")
        print("=" * 70)
        
        if not self.copy_system_template(server_config):
            print("❌ Не удалось подготовить шаблон для модификаций")
            print("💡 Без локального шаблона нельзя безопасно модифицировать footer.php")
            return False
        
        # Развертываем файлы
        print("\n" + "=" * 70)
        print("📂 ЭТАП 2: Развертывание файлов блокировщика")
        print("=" * 70)
        
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
            print(f"   5. Подключите JavaScript вручную через footer.php")
            print(f"      <script src=\"/local/templates/bitrix24/assets/js/enhanced_task_modifier.js\"></script>")
        else:
            print(f"\n❌ Развертывание не удалось")
        
        return successful_deployments > 0
    
    def test_deployment(self):
        """Тестирует развертывание"""
        print("🧪 Тестирование развертывания...")
        
        config = self.load_config()
        if not config:
            return False
        
        server_config = config['server']
        
        # Проверяем локальный шаблон
        print("📋 Проверка локального шаблона:")
        template_check = "test -d /home/bitrix/www/local/templates/bitrix24 && echo 'EXISTS' || echo 'NOT_FOUND'"
        success, output = self._execute_remote_command_with_output(server_config, template_check)
        if success and "EXISTS" in output:
            print("   ✅ Локальный шаблон bitrix24 найден")
        else:
            print("   ❌ Локальный шаблон bitrix24 НЕ найден")
            print("   💡 Необходимо скопировать системный шаблон в local")
        
        # Проверяем доступность файлов
        test_commands = [
            "ls -la /home/bitrix/www/local/php_interface/task_completion_blocker.php",
            "ls -la /home/bitrix/www/local/php_interface/init.php",
            "ls -la /home/bitrix/www/local/templates/bitrix24/assets/js/enhanced_task_modifier.js"
        ]
        
        print("\n📋 Проверка развернутых файлов:")
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
        
        # Напоминание о подключении JavaScript
        print("\n📝 Напоминание:")
        print("   ⚠️  Не забудьте подключить JavaScript вручную через footer.php:")
        print("   <script src=\"/local/templates/bitrix24/assets/js/enhanced_task_modifier.js\"></script>")
        
        return True

def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python deploy_task_blocker.py deploy  - развернуть все файлы")
        print("  python deploy_task_blocker.py test    - протестировать развертывание")
        print("  python deploy_task_blocker.py template - только скопировать системный шаблон")
        return 1
    
    deployer = TaskBlockerDeployer()
    
    command = sys.argv[1].lower()
    
    if command == "deploy":
        success = deployer.deploy_all()
        return 0 if success else 1
    elif command == "test":
        success = deployer.test_deployment()
        return 0 if success else 1
    elif command == "template":
        config = deployer.load_config()
        if config:
            success = deployer.copy_system_template(config['server'])
            return 0 if success else 1
        return 1
    else:
        print("❌ Неизвестная команда")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 