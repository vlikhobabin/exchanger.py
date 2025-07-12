#!/usr/bin/env python3
"""
Мастер-скрипт для полной инспекции Bitrix24
Выполняет: отправка инспектора → запуск → получение отчета → анализ
"""

import sys
import subprocess
from pathlib import Path
import time

def run_script(script_name, description):
    """Запускает Python скрипт и возвращает код выхода"""
    script_path = Path(__file__).parent / script_name
    
    print(f"\n🚀 {description}")
    print("-" * 50)
    
    try:
        result = subprocess.run([sys.executable, str(script_path)], 
                              check=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при выполнении {script_name}: {e}")
        return False
    except FileNotFoundError:
        print(f"❌ Скрипт {script_name} не найден")
        return False

def check_prerequisites():
    """Проверяет наличие необходимых файлов"""
    print("🔍 Проверка предварительных требований...")
    
    # Файлы в корне проекта
    root_files = ['config.json']
    
    # Файлы в текущей папке (inspection-system/)
    local_files = [
        'bitrix_inspector.py',
        'send_inspector.py',
        'get_report.py'
    ]
    
    missing_files = []
    current_dir = Path(__file__).parent
    root_dir = current_dir.parent
    
    # Проверяем файлы в корне проекта
    for file_name in root_files:
        file_path = root_dir / file_name
        if not file_path.exists():
            missing_files.append(f"{file_name} (в корне проекта)")
    
    # Проверяем файлы в текущей папке
    for file_name in local_files:
        file_path = current_dir / file_name
        if not file_path.exists():
            missing_files.append(f"{file_name} (в папке inspection-system/)")
    
    if missing_files:
        print(f"❌ Отсутствуют файлы: {', '.join(missing_files)}")
        return False
    
    print("✅ Все необходимые файлы найдены")
    return True

def main():
    """Основная функция"""
    print("🔍 Полная инспекция Bitrix24")
    print("=" * 60)
    print("🎯 Этапы:")
    print("   1. Отправка и запуск инспектора на сервере")
    print("   2. Получение отчета с сервера")
    print("   3. Анализ результатов")
    print("=" * 60)
    
    # Проверяем предварительные требования
    if not check_prerequisites():
        print("\n❌ Не выполнены предварительные требования")
        print("💡 Убедитесь, что:")
        print("   - Файл config.json настроен правильно")
        print("   - Все скрипты инспектора присутствуют")
        print("   - Настроена аутентификация на сервере")
        return 1
    
    start_time = time.time()
    
    # Этап 1: Отправка и запуск инспектора
    if not run_script("send_inspector.py", "Этап 1: Отправка и запуск инспектора"):
        print("\n❌ Ошибка на этапе отправки инспектора")
        print("💡 Проверьте:")
        print("   - Подключение к серверу")
        print("   - Настройки аутентификации")
        print("   - Права доступа на сервере")
        return 1
    
    # Небольшая пауза перед получением отчета
    print("\n⏳ Пауза 3 секунды перед получением отчета...")
    time.sleep(3)
    
    # Этап 2: Получение отчета
    if not run_script("get_report.py", "Этап 2: Получение и анализ отчета"):
        print("\n❌ Ошибка при получении отчета")
        print("💡 Возможные причины:")
        print("   - Инспектор не завершил работу")
        print("   - Проблемы с правами на сервере")
        print("   - Отчет не был создан")
        return 1
    
    end_time = time.time()
    duration = int(end_time - start_time)
    
    print("\n" + "=" * 60)
    print("🎉 ИНСПЕКЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
    print("=" * 60)
    print(f"⏱️  Время выполнения: {duration} секунд")
    print("\n📋 Результаты:")
    print("   ✅ Инспектор выполнен на сервере")
    print("   ✅ Отчет получен и проанализирован")
    print("   📁 Файлы сохранены в папке reports/")
    
    print("\n📚 Следующие шаги:")
    print("   1. Изучите подробный отчет в формате JSON")
    print("   2. Ознакомьтесь с краткой сводкой")
    print("   3. Используйте полученную информацию для кастомизации")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 