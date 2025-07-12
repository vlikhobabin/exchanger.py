#!/usr/bin/env python3
"""
Скрипт для полного восстановления оригинального состояния Bitrix24
Удаляет все файлы блокировщика задач и восстанавливает оригинальные файлы
"""

import sys
import json
from pathlib import Path
import subprocess
import time

class SystemRestorer:
    def __init__(self):
        self.project_root = Path(__file__).parent
        
    def load_config(self):
        """Загружает конфигурацию сервера"""
        config_path = self.project_root.parent / "config.json"
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Ошибка загрузки конфигурации: {e}")
            return None
    
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
            return False, "No key file specified"
        
        if Path(key_file).is_absolute():
            key_path = Path(key_file)
        else:
            key_path = self.project_root.parent / key_file
        
        if not key_path.exists():
            return False, f"Key file not found: {key_path}"
        
        # Проверяем, есть ли plink
        import shutil
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
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
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
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timeout"
        except Exception as e:
            return False, str(e)
    
    def remove_our_files(self, server_config):
        """Удаляет все файлы блокировщика задач"""
        print("🗑️ Удаление файлов блокировщика задач...")
        
        files_to_remove = [
            "/home/bitrix/www/local/php_interface/task_completion_blocker.php",
            "/home/bitrix/www/local/php_interface/init.php",
            "/home/bitrix/www/local/templates/bitrix24/assets/js/enhanced_task_modifier.js"
        ]
        
        remove_command = f"""
# Удаляем наши файлы
echo "🗑️ Удаление файлов блокировщика задач..."
for file in {' '.join(files_to_remove)}; do
    if [ -f "$file" ]; then
        rm -f "$file"
        echo "✅ Удален: $file"
    else
        echo "ℹ️ Файл не существует: $file"
    fi
done

# Удаляем подключение JavaScript из шаблона
echo ""
echo "🔗 Удаление подключения JavaScript..."
template_file="/home/bitrix/www/local/templates/bitrix24/header.php"
if [ -f "$template_file" ]; then
    # Удаляем строку с нашим JS
    sed -i '/enhanced_task_modifier.js/d' "$template_file"
    echo "✅ JavaScript отключен от шаблона"
else
    echo "ℹ️ Файл шаблона не найден: $template_file"
fi

echo ""
echo "✅ Все файлы блокировщика удалены"
        """
        
        success, output = self._execute_remote_command(server_config, remove_command)
        
        if success:
            print("✅ Файлы блокировщика удалены")
            print(output)
            return True
        else:
            print("❌ Ошибка при удалении файлов")
            print(output)
            return False
    
    def restore_original_files(self, server_config):
        """Восстанавливает оригинальные файлы из backup"""
        print("📦 Восстановление оригинальных файлов...")
        
        # Ищем самый последний backup с файлами
        backup_dirs = sorted([d for d in (self.project_root / "backups").iterdir() if d.is_dir()], reverse=True)
        
        restored_files = 0
        
        for backup_dir in backup_dirs:
            backup_info_file = backup_dir / "backup_info.json"
            if not backup_info_file.exists():
                continue
            
            try:
                with open(backup_info_file, 'r', encoding='utf-8') as f:
                    backup_info = json.load(f)
                
                for file_info in backup_info.get('files', []):
                    if file_info.get('status') == 'success':
                        local_backup_file = backup_dir / file_info['local_path']
                        remote_path = file_info['remote_path']
                        
                        if local_backup_file.exists():
                            print(f"📥 Восстановление: {remote_path}")
                            
                            # Копируем файл обратно на сервер
                            restore_command = f"""
# Создаем директорию если нужно
mkdir -p "$(dirname "{remote_path}")"

# Копируем файл
cat > "{remote_path}" << 'EOF'
$(cat "{local_backup_file}")
EOF

echo "✅ Восстановлен: {remote_path}"
                            """
                            
                            # Читаем содержимое backup файла
                            with open(local_backup_file, 'r', encoding='utf-8') as f:
                                file_content = f.read()
                            
                            # Заменяем placeholder на реальное содержимое
                            restore_command = restore_command.replace(f'$(cat "{local_backup_file}")', file_content)
                            
                            success, output = self._execute_remote_command(server_config, restore_command)
                            
                            if success:
                                print(f"✅ Восстановлен: {remote_path}")
                                restored_files += 1
                            else:
                                print(f"❌ Ошибка восстановления: {remote_path}")
                                print(output)
                
            except Exception as e:
                print(f"❌ Ошибка чтения backup: {e}")
                continue
        
        print(f"📦 Восстановлено файлов: {restored_files}")
        return restored_files > 0
    
    def verify_restoration(self, server_config):
        """Проверяет успешность восстановления"""
        print("🔍 Проверка восстановления...")
        
        check_command = """
echo "=== Проверка состояния системы ==="
echo ""

# Проверяем, что наших файлов нет
echo "🔍 Проверка удаления наших файлов:"
our_files=(
    "/home/bitrix/www/local/php_interface/task_completion_blocker.php"
    "/home/bitrix/www/local/php_interface/init.php"
    "/home/bitrix/www/local/templates/bitrix24/assets/js/enhanced_task_modifier.js"
)

for file in "${our_files[@]}"; do
    if [ -f "$file" ]; then
        echo "⚠️ Файл все еще существует: $file"
    else
        echo "✅ Файл удален: $file"
    fi
done

echo ""
echo "🔍 Проверка подключения JavaScript:"
if grep -q "enhanced_task_modifier.js" /home/bitrix/www/local/templates/bitrix24/header.php 2>/dev/null; then
    echo "⚠️ JavaScript все еще подключен в шаблоне"
else
    echo "✅ JavaScript отключен от шаблона"
fi

echo ""
echo "🔍 Проверка структуры папок:"
echo "📁 /home/bitrix/www/local/php_interface/:"
ls -la /home/bitrix/www/local/php_interface/ 2>/dev/null || echo "Папка не существует"

echo ""
echo "📁 /home/bitrix/www/bitrix/php_interface/:"
ls -la /home/bitrix/www/bitrix/php_interface/ | head -5

echo ""
echo "✅ Проверка завершена"
        """
        
        success, output = self._execute_remote_command(server_config, check_command)
        
        if success:
            print("✅ Проверка выполнена")
            print(output)
            return True
        else:
            print("❌ Ошибка при проверке")
            print(output)
            return False
    
    def full_restore(self):
        """Выполняет полное восстановление системы"""
        print("🔄 ПОЛНОЕ ВОССТАНОВЛЕНИЕ СИСТЕМЫ BITRIX24")
        print("=" * 60)
        
        config = self.load_config()
        if not config:
            return False
        
        server_config = config['server']
        print(f"🎯 Сервер: {server_config['user']}@{server_config['host']}")
        print("-" * 60)
        
        steps = [
            ("Удаление файлов блокировщика", self.remove_our_files),
            ("Восстановление оригинальных файлов", self.restore_original_files),
            ("Проверка восстановления", self.verify_restoration)
        ]
        
        for step_name, step_function in steps:
            print(f"\n📋 {step_name}")
            try:
                if not step_function(server_config):
                    print(f"❌ Ошибка на этапе: {step_name}")
                    return False
            except Exception as e:
                print(f"❌ Исключение на этапе {step_name}: {e}")
                return False
        
        print("\n" + "=" * 60)
        print("🎉 ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО!")
        print("✅ Система Bitrix24 возвращена в исходное состояние")
        print("✅ Все файлы блокировщика удалены")
        print("✅ Оригинальные файлы восстановлены")
        print("\nТеперь можно проверить, исчезла ли ошибка в Bitrix24.")
        return True

def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python restore_manager.py list          - список резервных копий")
        print("  python restore_manager.py restore <name> - восстановить из резервной копии")
        print("  python restore_manager.py full          - полное восстановление системы")
        return 1
    
    restorer = SystemRestorer()
    
    command = sys.argv[1].lower()
    
    if command == "list":
        # Список резервных копий (переиспользуем из backup_manager)
        from backup_manager import BitrixBackupManager
        backup_manager = BitrixBackupManager()
        backup_manager.list_backups()
        return 0
    elif command == "restore" and len(sys.argv) > 2:
        backup_name = sys.argv[2]
        print(f"🔄 Восстановление из резервной копии: {backup_name}")
        # TODO: Реализовать восстановление из конкретной резервной копии
        print("ℹ️  Эта функция будет реализована в следующих версиях")
        return 0
    elif command == "full":
        print("⚠️  ВНИМАНИЕ: Этот скрипт удалит ВСЕ файлы блокировщика задач!")
        print("⚠️  Система будет возвращена в состояние ДО установки блокировщика.")
        print()
        
        # Запрашиваем подтверждение
        while True:
            confirm = input("Продолжить восстановление? (yes/no): ").lower().strip()
            if confirm in ['yes', 'y', 'да']:
                break
            elif confirm in ['no', 'n', 'нет']:
                print("❌ Восстановление отменено")
                return 1
            else:
                print("Пожалуйста, введите 'yes' или 'no'")
        
        print("\n🔄 Начинаю восстановление...")
        time.sleep(2)  # Небольшая пауза для осознания
        
        success = restorer.full_restore()
        return 0 if success else 1
    else:
        print("❌ Неизвестная команда")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 