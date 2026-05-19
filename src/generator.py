"""
generator.py
Модуль динамической генерации предметов на основе JSON-профилей.
Поддерживает стандартные шаблоны и кастомные пользовательские файлы.
"""

import json
import random
from pathlib import Path
from typing import Dict, List, TypedDict

from config import ItemGeneratorData, log_error, log_info
from models import Item, ItemCondition, ItemType


# --- ОПИСАНИЕ СТРУКТУРЫ JSON ДЛЯ ПРЕДОТВРАЩЕНИЯ ОШИБОК ---
class GeneratorProfileDict(TypedDict):
    manufacturers: List[str]
    presets: Dict[str, List[str]]


# Жесткий резервный хардкод на случай, если с диска вообще всё удалили
FALLBACK_PROFILE: GeneratorProfileDict = {
    "manufacturers": ["Generic Brand"],
    "presets": {k.value: [f"Default {k.name} Item"] for k in ItemType},
}


def _load_profile(profile_filename: str) -> GeneratorProfileDict:
    """
    Загружает JSON-профиль генератора.
    Если файл поврежден, отсутствует или некорректен, безопасно возвращает базовый профиль.
    """
    file_path: Path = ItemGeneratorData / profile_filename

    # Если файла нет — создаем дефолтный DefaultItemGen.json, чтобы папка не была пустой
    if not file_path.exists() and profile_filename == "DefaultItemGen.json":
        try:
            # Создаем структуру на основе встроенных данных для первого запуска
            default_structure: GeneratorProfileDict = {
                "manufacturers": [
                    "Nike",
                    "Adidas",
                    "Torneo",
                    "Kettler",
                    "Under Armour",
                ],
                "presets": {
                    ItemType.CARDIO_MACHINE.value: [
                        "Беговая дорожка X-Fit",
                        "Велотренажер CyclePro",
                    ],
                    ItemType.STRENGTH_MACHINE.value: [
                        "Тренажер для жима ногами",
                        "Кроссовер блочный",
                    ],
                    ItemType.FREE_WEIGHT.value: [
                        "Гантель гексагональная 10кг",
                        "Блин для штанги 20кг",
                    ],
                    ItemType.BENCH.value: [
                        "Скамья для жима регулируемая",
                        "Стойка для приседаний",
                    ],
                    ItemType.FLEXIBILITY_EQUIPMENT.value: [
                        "Коврик для йоги",
                        "Роллер массажный",
                    ],
                    ItemType.BALL.value: ["Мяч футбольный", "Мяч баскетбольный"],
                    ItemType.SPORTS_GEAR.value: [
                        "Ракетка для тенниса",
                        "Набор для пинг-понга",
                    ],
                    ItemType.PROTECTIVE_GEAR.value: [
                        "Шлем боксерский",
                        "Щитки футбольные",
                    ],
                    ItemType.CLOTHING_SMALL.value: [
                        "Жилет-утяжелитель 10кг",
                        "Пояс атлетический",
                    ],
                    ItemType.ACCESSORY.value: [
                        "Скакалка скоростная",
                        "Эспандер ленточный",
                    ],
                },
            }
            file_path.write_text(
                json.dumps(default_structure, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            log_info(
                "DefaultItemGen.json generated successfully on zero-state trigger."
            )
            return default_structure
        except Exception as e:
            log_error(f"Failed to dump default itemgen profile: {e}")
            return FALLBACK_PROFILE

    # Читаем существующий файл с защитой от ошибок синтаксиса (JSONDecodeError)
    try:
        data: GeneratorProfileDict = json.loads(file_path.read_text(encoding="utf-8"))

        # Проверяем структуру: есть ли нужные корневые ключи
        if "manufacturers" not in data or "presets" not in data:
            raise KeyError("Missing core profile keys: 'manufacturers' or 'presets'")

        return data
    except Exception as e:
        log_error(
            f"Profile loading failed for {profile_filename!r} ({e}). Falling back to safe defaults."
        )
        return FALLBACK_PROFILE


def generate_random_item(profile_name: str = "DefaultItemGen.json") -> Item:
    """
    Генерирует объект Item, используя указанный JSON-профиль из папки itemgenerator.
    Если передан сторонний файл (например, 'UserCustom.json'), данные подтянутся из него.
    """
    profile = _load_profile(profile_name)

    # 1. Выбираем случайную категорию инвентаря
    category: ItemType = random.choice(list(ItemType))

    # 2. Безопасно достаем список названий для этой категории из JSON
    # Если в пользовательском файле забыли указать эту категорию, берем запасное имя
    available_names = profile["presets"].get(category.value)
    if not available_names:
        log_error(
            f"Profile {profile_name!r} misses key {category.value!r}. Patching inline."
        )
        available_names = [f"Инвентарь категории {category.name}"]

    name: str = random.choice(available_names)

    # 3. Выбираем бренд и состояние
    manufacturer = random.choice(profile["manufacturers"])
    condition = random.choice(list(ItemCondition))

    # 4. Логика стекирования (остаётся неизменной и надёжной)
    stackable_categories: List[ItemType] = [
        ItemType.BALL,
        ItemType.CLOTHING_SMALL,
        ItemType.ACCESSORY,
        ItemType.FREE_WEIGHT,
    ]
    is_stackable = category in stackable_categories

    max_stack = 20 if is_stackable else None
    amount = random.randint(1, 20) if is_stackable else 1

    return Item(
        category=category,
        name=name,
        manufacturer=manufacturer,
        amount=amount,
        condition=condition,
        stackable=is_stackable,
        max_stack=max_stack,
    )
