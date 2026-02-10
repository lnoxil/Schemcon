from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .categories import BlockTraits, categorize_block


@dataclass(frozen=True)
class MatchResult:
    source: str
    target: str
    reason: str
    confidence: float  # НОВОЕ: уверенность в замене (0.0-1.0)


def _color_distance(a: tuple[int, int, int] | None, b: tuple[int, int, int] | None) -> float:
    """Вычисляет расстояние между цветами в RGB пространстве."""
    if a is None or b is None:
        return 40.0
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _token_similarity(a: set[str], b: set[str]) -> float:
    """Вычисляет схожесть наборов токенов (Jaccard similarity)."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union


# НОВОЕ: Критические правила, которые НЕЛЬЗЯ нарушать
CRITICAL_RULES = {
    # Жидкость → жидкость того же типа
    "liquid_water": {"liquid_water"},
    "liquid_lava": {"liquid_lava"},
    
    # Воздух → воздух
    "air": {"air"},
    
    # Блок травы ≠ растение трава
    "grass_block": {"grass_block"},  # Только в блок травы
    "grass_plant": {"grass_plant", "tall_plant"},  # Трава/папоротник
    
    # Маленький гриб ≠ блок гриба
    "mushroom_small": {"mushroom_small"},
    "mushroom_block": {"mushroom_block"},
    
    # Растения только в растения
    "flower_small": {"flower_small", "grass_plant"},
    "flower_tall": {"flower_tall", "tall_plant"},
    "sapling": {"sapling"},
    "crop": {"crop", "grass_plant"},
    "water_plant": {"water_plant"},
    "vine": {"vine"},
    "roots": {"roots", "vine"},
    "bamboo": {"bamboo"},
}


# НОВОЕ: Предпочтительные замены (если есть выбор)
PREFERRED_REPLACEMENTS = {
    # Если нет точного совпадения, используем эти замены
    "grass_plant": "short_grass",  # Трава → короткая трава
    "flower_small": "dandelion",   # Цветок → одуванчик
    "flower_tall": "sunflower",    # Высокий цветок → подсолнух
    "mushroom_small": "red_mushroom",  # Гриб → красный гриб
    "sapling": "oak_sapling",      # Саженец → дуб
    "crop": "wheat",               # Культура → пшеница
}


def _is_category_compatible(source_category: str, target_category: str) -> bool:
    """НОВОЕ: Проверяет совместимость категорий блоков."""
    # Точное совпадение
    if source_category == target_category:
        return True
    
    # Проверяем критические правила
    if source_category in CRITICAL_RULES:
        return target_category in CRITICAL_RULES[source_category]
    
    # Если нет строгих правил, считаем совместимым
    return True


def _score(candidate: BlockTraits, source: BlockTraits) -> float:
    """ИСПРАВЛЕНО: Улучшенная система скоринга с весами."""
    score = 0.0
    
    # КРИТИЧНО: Несовместимая категория = огромный штраф
    if not _is_category_compatible(source.category, candidate.category):
        score += 1000.0  # Практически исключаем
    
    # КРИТИЧНО: Разный тип блока (solid/plant/liquid) = большой штраф
    if source.block_type != candidate.block_type:
        score += 500.0
    
    # ВАЖНО: Разная форма (slab, stairs, etc.)
    if candidate.shape != source.shape:
        score += 150.0
    
    # ВАЖНО: Разное семейство (wool, stone, etc.)
    if candidate.family != source.family:
        score += 100.0
    
    # ВАЖНО: Схожесть токенов (названия)
    token_sim = _token_similarity(candidate.tokens, source.tokens)
    score += (1.0 - token_sim) * 50.0
    
    # ВАЖНО: Расстояние по цвету
    color_dist = _color_distance(candidate.color, source.color)
    score += color_dist * 2.0  # Увеличили вес цвета
    
    return score


def _is_safe_match(source: BlockTraits, candidate: BlockTraits, score: float) -> bool:
    """ИСПРАВЛЕНО: Более строгие критерии безопасной замены."""
    # Проверяем совместимость категорий
    if not _is_category_compatible(source.category, candidate.category):
        return False
    
    # Разный тип блока = небезопасно
    if source.block_type != candidate.block_type:
        return False
    
    token_sim = _token_similarity(source.tokens, candidate.tokens)
    same_shape = source.shape == candidate.shape
    same_family = source.family == candidate.family
    same_category = source.category == candidate.category
    
    # Идеальное совпадение
    if same_shape and same_family and same_category and score < 100:
        return True
    
    # Хорошее совпадение
    if same_shape and same_category and token_sim >= 0.5 and score < 150:
        return True
    
    # Приемлемое совпадение с высокой схожестью токенов
    if same_category and token_sim >= 0.7 and score < 120:
        return True
    
    return False


def _calculate_confidence(score: float, source: BlockTraits, candidate: BlockTraits) -> float:
    """НОВОЕ: Вычисляет уверенность в замене (0.0-1.0)."""
    if score >= 500:  # Несовместимые типы
        return 0.0
    
    # Идеальное совпадение
    if source.category == candidate.category and source.shape == candidate.shape:
        if score < 50:
            return 1.0
        elif score < 100:
            return 0.9
        elif score < 150:
            return 0.8
    
    # Хорошее совпадение
    if source.category == candidate.category:
        if score < 100:
            return 0.7
        elif score < 200:
            return 0.6
    
    # Приемлемое совпадение
    if score < 250:
        return 0.5
    
    return 0.3  # Низкая уверенность


@lru_cache(maxsize=4096)
def _cached_traits(name: str) -> BlockTraits:
    return categorize_block(name)


def pick_best_match(source_name: str, target_blocks: set[str]) -> MatchResult:
    """ИСПРАВЛЕНО: Улучшенный алгоритм маппинга с умными правилами."""
    # Точное совпадение
    if source_name in target_blocks:
        return MatchResult(
            source=source_name, 
            target=source_name, 
            reason="exact", 
            confidence=1.0
        )

    source_traits = _cached_traits(source_name)
    
    # НОВОЕ: Сначала ищем только совместимые по категории
    compatible_candidates: list[tuple[float, str, BlockTraits]] = []
    incompatible_candidates: list[tuple[float, str, BlockTraits]] = []
    
    for candidate_name in target_blocks:
        if candidate_name.startswith("#"):
            continue
        
        candidate_traits = _cached_traits(candidate_name)
        score = _score(candidate_traits, source_traits)
        
        if _is_category_compatible(source_traits.category, candidate_traits.category):
            compatible_candidates.append((score, candidate_name, candidate_traits))
        else:
            incompatible_candidates.append((score, candidate_name, candidate_traits))
    
    # Сортируем по score (меньше = лучше)
    compatible_candidates.sort(key=lambda x: x[0])
    
    # НОВОЕ: Пытаемся найти безопасную замену среди совместимых
    if compatible_candidates:
        for score, candidate_name, candidate_traits in compatible_candidates[:10]:  # Топ-10
            if _is_safe_match(source_traits, candidate_traits, score):
                confidence = _calculate_confidence(score, source_traits, candidate_traits)
                return MatchResult(
                    source=source_name,
                    target=candidate_name,
                    reason=f"smart_match(score={score:.1f})",
                    confidence=confidence
                )
        
        # Если нет безопасной замены, но есть совместимые - берём лучший
        score, candidate_name, candidate_traits = compatible_candidates[0]
        if score < 300:  # Разумный порог
            confidence = _calculate_confidence(score, source_traits, candidate_traits)
            return MatchResult(
                source=source_name,
                target=candidate_name,
                reason=f"compatible_match(score={score:.1f})",
                confidence=confidence
            )
    
    # НОВОЕ: Если ничего не найдено, проверяем предпочтительные замены
    if source_traits.category in PREFERRED_REPLACEMENTS:
        preferred = PREFERRED_REPLACEMENTS[source_traits.category]
        for candidate_name in target_blocks:
            if preferred in candidate_name:
                return MatchResult(
                    source=source_name,
                    target=candidate_name,
                    reason="preferred_fallback",
                    confidence=0.6
                )
    
    # Последняя попытка: ищем хоть что-то похожее
    if incompatible_candidates:
        incompatible_candidates.sort(key=lambda x: x[0])
        score, candidate_name, _candidate_traits = incompatible_candidates[0]
        if score < 200:  # Очень строгий порог для несовместимых
            return MatchResult(
                source=source_name,
                target=candidate_name,
                reason=f"unsafe_match(score={score:.1f})",
                confidence=0.3
            )
    
    # Не нашли замену - оставляем как есть
    return MatchResult(
        source=source_name, 
        target=source_name, 
        reason="no_safe_match", 
        confidence=0.0
    )
