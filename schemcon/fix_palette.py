#!/usr/bin/env python3
"""
Автоматическое исправление палитры .schem файла
Исправляет все проблемы которые вызывают NullPointerException
"""

import sys
import re
from pathlib import Path

# Импортируем из нашего пакета
try:
    from schem import load_schematic, save_schematic
except ImportError:
    print("❌ Не могу импортировать schem.py")
    print("   Убедитесь что schem.py находится в той же папке")
    sys.exit(1)


def fix_block_name(name: str) -> str:
    """Исправляет имя блока."""
    if not name or not name.strip():
        return "minecraft:air"
    
    name = name.strip().lower()
    
    # Добавляем namespace если нет
    if ':' not in name:
        name = f"minecraft:{name}"
    
    # Проверяем формат
    base = name.split('[')[0]
    pattern = re.compile(r'^[a-z0-9_.-]+:[a-z0-9_./-]+$')
    
    if not pattern.match(base):
        print(f"   ⚠️  Невалидный блок '{name}' → minecraft:air")
        return "minecraft:air"
    
    return name


def fix_palette_manual(schem_path: str, output_path: str = None):
    """Исправляет палитру вручную."""
    if output_path is None:
        output_path = schem_path.replace('.schem', '_fixed.schem')
    
    print(f"\n🔧 Исправление файла: {schem_path}")
    print(f"📝 Вывод: {output_path}")
    print("=" * 60)
    
    try:
        # Загружаем
        schematic = load_schematic(schem_path)
        palette = schematic.palette
        
        print(f"📊 Оригинальная палитра: {len(palette)} блоков")
        
        # Исправляем
        fixed_palette = {}
        fixed_count = 0
        removed_count = 0
        
        # Сначала резервируем воздух в индексе 0
        air_index = 0
        for name, idx in palette.items():
            if 'air' in name.lower():
                air_index = int(idx)
                break
        
        fixed_palette["minecraft:air"] = air_index if air_index == 0 else 0
        print(f"✅ Воздух зарезервирован в индексе {fixed_palette['minecraft:air']}")
        
        # Исправляем остальные блоки
        for name, index in palette.items():
            if 'air' in name.lower() and name != "minecraft:air":
                continue  # Пропускаем другие варианты воздуха
            
            if name == "minecraft:air":
                continue  # Уже добавлен
            
            fixed_name = fix_block_name(name)
            
            if fixed_name != name:
                fixed_count += 1
                print(f"   🔧 {name} → {fixed_name}")
            
            if fixed_name == "minecraft:air" and name != "minecraft:air":
                removed_count += 1
                # Не добавляем, заменили на воздух
                continue
            
            # Проверяем коллизии индексов
            if fixed_name in fixed_palette:
                if fixed_palette[fixed_name] != int(index):
                    print(f"   ⚠️  Коллизия: {fixed_name} уже существует")
                    # Заменяем на безопасный блок
                    safe_blocks = ["minecraft:stone", "minecraft:dirt", "minecraft:cobblestone"]
                    for safe in safe_blocks:
                        if safe not in fixed_palette or fixed_palette[safe] == int(index):
                            fixed_name = safe
                            print(f"      → Использую {safe}")
                            break
            
            fixed_palette[fixed_name] = int(index)
        
        # Применяем исправленную палитру
        print(f"\n📈 Исправленная палитра: {len(fixed_palette)} блоков")
        print(f"   Исправлено: {fixed_count}")
        print(f"   Удалено: {removed_count}")
        
        schematic.replace_palette(fixed_palette)
        
        # Сохраняем
        save_schematic(schematic, output_path)
        
        print(f"\n✅ ГОТОВО!")
        print(f"   Файл сохранён: {output_path}")
        
        # Проверяем размер
        orig_size = Path(schem_path).stat().st_size
        new_size = Path(output_path).stat().st_size
        
        print(f"\n📦 Размеры файлов:")
        print(f"   Оригинал: {orig_size:,} байт ({orig_size / 1024 / 1024:.2f} MB)")
        print(f"   Исправлен: {new_size:,} байт ({new_size / 1024 / 1024:.2f} MB)")
        
        if new_size < orig_size:
            saved = orig_size - new_size
            print(f"   💾 Сэкономлено: {saved:,} байт ({saved / 1024 / 1024:.2f} MB)")
        
        print("\n" + "=" * 60)
        print("💡 Теперь попробуйте загрузить исправленный файл в FAWE:")
        print(f"   //schem load {Path(output_path).name}")
        print("   //paste")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("""
🔧 Автоматическое исправление палитры .schem

Использование:
    python fix_palette.py <input.schem> [output.schem]

Пример:
    python fix_palette.py lgdfl.schem lgdfl_fixed.schem
    
Если output не указан, добавится '_fixed' к имени файла.
""")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not Path(input_file).exists():
        print(f"❌ Файл не найден: {input_file}")
        sys.exit(1)
    
    fix_palette_manual(input_file, output_file)
