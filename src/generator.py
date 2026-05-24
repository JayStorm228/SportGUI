"""
generator.py
Модуль динамической генерации предметов на основе JSON-профилей.
Поддерживает стандартные шаблоны и кастомные пользовательские файлы.
"""

import json
import random
import uuid
from pathlib import Path
from typing import Dict, List, TypedDict

from config import Icons, ItemGeneratorData, log_error, log_info
from exceptions import GeneratorError
from models import Item, ItemCondition, ItemType


class GeneratorProfileDict(TypedDict):
    manufacturers: List[str]
    presets: Dict[str, List[str]]


FALLBACK_PROFILE: GeneratorProfileDict = {
    "manufacturers": ["Generic Brand"],
    "presets": {k.value: [f"Default {k.name} Item"] for k in ItemType},
}


def _load_profile(profile_filename: str) -> GeneratorProfileDict:
    file_path: Path = ItemGeneratorData / profile_filename

    if not file_path.exists():
        log_error(f"Generation profile blueprint missing at: {file_path}")
        return FALLBACK_PROFILE

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if "manufacturers" not in data or "presets" not in data:
            raise GeneratorError(
                "Invalid JSON schema layout inside generator blueprint."
            )
        return data
    except Exception as e:
        log_error(f"Critical damage in item generator JSON array: {e}")
        return FALLBACK_PROFILE


def generate_random_item(profile_name: str = "DefaultItemGen.json") -> Item:
    """Генерирует строго типизированный валидный объект инвентаря."""
    profile = _load_profile(profile_name)

    if not profile.get("manufacturers") or not profile.get("presets"):
        raise GeneratorError("Item generator component is completely uninitialized.")

    category: ItemType = random.choice(list(ItemType))
    available_names = profile["presets"].get(category.value)

    if not available_names:
        available_names = [f"Инвентарь категории {category.name}"]

    name: str = random.choice(available_names)
    manufacturer = random.choice(profile["manufacturers"])
    condition = random.choice(list(ItemCondition))

    stackable_categories: List[ItemType] = [
        ItemType.BALL,
        ItemType.CLOTHING_SMALL,
        ItemType.ACCESSORY,
        ItemType.FREE_WEIGHT,
    ]
    is_stackable = category in stackable_categories
    max_stack = 20 if is_stackable else None

    item = Item(
        id=str(uuid.uuid4()),
        category=category,
        name=name,
        manufacturer=manufacturer,
        amount=1 if not is_stackable else random.randint(1, 5),
        condition=condition,
        icon_path=Icons / f"{category.value}.png",
        stackable=is_stackable,
        max_stack=max_stack,
    )
    log_info(f"Random item generated: {item.name} ({item.category.value})")
    return item
