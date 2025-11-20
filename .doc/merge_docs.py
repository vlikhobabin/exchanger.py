#!/usr/bin/env python3
"""
Скрипт для объединения всех markdown файлов из каталога .doc в единый файл.
Между файлами добавляется разделитель.
"""

import os
from pathlib import Path

def merge_doc_files():
    """Объединяет все файлы из .doc в один markdown файл."""
    
    # Определяем пути
    doc_dir = Path(__file__).parent / '.doc'
    output_file = Path(__file__).parent / 'merged_documentation.md'
    
    # Проверяем существование каталога
    if not doc_dir.exists():
        print(f"Ошибка: каталог {doc_dir} не найден")
        return
    
    # Получаем все .md файлы и сортируем по имени
    md_files = sorted(doc_dir.glob('*.md'))
    
    if not md_files:
        print(f"Ошибка: в каталоге {doc_dir} не найдено markdown файлов")
        return
    
    print(f"Найдено {len(md_files)} файлов для объединения")
    
    # Разделитель между файлами
    separator = "\n\n---\n\n"
    
    # Объединяем файлы
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for i, md_file in enumerate(md_files):
            print(f"Обработка: {md_file.name}")
            
            try:
                with open(md_file, 'r', encoding='utf-8') as infile:
                    content = infile.read()
                    
                    # Добавляем заголовок с именем файла
                    outfile.write(f"# {md_file.stem}\n\n")
                    outfile.write(content)
                    
                    # Добавляем разделитель после каждого файла, кроме последнего
                    if i < len(md_files) - 1:
                        outfile.write(separator)
                        
            except Exception as e:
                print(f"Ошибка при чтении файла {md_file.name}: {e}")
                continue
    
    print(f"\nГотово! Объединенный файл сохранен: {output_file}")
    print(f"Размер файла: {output_file.stat().st_size / 1024:.2f} KB")

if __name__ == '__main__':
    merge_doc_files()

