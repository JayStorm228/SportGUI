"""
auth.py
Управляет учётными записями пользователей (User), хешированием паролей и сохранением данных на диск.
"""

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import List, TypedDict

# Импортируем необходимые инструменты из соседних файлов нашей структуры
from config import Icons, UserData, date_format, encoding, log_error, log_info
from models import Inventory, Item, ItemCondition, ItemSerializedDict, ItemType


# --- СТРУКТУРА ДАННЫХ ПОЛЬЗОВАТЕЛЯ ДЛЯ JSON ---
class UserDataDict(TypedDict):
    username: str
    password_hash: str
    registration_date: str
    inventory: List[ItemSerializedDict]


# --- КЛАСС ПОЛЬЗОВАТЕЛЯ (USER) ---
@dataclass
class User:
    username: str
    password: (
        str  # Сюда передается обычный текст, но в __post_init__ он превращается в хеш
    )
    registration_date: date = field(default_factory=date.today)
    # Флаг-предохранитель. Если True, класс знает, что пароль уже захеширован, и не трогает его повторно.
    is_hashed: bool = field(default=False, repr=False, compare=False)
    inventory: "Inventory" = field(init=False)

    def __post_init__(self):
        # Отложенный импорт Inventory предотвращает круговую зависимость модулей (Circular Import)
        from models import Inventory

        self.inventory = Inventory()

        # Перехватываем сырой пароль при создании НОВОГО пользователя и превращаем в SHA-256 хеш
        if not self.is_hashed:
            self.password = hashlib.sha256(self.password.encode("utf-8")).hexdigest()
            self.is_hashed = True
            log_info(
                f"In-class password encapsulation executed. Password hashed for user: {self.username!r}"
            )

    def check_password(self, incoming_plaintext: str) -> bool:
        """Берет введенный в GUI сырой текст, хеширует и сверяет с сохраненным эталоном."""
        incoming_hash = hashlib.sha256(incoming_plaintext.encode("utf-8")).hexdigest()
        return self.password == incoming_hash

    @staticmethod
    def is_valid_username(username: str) -> bool:
        """Проверяет, что имя содержит только латиницу, цифры и подчеркивания (безопасно для файлов)."""
        return bool(re.match(r"^[a-zA-Z0-9_]{3,20}$", username))

    def save(self) -> None:
        """Безопасное атомное сохранение инвентаря на диск."""
        if not self.is_valid_username(self.username):
            raise ValueError("Invalid username character set.")

        save_path: Path = UserData / f"{self.username}.json"
        tmp_path: Path = UserData / f"{self.username}.json.tmp"

        # Сериализация (код остаётся прежним)
        items_serialized: list[ItemSerializedDict] = [
            {
                "id": item.id,
                "category": item.category.value,
                "name": item.name,
                "manufacturer": item.manufacturer,
                "amount": item.amount,
                "condition": item.condition.value,
                "icon_path": str(item.icon_path),
                "stackable": item.stackable,
                "max_stack": item.max_stack,
            }
            for item in self.inventory.items
        ]

        user_data: UserDataDict = {
            "username": self.username,
            "password_hash": self.password,
            "registration_date": self.registration_date.strftime(date_format),
            "inventory": items_serialized,
        }

        # НОВАЯ ЛОГИКА: Пишем сначала в .tmp файл
        try:
            tmp_path.write_text(
                json.dumps(user_data, indent=2, ensure_ascii=False), encoding=encoding
            )
            # Если записалось без ошибок — атомарно заменяем старый файл новым
            tmp_path.replace(save_path)
            log_info(f"Atomic disk sync successful for user: {self.username!r}")
        except Exception as e:
            log_error(f"Atomic save failed for user {self.username!r}: {e}")
            if tmp_path.exists():
                tmp_path.unlink()  # Чистим за собой мусор
            raise e

    @classmethod
    def load(cls, username: str) -> "User":
        """Загружает профиль пользователя и весь его инвентарь из JSON-файла."""
        save_path: Path = UserData / f"{username}.json"
        if not save_path.exists():
            log_error(
                f"Failed login attempt: User profile file {username!r} was not found on disk storage."
            )
            raise ValueError(f"Profile {username} not found.")

        userdata = json.loads(save_path.read_text(encoding=encoding))
        reg_date = datetime.strptime(userdata["registration_date"], date_format).date()

        # Важно: передаем флаг is_hashed=True, чтобы конструктор класса НЕ захешировал хеш заново!
        user = cls(
            username=userdata["username"],
            password=userdata["password_hash"],
            registration_date=reg_date,
            is_hashed=True,
        )

        # Восстанавливаем объекты предметов из словарей
        for it in userdata.get("inventory", []):
            try:
                cat = ItemType(it["category"])
                cond = ItemCondition(it.get("condition", "new"))
            except ValueError:
                log_error(
                    f"Skipping corrupted database entry loading sequence for user {username!r}"
                )
                continue

            item = Item(
                id=it.get("id", str(uuid.uuid4())),
                category=cat,
                name=it["name"],
                manufacturer=it["manufacturer"],
                amount=int(it["amount"]),
                condition=cond,
                icon_path=Path(it.get("icon_path", Icons / "icon.png")),
                stackable=bool(it.get("stackable", False)),
                max_stack=it.get("max_stack"),
            )
            user.inventory.items.append(item)

        log_info(f"User profile loaded successfully from disk database: {username!r}")
        return user
