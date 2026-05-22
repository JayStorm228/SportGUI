"""
models.py
Логика описания спортивного инвентаря. Интегрирована система умных
относительных путей для графических иконок и модуль их кастомного импорта.
"""

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Callable, List, Optional, TypedDict

# ТИПИЗАЦИЯ: Импортируем Pillow для оптимизации кастомной графики в GUI
from PIL import Image

from config import Icons, log_error, log_info, t
from exceptions import ItemNotFoundError, ItemStackError

InventoryCallback = Callable[[], None]


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
        Берет любое изображение с ПК пользователя, сжимает его до 256x256
        через Pillow для экономии памяти GUI и сохраняет в ассеты как PNG.
        """
        if not external_file_path.exists():
            raise FileNotFoundError(
                f"Selected source image {external_file_path} does not exist."
            )

        # Расширяем список поддерживаемых форматов для Pillow
        extension = external_file_path.suffix.lower()
        if extension not in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
            raise ValueError("Unsupported image format. Use PNG, JPG, WEBP or BMP.")

        # Фиксируем формат PNG: он идеален для иконок интерфейса из-за поддержки альфа-канала (прозрачности)
        new_filename = f"custom_{self.id}.png"
        destination_path = Icons / new_filename

        try:
            # Открываем изображение через контекстный менеджер Pillow
            with Image.open(external_file_path) as img:
                # Задаем целевой максимальный размер для ячейки инвентаря
                target_size: tuple[int, int] = (256, 256)

                # thumbnail() пропорционально уменьшает картинку, если она больше 256x256.
                # Resampling.LANCZOS обеспечивает максимальную четкость при сжатии.
                img.thumbnail(target_size, Image.Resampling.LANCZOS)

                # Сохраняем с флагом оптимизации веса файла
                img.save(destination_path, "PNG", optimize=True)

            self.icon_path = destination_path
            log_info(
                f"Custom user icon successfully optimized and saved to assets: {new_filename}"
            )
        except Exception as e:
            log_error(f"Critical image optimization failure: {e}")
            raise IOError("Could not process and compress custom icon setup.")

    def can_stack_with(self, other: "Item") -> bool:
        if not self.stackable or not other.stackable:
            return False
        return (
            self.category == other.category
            and self.name.strip().lower() == other.name.strip().lower()
            and self.manufacturer.strip().lower() == other.manufacturer.strip().lower()
            and self.condition == other.condition
        )

    def stack_up(self, amount_to_add: int) -> None:
        """
        Увеличивает количество предметов в стеке.
        ТИПИЗАЦИЯ И ОШИБКИ: Выбрасывает ItemStackError вместо ValueError.
        """
        if not self.stackable:
            raise ItemStackError(f"Item '{self.name}' is non-stackable.")

        limit = self.max_stack if self.max_stack is not None else 20
        if self.amount + amount_to_add > limit:
            raise ItemStackError(
                f"Stack overflow for '{self.name}'. "
                f"Attempted: {self.amount + amount_to_add}, Max allowed: {limit}"
            )
        self.amount += amount_to_add

    def stack_down(self, amount: int) -> None:
        if amount <= 0 or amount > self.amount:
            raise ValueError("Invalid unstacking amount requested.")
        self.amount -= amount


@dataclass
class Inventory:
    # Список предметов инвентаря
    items: list[Item] = field(default_factory=lambda: [])

    # ИСПРАВЛЕНИЕ ДЛЯ PYLANCE: Используем кастомный тип InventoryCallback.
    # Конструкция lambda: [] явно говорит тайп-чекеру: "Здесь создается пустой список под кастомный тип".
    _listeners: list[InventoryCallback] = field(
        default_factory=lambda: [], repr=False, compare=False
    )

    def subscribe(self, callback_function: InventoryCallback) -> None:
        """
        Регистрирует внешнюю функцию интерфейса, которую нужно вызвать при изменении данных.
        """
        if callback_function not in self._listeners:
            self._listeners.append(callback_function)

    def _notify_listeners(self) -> None:
        """
        Внутренний служебный метод: перебирает всех подписчиков и вызывает их функции.
        """
        for callback in self._listeners:
            try:
                callback()  # Вызываем сохраненную функцию окна интерфейса
            except Exception as e:
                log_error(f"Error notifying inventory listener: {e}")

    def add_item(self, item: Item) -> None:
        """Добавляет предмет с автоматическим умным стекированием."""
        if item.stackable:
            for existing in self.items:
                if existing.can_stack_with(item):
                    try:
                        existing.stack_up(item.amount)
                        log_info(
                            f"Merged stack for item: '{item.name}' (New quantity: {existing.amount})"
                        )
                        self._notify_listeners()
                        return
                    except ItemStackError:
                        # Если этот конкретный стек заполнен, ищем следующий или добавим отдельной ячейкой
                        pass
        self.items.append(item)
        log_info(f"New discrete slot added to inventory: '{item.name}'")
        self._notify_listeners()

    def remove_item(self, item_id: str) -> None:
        """
        Удаляет предмет по ID.
        ТИПИЗАЦИЯ И ОШИБКИ: Выбрасывает ItemNotFoundError, если ID некорректен.
        """
        target = next((it for it in self.items if it.id == item_id), None)
        if not target:
            raise ItemNotFoundError(f"Cannot delete item. ID '{item_id}' not found.")

        self.items.remove(target)
        log_info(f"Item with ID {item_id} successfully purged.")
        self._notify_listeners()

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
                        # При редактировании предмет объединился с другим стеком -> уведомляем UI
                        self._notify_listeners()
                        return
                    except ValueError:
                        pass

        # Текст или свойства предмета просто изменились -> уведомляем UI
        self._notify_listeners()

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
