"""
models.py
Логика описания спортивного инвентаря. Интегрирована система умных
относительных путей для графических иконок и модуль их кастомного импорта.
"""

import shutil  # Понадобится для копирования файлов при импорте иконок с ПК
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import List, Optional, TypedDict

from config import Icons, log_error, log_info, t


class ItemType(StrEnum):
    CARDIO_MACHINE = "cardio_machine"
    STRENGTH_MACHINE = "strength_machine"
    FREE_WEIGHT = "free_weight"
    BENCH = "bench"
    FLEXIBILITY_EQUIPMENT = "flexibility_equipment"
    BALL = "ball"
    SPORTS_GEAR = "sports_gear"
    PROTECTIVE_GEAR = "protective_gear"
    CLOTHING_SMALL = "clothing_small"
    ACCESSORY = "accessory"

    def get_label(self) -> str:
        return t(f"cat_{self.value}")


class ItemCondition(StrEnum):
    NEW = "new"
    USED = "used"
    BROKEN = "broken"

    def get_label(self) -> str:
        return t(f"cond_{self.value}")


class ItemSerializedDict(TypedDict):
    id: str
    category: str
    name: str
    manufacturer: str
    amount: int
    condition: str
    icon_path: str
    stackable: bool
    max_stack: Optional[int]


@dataclass
class Item:
    category: ItemType
    name: str
    manufacturer: str
    amount: int
    condition: ItemCondition = ItemCondition.NEW
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    # По умолчанию ставим None, чтобы __post_init__ заполнил путь автоматически
    icon_path: Optional[Path] = None
    stackable: bool = False
    max_stack: Optional[int] = None

    def _validate_amount(self) -> None:
        if not isinstance(self.amount, int) or self.amount <= 0:
            raise ValueError("Amount must be a positive integer.")
        if self.max_stack is not None and self.amount > self.max_stack:
            raise ValueError(
                f"Initial amount ({self.amount}) exceeds max stack limit ({self.max_stack})."
            )

    def __post_init__(self) -> None:
        self._validate_amount()

        # --- АВТОМАТИЧЕСКИЙ ПОДБОР ИКОНКИ ---
        if self.icon_path is None:
            # Пытаемся найти иконку конкретно под категорию (например, ball.png)
            category_icon = Icons / f"{self.category.value}.png"
            if category_icon.exists():
                self.icon_path = category_icon
            else:
                # Если такой иконки нет (или оффлайн), откатываемся на общую заглушку
                self.icon_path = Icons / "default.png"

        log_info(f"Item initialized. Bound icon path: {self.icon_path.name}")

    def change_custom_icon(self, external_file_path: Path) -> None:
        """
        Берет любой файл изображения с ПК пользователя, безопасно копирует его
        в локальную папку проекта assets/icons/ под уникальным именем и привязывает к предмету.
        Это бэкенд-база для кнопки 'Загрузить свою иконку' в GUI.
        """
        if not external_file_path.exists():
            raise FileNotFoundError(
                f"Selected source image {external_file_path} does not exist."
            )

        # Получаем расширение оригинального файла (.png, .jpg)
        extension = external_file_path.suffix.lower()
        if extension not in [".png", ".jpg", ".jpeg", ".gif"]:
            raise ValueError("Unsupported image format. Use PNG or JPG.")

        # Генерируем уникальное имя внутри нашей папки, чтобы файлы не перезаписывали друг друга
        new_filename = f"custom_{self.id}{extension}"
        destination_path = Icons / new_filename

        try:
            shutil.copy2(external_file_path, destination_path)
            self.icon_path = destination_path
            log_info(
                f"Custom user icon successfully imported to database assets: {new_filename}"
            )
        except Exception as e:
            log_error(f"Critical asset copy failure: {e}")
            raise IOError("Could not save custom icon to local database storage.")

    def can_stack_with(self, other: "Item") -> bool:
        # Предметы с разными кастомными иконками не должны стакаться вместе
        return (
            self.stackable
            and other.stackable
            and self.name == other.name
            and self.manufacturer == other.manufacturer
            and self.condition == other.condition
            and self.icon_path == other.icon_path
        )

    def stack_up(self, amount: int) -> None:
        if amount <= 0 or not self.stackable:
            raise ValueError("Invalid stacking operation request.")
        if self.max_stack is not None and self.amount + amount > self.max_stack:
            raise ValueError(f"Stack overflow limit reached ({self.max_stack}).")
        self.amount += amount

    def stack_down(self, amount: int) -> None:
        if amount <= 0 or amount > self.amount:
            raise ValueError("Invalid unstacking amount requested.")
        self.amount -= amount


@dataclass
class Inventory:
    items: list[Item] = field(default_factory=list[Item])

    def add_item(self, item: Item) -> None:
        if item.stackable:
            for existing_item in self.items:
                if existing_item.can_stack_with(item):
                    try:
                        existing_item.stack_up(item.amount)
                        return
                    except ValueError:
                        pass
        self.items.append(item)

    def remove_item_by_id(self, item_id: str) -> None:
        for item in self.items:
            if item.id == item_id:
                self.items.remove(item)
                log_info(f"Item record wiped out completely. Target ID: {item_id}")
                return
        raise ValueError(f"Item record with ID {item_id} was not found.")

    def edit_item(
        self,
        item_id: str,
        new_name: str | None = None,
        new_manufacturer: str | None = None,
        new_condition: ItemCondition | None = None,
    ) -> None:
        target_item = next((it for it in self.items if it.id == item_id), None)
        if not target_item:
            raise ValueError(f"Item with ID {item_id} not found.")

        if new_name and new_name.strip():
            target_item.name = new_name.strip()
        if new_manufacturer:
            target_item.manufacturer = new_manufacturer.strip()
        if new_condition:
            target_item.condition = new_condition

        if target_item.stackable:
            for existing_item in self.items:
                if existing_item.id != target_item.id and existing_item.can_stack_with(
                    target_item
                ):
                    try:
                        existing_item.stack_up(target_item.amount)
                        self.items.remove(target_item)
                        return
                    except ValueError:
                        pass

    def get_filtered_and_sorted(
        self,
        category: Optional[ItemType] = None,
        condition: Optional[ItemCondition] = None,
        search_query: Optional[str] = None,
        sort_by: Optional[str] = None,
    ) -> List[Item]:
        result: List[Item] = self.items.copy()
        if category:
            result = [it for it in result if it.category == category]
        if condition:
            result = [it for it in result if it.condition == condition]
        if search_query and search_query.strip():
            q = search_query.strip().lower()
            result = [
                it
                for it in result
                if q in it.name.lower() or q in it.manufacturer.lower()
            ]

        if sort_by == "name":
            result.sort(key=lambda it: it.name.casefold())
        elif sort_by == "amount":
            result.sort(key=lambda it: it.amount, reverse=True)
        return result
