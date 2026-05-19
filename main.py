import json
import random as r
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Callable, List, Optional, TypedDict

# Константы путей
CWD: Path = Path(__file__).resolve().parent
Icons: Path = CWD / "assets" / "icons"
Data: Path = CWD / "assets" / "data"
UserData: Path = Data / "user"
ItemData: Path = Data / "item"
ItemGeneratorData: Path = Data / "itemgenerator"
Logs: Path = CWD / "Logs"

# Генерация базовых данных и структуры
Data.mkdir(parents=True, exist_ok=True)
UserData.mkdir(parents=True, exist_ok=True)
ItemData.mkdir(parents=True, exist_ok=True)
ItemGeneratorData.mkdir(parents=True, exist_ok=True)
Icons.mkdir(parents=True, exist_ok=True)
Logs.mkdir(parents=True, exist_ok=True)

date_format = "%d.%m.%Y"
time_format = "%Y.%m.%d %H-%M-%S"
encoding = "utf-8"


# TypedDict для генераторов (оставляем как подсказку типа для загруженного JSON)
class ItemGenerator(TypedDict):
    name: str
    manufacturer: str
    stackable: bool
    max_stack: Optional[int]


# Лог-функции (не зависят от классов)
def _get_log_file() -> Path:
    log_filename = datetime.today().strftime(date_format)
    return Logs / f"{log_filename}.log"


def log_info(message: str) -> None:
    log_file: Path = _get_log_file()
    timestamp: str = datetime.now().strftime(time_format)
    with log_file.open("a", encoding=encoding) as f:
        f.write(f"{timestamp} -- INFO -- {message}\n")


def log_error(message: str) -> None:
    log_file: Path = _get_log_file()
    timestamp: str = datetime.now().strftime(time_format)
    with log_file.open("a", encoding=encoding) as f:
        f.write(f"{timestamp} -- ERROR -- {message}\n")


# Ленивый загрузчик Item.json вместо топ-левел загрузки (чтобы не ссылаться на типы/файлы до их объявления)
def load_item_generators(
    filename: str = "BasicItemGen.json",
) -> dict[str, List[ItemGenerator]]:
    """
    Загружает JSON генераторов из папки ItemGeneratorData.
    Возвращает пустой dict, если файл отсутствует или некорректен.
    """
    path = ItemGeneratorData / filename
    if not path.exists():
        log_error(f"Item generators file not found: {path}")
        raise ValueError(f"Item generators file not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding=encoding))
        return raw
    except json.JSONDecodeError as e:
        log_error(f"Failed to parse item generators JSON {path}: {e}")
        raise ValueError(f"Failed to parse item generators JSON {path}: {e}")


# Enum должен быть определён до использования
class ItemType(StrEnum):
    CARDIO_MACHINE = "Кардиотренажёр"
    STRENGTH_MACHINE = "Силовой тренажёр"
    FREE_WEIGHT = "Свободные веса"
    BENCH = "Скамья и стойки"
    FLEXIBILITY_EQUIPMENT = "Оборудование для гибкости"
    BALL = "Мяч"
    SPORTS_GEAR = "Игровой инвентарь"
    PROTECTIVE_GEAR = "Защитный инвентарь"
    CLOTHING_SMALL = "Малые вещи"
    ACCESSORY = "Аксессуары"


@dataclass
class Item:
    category: ItemType
    name: str
    manufacturer: str
    amount: int
    icon_path: Path = field(default_factory=lambda: Icons / "icon.png")
    stackable: bool = False
    max_stack: int | None = None  # None = неограничен, иначе положительное целое

    def _validate_amount(self) -> None:
        if not isinstance(self.amount, int):
            log_error(
                f"Invalid amount type for item {self.name!r}: {self.amount!r} (type {type(self.amount)})"
            )
            raise TypeError(f"Amount must be int, got {type(self.amount).__name__}")
        if self.amount <= 0:
            log_error(
                f"Invalid amount for item {self.name!r}: {self.amount} (must be > 0)"
            )
            raise ValueError(f"Amount must be positive (>0). Given: {self.amount}")

    def can_stack_with(self, other: "Item") -> bool:
        """Проверяет, можно ли стекать self с other (совместимость по ключевым полям)."""
        return (
            self.stackable
            and other.stackable
            and self.name == other.name
            and self.manufacturer == other.manufacturer
            # при необходимости добавить сравнение дополнительных полей (например, свойства)
        )

    def stack_up(self, amount: int) -> None:
        if not isinstance(amount, int):
            log_error(f"stack_up: non-int amount={amount!r} for {self.name!r}")
            raise TypeError("amount must be int")
        if amount <= 0:
            log_error(f"stack_up: non-positive amount={amount} for {self.name!r}")
            raise ValueError("Cannot stack up non-positive amount")
        if not self.stackable:
            log_error(f"Attempt to stack up non-stackable item {self.name!r}")
            raise ValueError("Item is not stackable")
        if self.max_stack is not None:
            if self.amount + amount > self.max_stack:
                log_error(
                    f"stack_up overflow for {self.name!r}: current={self.amount}, add={amount}, max={self.max_stack}"
                )
                raise ValueError(
                    f"Cannot add {amount} to {self.name!r}: would exceed max_stack ({self.max_stack})"
                )
        self.amount += amount
        log_info(f"Stacked up {amount} to {self.name!r}; new amount={self.amount}")

    def stack_down(self, amount: int) -> None:
        if not isinstance(amount, int):
            log_error(f"stack_down: non-int amount={amount!r} for {self.name!r}")
            raise TypeError("amount must be int")
        if amount <= 0:
            log_error(f"stack_down: non-positive amount={amount} for {self.name!r}")
            raise ValueError("Cannot stack down non-positive amount")
        if not self.stackable:
            log_error(f"Attempt to stack down non-stackable item {self.name!r}")
            raise ValueError("Item is not stackable")
        if amount > self.amount:
            log_error(
                f"stack_down underflow for {self.name!r}: requested={amount}, available={self.amount}"
            )
            raise ValueError(
                f"Cannot remove {amount} from {self.name!r}; only {self.amount} available"
            )
        self.amount -= amount
        log_info(f"Stacked down {amount} from {self.name!r}; new amount={self.amount}")

    def __post_init__(self) -> None:
        self._validate_amount()
        log_info(
            f"Created Item: name={self.name!r}, category={self.category.value!r}, amount={self.amount}"
        )

    @staticmethod
    def random_item(
        category: ItemType | None = None, filename: str = "BasicItemGen.json"
    ) -> "Item":
        if category is None:
            category = r.choice(list(ItemType))
        try:
            generators: dict[str, List[ItemGenerator]] = load_item_generators(filename)
        except ValueError:
            raise

        gen_list: List[ItemGenerator] = generators.get(
            category.value, []
        )  # явно по category.value
        if not gen_list:
            log_error(
                f"No item generators for category {category.value!r} in {filename}"
            )
            raise ValueError(f"No item generators for category: {category}")
        generator: ItemGenerator = r.choice(gen_list)
        stackable = bool(generator.get("stackable", False))
        max_stack = generator.get("max_stack")
        if max_stack is not None:
            try:
                max_stack = int(max_stack)
            except (TypeError, ValueError):
                max_stack = None
        amount = int(generator.get("amount", r.randint(1, 10)))
        item = Item(
            category=category,
            name=generator["name"],
            manufacturer=generator["manufacturer"],
            amount=amount,
            stackable=stackable,
            max_stack=max_stack,
        )
        log_info(
            f"Created item: {item.name!r} ({item.category.value!r}), stackable={item.stackable}, amount={item.amount}"
        )
        return item


@dataclass
class Inventory:
    # Исправлено: используем default_factory=list чтобы избежать общего списка для всех экземпляров [web:11]
    items: List[Item] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.items)

    def add_item(self, item: Item) -> None:
        self.items.append(item)
        log_info(f"Added this item to inventory: \n{item}")

    def remove_item(self, item: Item) -> None:
        if item not in self.items:
            text = f"No matching item: \n{item}"
            log_error(text)
            raise ValueError(text)
        # Исправлено: удаляем объект, если он найден
        self.items.remove(item)
        log_info(f"Removed item from inventory: \n{item}")

    def count_item(self, item: Item) -> int:
        return self.items.count(item)

    def search_item(self, name: str) -> List[Item]:
        log_info(f"Searching for items by name pattern: {name!r}")
        needle: str = name.casefold()
        found: List[Item] = [
            item for item in self.items if needle in item.name.casefold()
        ]
        log_info(f"Found: {len(found)}")
        return found

    def search_category(self, category: ItemType) -> List[Item]:
        log_info(f"Searching for items of type {category.value!r}")
        found: List[Item] = [item for item in self.items if item.category == category]
        log_info(f"Found: {len(found)} items for category {category.value!r}")
        return found

    def search_by_name(
        self,
        name: str,
        exact: bool = False,
        case_sensitive: bool = False,
        limit: int | None = None,
    ) -> List[Item]:
        needle: str = name if case_sensitive else name.casefold()

        def matches(item: Item) -> bool:
            target: str = item.name if case_sensitive else item.name.casefold()
            return (target == needle) if exact else (needle in target)

        results: List[Item] = [it for it in self.items if matches(it)]
        if limit is not None:
            results = results[:limit]
        log_info(
            f"search_by_name({name!r}, exact={exact}, case_sensitive={case_sensitive}) -> {len(results)} results"
        )
        return results

    def find_where(self, predicate: Callable[[Item], bool]) -> List[Item]:
        """Возвращает элементы, для которых predicate(item) is True."""
        found: List[Item] = [item for item in self.items if predicate(item)]
        log_info(f"find_where: found {len(found)} items")
        return found

    def count_by_name(self) -> Counter:
        return Counter(item.name for item in self.items)

    def count_by_category(self) -> Counter:
        return Counter(item.category for item in self.items)


@dataclass
class User:
    username: str
    password: str
    # Исправлено: используем default_factory=date.today чтобы дата регитсрации вычислялась при создании экземпляра [web:11]
    registration_date: date = field(default_factory=date.today)
    # inventory не в init, инициализируем в __post_init__
    inventory: Inventory = field(init=False)

    def __post_init__(self):
        # Исправлено: инициализируем inventory чтобы не получить AttributeError при обращении
        self.inventory = Inventory()

    def save(self) -> None:
        filename: str = f"{self.username}.json"
        save_path: Path = (
            UserData / filename
        )  # используем UserData константу для согласованности
        # Исправлено: сериализуем объекты Item в JSON-совместимый формат (Enum->str, Path->str)
        items_serialized = [
            {
                "category": item.category.value,
                "name": item.name,
                "manufacturer": item.manufacturer,
                "amount": item.amount,
                "icon_path": str(item.icon_path),
                "stackable": item.stackable,
                "max_stack": item.max_stack,
            }
            for item in self.inventory.items
        ]
        user_data: dict = {
            "username": self.username,
            "password": self.password,
            "registration_date": self.registration_date.strftime(date_format),
            "inventory": items_serialized,
        }
        # ensure_ascii=False сохраняет кириллицу читабельной в JSON файле [web:24]
        save_path.write_text(
            json.dumps(user_data, indent=2, ensure_ascii=False), encoding=encoding
        )
        log_info(f"Successfully saved user: {self.username!r}")

    @classmethod
    def load(cls, username: str) -> "User":
        filename: str = f"{username}.json"
        save_path: Path = UserData / filename  # используем ту же константу
        if save_path.exists():
            userdata = json.loads(save_path.read_text(encoding=encoding))
            reg_date = datetime.strptime(
                userdata["registration_date"], date_format
            ).date()
            user = cls(
                username=userdata["username"],
                password=userdata["password"],
                registration_date=reg_date,
            )
            # Исправлено: восстанавливаем inventory из сериализованного списка
            for it in userdata.get("inventory", []):
                # Пытаемся преобразовать строку категории обратно в ItemType
                cat = None
                try:
                    # сначала попробуем напрямую создать ItemType из строки (если в JSON хранится name)
                    cat = ItemType(it["category"])
                except Exception:
                    # иначе ищем по value
                    cat = next((c for c in ItemType if c.value == it["category"]), None)
                # Если cat всё ещё None — можно пропустить или поднять ошибку; здесь пропустим
                if cat is None:
                    log_error(f"Unknown category in saved item: {it.get('category')}")
                    continue
                item = Item(
                    category=cat,
                    name=it["name"],
                    manufacturer=it["manufacturer"],
                    amount=int(it["amount"]),
                    icon_path=Path(it.get("icon_path", Icons / "icon.png")),
                    stackable=bool(it.get("stackable", False)),
                    max_stack=(
                        int(it["max_stack"])
                        if it.get("max_stack") is not None
                        else None
                    ),
                )
                user.inventory.add_item(item)
            log_info(f"Successfully loaded user: {username!r}")
            return user
        else:
            log_error(f"No matching user: {username!r}")
            raise ValueError(f"No matching user: {username!r}")


def main() -> None:
    user: User = User.load("TheRisingStorm")
    category_to_find: ItemType = r.choice(list(ItemType))
    found: List[Item] = user.inventory.search_category(category_to_find)
    print(found)


if __name__ == "__main__":
    main()
