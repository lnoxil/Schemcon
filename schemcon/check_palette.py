#!/usr/bin/env python3
"""
Диагностика палитры .schem файла
Показывает какие блоки вызывают NullPointerException в FAWE
"""

import sys
import nbtlib
from pathlib import Path


def check_palette(schem_path):
    """Проверяет палитру на проблемные блоки."""
    print(f"\n🔍 Проверка файла: {schem_path}")
    print("=" * 60)
    
    try:
        # Загружаем NBT
        nbt = nbtlib.load(schem_path)
        
        # Получаем root
        if hasattr(nbt, 'root'):
            root = nbt.root
        elif isinstance(nbt, dict):
            root = nbt.get('') or nbt
        else:
            root = nbt
        
        # Ищем палитру
        palette = root.get('Palette')
        if not palette:
            print("❌ Палитра не найдена!")
            return
        
        print(f"\n📊 Найдено блоков в палитре: {len(palette)}")
        print("-" * 60)
        
        problems = []
        air_found = False
        
        for block_name, index in sorted(palette.items(), key=lambda x: int(x[1])):
            index_int = int(index)
            block_str = str(block_name)
            
            # Проверки
            issues = []
            
            # 1. Проверка на air
            if 'air' in block_str.lower():
                air_found = True
                if index_int != 0:
                    issues.append(f"⚠️  ВОЗДУХ НЕ В ИНДЕКСЕ 0! (индекс: {index_int})")
            
            # 2. Проверка формата имени
            if ':' not in block_str:
                issues.append("❌ Нет namespace (minecraft:)")
            
            # 3. Проверка на спецсимволы
            base_name = block_str.split('[')[0]
            if not base_name.replace(':', '').replace('_', '').replace('-', '').replace('.', '').replace('/', '').isalnum():
                issues.append(f"❌ Невалидные символы в имени")
            
            # 4. Проверка на пустое имя
            if not block_str or block_str.strip() == '':
                issues.append("❌ ПУСТОЕ ИМЯ!")
            
            # 5. Проверка properties
            if '[' in block_str:
                if not block_str.endswith(']'):
                    issues.append("❌ Незакрытые properties")
            
            # Вывод
            status = "✅" if not issues else "🔴"
            print(f"{status} [{index_int:4d}] {block_str}")
            
            if issues:
                for issue in issues:
                    print(f"         {issue}")
                problems.append((index_int, block_str, issues))
        
        # Итоги
        print("\n" + "=" * 60)
        print(f"📈 ИТОГИ:")
        print(f"   Всего блоков: {len(palette)}")
        print(f"   Проблемных: {len(problems)}")
        print(f"   Воздух найден: {'✅ Да' if air_found else '❌ НЕТ!'}")
        
        if not air_found:
            print("\n🔥 КРИТИЧНО: В палитре НЕТ minecraft:air!")
            print("   Это вызовет NullPointerException в FAWE!")
        
        if problems:
            print(f"\n🔴 ПРОБЛЕМНЫЕ БЛОКИ ({len(problems)}):")
            print("-" * 60)
            for idx, name, issues in problems[:10]:  # Показываем первые 10
                print(f"   [{idx}] {name}")
                for issue in issues:
                    print(f"       → {issue}")
            
            if len(problems) > 10:
                print(f"   ... и ещё {len(problems) - 10} проблемных блоков")
        
        # Проверка BlockData
        block_data = root.get('BlockData')
        if block_data:
            print(f"\n📦 BlockData: {len(block_data)} байт")
        
        # Проверка Version
        version = root.get('Version')
        if version:
            print(f"📌 Sponge Version: {int(version)}")
        
        # Проверка DataVersion  
        data_version = root.get('DataVersion')
        if data_version:
            print(f"🎮 Minecraft DataVersion: {int(data_version)}")
        
        # Рекомендации
        if problems or not air_found:
            print("\n" + "=" * 60)
            print("💡 РЕКОМЕНДАЦИИ:")
            print("=" * 60)
            
            if not air_found:
                print("1. Добавить minecraft:air в индекс 0")
            
            if any('namespace' in str(i) for _, _, issues in problems for i in issues):
                print("2. Добавить 'minecraft:' к блокам без namespace")
            
            if any('символы' in str(i) for _, _, issues in problems for i in issues):
                print("3. Удалить невалидные блоки или заменить на minecraft:air")
            
            print("\n📝 Используйте исправленный schem.py для автофикса!")
        else:
            print("\n✅ Палитра выглядит валидной!")
    
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python check_palette.py <файл.schem>")
        sys.exit(1)
    
    schem_file = sys.argv[1]
    if not Path(schem_file).exists():
        print(f"❌ Файл не найден: {schem_file}")
        sys.exit(1)
    
    check_palette(schem_file)
