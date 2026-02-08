# Schemcon

Прототип бесплатного конвертера Minecraft-схем (`.schem`) между версиями. Сейчас инструмент делает базовый шаг: строит карту соответствий блоков между версиями и обновляет палитру схемы, сохраняя индексы BlockData.

## Что уже есть
- Загрузка `reports/blocks.json` и `reports/registries.json` из server.jar выбранной версии.
- Автоматическое построение карты соответствий по категориям (slab/stairs/flower/etc) и цвету.
- Конвертация `.schem` через замену элементов палитры.

## Быстрый старт
### 1) Скачать реестры блоков
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

## GUI
Для удобного использования можно открыть графический интерфейс:

```bash
python -m schemcon gui
```

GUI содержит три шага: загрузка реестров, построение mapping и конвертация схемы.

## Ограничения
- Сейчас конвертация меняет только палитру, не пересчитывая BlockData.
- При коллизиях (две разные записи палитры → один блок) сохранится оригинальное имя, чтобы не сломать индексы.
- Нужна доработка правил замены и полноценное слияние индексов с перезаписью BlockData.
