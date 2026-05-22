"""
auth.py
Управляет учётными записями пользователей (User), хешированием паролей и сохранением данных на диск.
"""

import hashlib
import json
import os  # Понадобится для генерации безопасной соли через os.urandom
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


# --- СТРУКТУРА ДАННЫХ ПОЛЬЗОВАТЕЛЯ ДЛЯ JSON (ОБНОВЛЕННАЯ) ---
class UserDataDict(TypedDict):
    username: str
    password_hash: str
    password_salt: str  # ТИПИЗАЦИЯ: Добавили поле для хранения уникальной соли
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
    is_hashed: bool = field(default=False, repr=False, compare=False)

    # ТИПИЗАЦИЯ: Хранилище соли для текущего пользователя
    password_salt: str = field(default="", repr=False, compare=False)
    inventory: "Inventory" = field(default_factory=Inventory)

    def __post_init__(self) -> None:
        """
        Если объект создается впервые (регистрация), генерируем соль и хешируем пароль.
        Если объект восстанавливается из БД, флаг is_hashed=True предотвратит повторный прогон.
        """
        if not self.is_hashed:
            # Генерируем 16 случайных байт и переводим в hex-строку (32 символа)
            self.password_salt = os.urandom(16).hex()

            # Склеиваем сырой пароль с солью перед хешированием
            salted_password = self.password + self.password_salt

            # Превращаем в криптостойкий SHA-256 хеш
            self.password = hashlib.sha256(salted_password.encode(encoding)).hexdigest()
            self.is_hashed = True

    def verify_password(self, plain_password: str) -> bool:
        """
        Проверяет, соответствует ли введенный пользователем сырой пароль текущему хешу.
        """
        salted = plain_password + self.password_salt
        calculated_hash = hashlib.sha256(salted.encode(encoding)).hexdigest()
        return self.password == calculated_hash

    @staticmethod
    def is_valid_username(username: str) -> bool:
        """Проверяет, что имя содержит только латиницу, цифры и подчеркивания (безопасно для файлов)."""
        return bool(re.match(r"^[a-zA-Z0-9_]{3,20}$", username))

    def save(self) -> None:
        """Сохраняет профиль пользователя на диск с атомарной гарантией."""
        save_path = UserData / f"{self.username}.json"
        tmp_path = UserData / f"{self.username}.json.tmp"

        # Собираем словарь, включая соль
        userdata: UserDataDict = {
            "username": self.username,
            "password_hash": self.password,
            "password_salt": self.password_salt,  # Запись соли в файл
            "registration_date": self.registration_date.strftime(date_format),
            "inventory": [
                {
                    "id": it.id,
                    "category": it.category.value,
                    "name": it.name,
                    "manufacturer": it.manufacturer,
                    "amount": it.amount,
                    "condition": it.condition.value,
                    "icon_path": str(it.icon_path),
                    "stackable": it.stackable,
                    "max_stack": it.max_stack,
                }
                for it in self.inventory.items
            ],
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
        """Загружает профиль пользователя. Выбрасывает кастомное исключение при ошибке."""
        save_path = UserData / f"{username}.json"
        if not save_path.exists():
            # Заменили общий ValueError на кастомный типизированный класс
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
                password_salt=userdata.get("password_salt", ""),  # Безопасный сбор соли
            )

            for it in userdata.get("inventory", []):
                try:
                    cat = ItemType(it["category"])
                    cond = ItemCondition(it.get("condition", "new"))
                except ValueError:
                    log_error(
                        f"Skipping corrupted database entry for user {username!r}"
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

            log_info(f"User profile loaded from database: '{username}'")
            return user
        except Exception as e:
            log_error(f"Failed to compile user entity from JSON {username}: {e}")
            raise IOError("Corrupted database layout context.")


def register_user(username: str, plain_password: str) -> User:
    """
    Регистрирует нового пользователя в системе.
    Если имя занято, выбрасывает UserAlreadyExistsError.
    """
    # Приводим к нижнему регистру или обрезаем пробелы, если нужно (базовая валидация)
    clean_username = username.strip()

    # Путь к потенциальному файлу в БД
    user_file = UserData / f"{clean_username}.json"

    if user_file.exists():
        # ИСПОЛЬЗОВАНИЕ №1: Защита от дубликатов
        raise UserAlreadyExistsError(f"Username '{clean_username}' is already taken.")

    # Создаем нового пользователя (здесь сработает __post_init__ и захеширует пароль с солью)
    new_user = User(username=clean_username, password=plain_password)
    new_user.save()

    log_info(f"New user database record generated for: '{clean_username}'")
    return new_user


def authenticate_user(username: str, plain_password: str) -> User:
    """
    Проверяет учетные данные пользователя.
    Выбрасывает UserNotFoundError, если пользователя нет,
    и InvalidPasswordError, если пароль не подошел.
    """
    clean_username = username.strip()

    # Загружаем пользователя. Если файла нет, load() сам выбросит UserNotFoundError
    user = User.load(clean_username)

    # Проверяем пароль с учетом соли
    if not user.verify_password(plain_password):
        # ИСПОЛЬЗОВАНИЕ №2: Защита от неверного пароля
        raise InvalidPasswordError("The password provided is incorrect.")

    log_info(f"Credentials successfully verified for user: '{clean_username}'")
    return user


# =====================================================================
# ВЫДЕЛЕННЫЙ МЕНЕДЖЕР СЕССИЙ (SESSION MANAGER — SINGLETON)
# =====================================================================
class SessionManager:
    """
    Менеджер сессий (Singleton).
    Централизованно хранит информацию о текущем вошедшем пользователе.
    Безопасен для импорта во все UI-окна.
    """

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
        """
        Возвращает объект текущего активного пользователя.
        ТИПИЗАЦИЯ: Если пользователь не авторизован, выбрасывает SessionError,
        благодаря чему тайп-чекер гарантирует, что возвращенный объект ВСЕГДА имеет тип User.
        """
        if self._current_user is None:
            raise SessionError("Unauthorized state. Access to current_user is denied.")
        return self._current_user

    def start_session(self, user: User) -> None:
        """Регистрирует успешный вход пользователя в систему."""
        self._current_user = user
        log_info(f"User session successfully started for: '{user.username}'")

    def close_session(self) -> None:
        """Завершает текущую сессию (выход из аккаунта)."""
        if self._current_user:
            log_info(f"User session closed for: '{self._current_user.username}'")
        self._current_user = None

    def is_active(self) -> bool:
        """Возвращает True, если в системе есть авторизованный пользователь."""
        return self._current_user is not None


# Глобальная точка доступа для UI-компонентов
session_manager = SessionManager()
