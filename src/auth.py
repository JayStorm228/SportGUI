"""
auth.py
Управляет учётными записями пользователей (User), хешированием паролей и сохранением данных на диск.
"""

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, TypedDict

from config import Icons, UserData, date_format, encoding, log_error, log_info
from exceptions import (
    InvalidPasswordError,
    SessionError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from models import Inventory, Item, ItemCondition, ItemSerializedDict, ItemType


class UserDataDict(TypedDict):
    username: str
    password_hash: str
    password_salt: str
    registration_date: str
    inventory: List[ItemSerializedDict]


@dataclass
class User:
    username: str
    password: str
    registration_date: date = field(default_factory=date.today)
    is_hashed: bool = field(default=False, repr=False, compare=False)
    password_salt: str = field(default="", repr=False, compare=False)
    inventory: "Inventory" = field(default_factory=Inventory)

    def __post_init__(self) -> None:
        if not self.is_hashed:
            self.password_salt = os.urandom(16).hex()
            salted_password = self.password + self.password_salt
            self.password = hashlib.sha256(salted_password.encode(encoding)).hexdigest()
            self.is_hashed = True

    def verify_password(self, plain_password: str) -> bool:
        salted = plain_password + self.password_salt
        calculated_hash = hashlib.sha256(salted.encode(encoding)).hexdigest()
        return self.password == calculated_hash

    @staticmethod
    def is_valid_username(username: str) -> bool:
        return bool(re.match(r"^[a-zA-Z0-9_]{3,20}$", username))

    def save(self) -> None:
        """Сохраняет профиль пользователя на диск с атомарной гарантией."""
        save_path = UserData / f"{self.username}.json"
        tmp_path = UserData / f"{self.username}.json.tmp"

        from config import ROOT_DIR

        inventory_data = []
        for it in self.inventory.items:
            # ИСПРАВЛЕНИЕ: Конвертируем путь к иконке в переносимый относительный (Bug 2)
            icon_path_str = ""
            if it.icon_path:
                try:
                    # Преобразуем абсолютный путь в относительный к ROOT_DIR
                    icon_path_str = it.icon_path.relative_to(ROOT_DIR).as_posix()
                except ValueError:
                    # Если путь лежит вне папки проекта, сохраняем только имя файла
                    icon_path_str = Path(it.icon_path).name
            if not icon_path_str:
                icon_path_str = "assets/icons/default.png"

            inventory_data.append(
                {
                    "id": it.id,
                    "category": it.category.value,
                    "name": it.name,
                    "manufacturer": it.manufacturer,
                    "amount": it.amount,
                    "condition": it.condition.value,
                    "icon_path": icon_path_str,
                    "stackable": it.stackable,
                    "max_stack": it.max_stack,
                }
            )

        userdata: UserDataDict = {
            "username": self.username,
            "password_hash": self.password,
            "password_salt": self.password_salt,
            "registration_date": self.registration_date.strftime(date_format),
            "inventory": inventory_data,
        }

        try:
            tmp_path.write_text(
                json.dumps(userdata, indent=4, ensure_ascii=False), encoding=encoding
            )
            if save_path.exists():
                save_path.unlink()
            tmp_path.rename(save_path)
            log_info(f"User profile metadata securely deployed for: '{self.username}'")
        except Exception as e:
            log_error(f"Atomic file write disruption for user {self.username}: {e}")
            if tmp_path.exists():
                tmp_path.unlink()
            raise IOError("Database transaction sequence failed.")

    @classmethod
    def load(cls, username: str) -> "User":
        save_path = UserData / f"{username}.json"
        if not save_path.exists():
            raise UserNotFoundError(
                f"User database records for {username!r} do not exist."
            )

        try:
            userdata: UserDataDict = json.loads(save_path.read_text(encoding=encoding))
            reg_date = datetime.strptime(
                userdata["registration_date"], date_format
            ).date()

            user = cls(
                username=userdata["username"],
                password=userdata["password_hash"],
                registration_date=reg_date,
                is_hashed=True,
                password_salt=userdata.get("password_salt", ""),
            )

            from config import ROOT_DIR

            for it in userdata.get("inventory", []):
                try:
                    cat = ItemType(it["category"])
                    cond = ItemCondition(it.get("condition", "new"))
                except ValueError:
                    log_error(
                        f"Skipping corrupted database entry for user {username!r}"
                    )
                    continue

                # ИСПРАВЛЕНИЕ: Восстанавливаем переносимый относительный путь до абсолютного
                icon_path_str = it.get("icon_path")
                if not icon_path_str or icon_path_str == "None":
                    icon_path_val = Icons / "default.png"
                else:
                    # 1. Проверяем относительный путь
                    resolved_path = ROOT_DIR / icon_path_str
                    if resolved_path.exists():
                        icon_path_val = resolved_path
                    else:
                        # 2. Проверяем абсолютный путь (поддержка старых БД)
                        alt_path = Path(icon_path_str)
                        if alt_path.is_absolute() and alt_path.exists():
                            icon_path_val = alt_path
                        else:
                            # 3. Проверяем по имени файла в папке Icons
                            fn_path = Icons / alt_path.name
                            if fn_path.exists():
                                icon_path_val = fn_path
                            else:
                                icon_path_val = Icons / "default.png"

                max_stack_val = it.get("max_stack")
                if max_stack_val is not None:
                    try:
                        max_stack_val = int(max_stack_val)
                    except (ValueError, TypeError):
                        max_stack_val = None

                item = Item(
                    id=it.get("id", str(uuid.uuid4())),
                    category=cat,
                    name=it["name"],
                    manufacturer=it["manufacturer"],
                    amount=int(it["amount"]),
                    condition=cond,
                    icon_path=icon_path_val,
                    stackable=bool(it.get("stackable", False)),
                    max_stack=max_stack_val,
                )
                user.inventory.items.append(item)

            log_info(f"User profile loaded from database: '{username}'")
            return user
        except Exception as e:
            log_error(f"Failed to compile user entity from JSON {username}: {e}")
            raise IOError("Corrupted database layout context.")


def register_user(username: str, plain_password: str) -> User:
    clean_username = username.strip()
    user_file = UserData / f"{clean_username}.json"

    if user_file.exists():
        raise UserAlreadyExistsError(f"Username '{clean_username}' is already taken.")

    new_user = User(username=clean_username, password=plain_password)
    new_user.save()

    log_info(f"New user database record generated for: '{clean_username}'")
    return new_user


def authenticate_user(username: str, plain_password: str) -> User:
    clean_username = username.strip()
    user = User.load(clean_username)

    if not user.verify_password(plain_password):
        raise InvalidPasswordError("The password provided is incorrect.")

    log_info(f"Credentials successfully verified for user: '{clean_username}'")
    return user


class SessionManager:
    """Менеджер сессий (Singleton)."""

    _instance: Optional["SessionManager"] = None

    def __new__(cls) -> "SessionManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._current_user: Optional[User] = None
        self._initialized: bool = True

    @property
    def current_user(self) -> User:
        if self._current_user is None:
            raise SessionError("Unauthorized state. Access to current_user is denied.")
        return self._current_user

    def start_session(self, user: User) -> None:
        self._current_user = user
        # Интегрируем паттерн Слушатель для автоматического сохранения изменений инвентаря
        self._current_user.inventory.subscribe(self._current_user.save)
        log_info(f"User session successfully started for: '{user.username}'")

    def close_session(self) -> None:
        if self._current_user:
            self._current_user.inventory.unsubscribe(self._current_user.save)
            log_info(f"User session closed for: '{self._current_user.username}'")
        self._current_user = None

    def is_active(self) -> bool:
        return self._current_user is not None

    def get_available_usernames(self) -> List[str]:
        if not UserData.exists():
            return []
        return [file_path.stem for file_path in UserData.glob("*.json")]


session_manager = SessionManager()
