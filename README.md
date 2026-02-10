# Schemcon

Бесплатный конвертер Minecraft-схем (`.schem`) между версиями. Инструмент строит mapping блоков между версиями и заменяет палитру схемы.

## Что уже есть
- Загрузка реестров блоков для выбранной версии.
- Если в server.jar нет `reports/blocks.json`, включается цепочка fallback: блоки из server tags, затем из client jar (`assets/minecraft/blockstates`), и только потом внешний источник (PrismarineJS). Это сильно снижает вероятность падения `fetch-registry`.
- Автоматическое построение mapping по форме, семейству и цвету блока.
- Конвертация `.schem` через замену палитры.
- Поддержка палитры как в стандартных `.schem` (Sponge `Palette`), так и в Litematic-подобных схемах (`Regions/*/BlockStatePalette`).

## CLI
### 1) Скачать реестры
```bash
python -m schemcon fetch-registry 1.21
python -m schemcon fetch-registry 1.16.5
```

### 2) Построить mapping
```bash
python -m schemcon build-mapping \
  --source-dir data/versions/1.21 \
  --target-dir data/versions/1.16.5 \
  --output data/mappings/1.21-to-1.16.5.json
```

### 3) Конвертировать схему
```bash
python -m schemcon convert \
  --input input.schem \
  --output output_1.16.5.schem \
  --mapping data/mappings/1.21-to-1.16.5.json \
  --report conversion_report.json
```

## GUI (автоматический режим)
Запуск:

```bash
python -m schemcon gui
```

В GUI теперь достаточно указать:
- исходную версию,
- целевую версию,
- входной `.schem`,
- выходной `.schem`.

После нажатия кнопки запускается полный конвейер автоматически:
1. скачивание/подготовка реестров,
2. построение mapping,
3. конвертация схемы,
4. вывод лога и таблицы замен **только тех блоков, которые реально были в палитре схемы**.

В таблице есть:
- исходный блок,
- блок-замена,
- причина выбора,
- свойства обоих блоков (`shape`, `family`, `color`).

При выборе строки показываются визуальные мини-превью (цветовые карточки) рядом с тегами.

## Ограничения
- Конвертация пока меняет только палитру, без пересчета BlockData.
- При коллизиях палитры сохранится оригинальное имя, чтобы не ломать индексы.
