"""
config.py
Глобальная конфигурация приложения. Включает автоматическую сборку
инфраструктуры папок и загрузку дефолтных графических ассетов.
"""

import urllib.request  # Понадобится для скачивания иконок по URL
from datetime import datetime
from enum import StrEnum
from pathlib import Path

# --- НАСТРОЙКИ ПУТЕЙ (PROJECT PATHS) ---
SCRIPT_DIR: Path = Path(__file__).resolve().parent
ROOT_DIR: Path = SCRIPT_DIR.parent

Icons: Path = ROOT_DIR / "assets" / "icons"
Data: Path = ROOT_DIR / "assets" / "data"
UserData: Path = Data / "user"
ItemGeneratorData: Path = Data / "itemgenerator"
Logs: Path = ROOT_DIR / "Logs"

date_format = "%d.%m.%Y"
time_format = "%Y.%m.%d %H-%M-%S"
encoding = "utf-8"


# --- СИСТЕМА ЛОГИРОВАНИЯ ---
def _get_log_file() -> Path:
    log_filename = datetime.today().strftime(date_format)
    return Logs / f"{log_filename}.log"


def log_info(message: str) -> None:
    log_file: Path = _get_log_file()
    timestamp: str = datetime.now().strftime(time_format)
    try:
        with log_file.open("a", encoding=encoding) as f:
            f.write(f"{timestamp} -- INFO -- {message}\n")
    except IOError:
        pass


def log_error(message: str) -> None:
    log_file: Path = _get_log_file()
    timestamp: str = datetime.now().strftime(time_format)
    try:
        with log_file.open("a", encoding=encoding) as f:
            f.write(f"{timestamp} -- ERROR -- {message}\n")
    except IOError:
        pass


# --- ССЫЛКИ НА ОТКРЫТЫЕ ИКОНКИ (Icons Bootstrap CDN) ---
ICON_URLS: dict[str, str] = {
    "default": "https://img.icons8.com/ios-filled/100/trophy.png",
    "cardio_machine": "https://img.icons8.com/ios-filled/100/treadmill.png",
    "strength_machine": "https://img.icons8.com/ios-filled/100/gym.png",
    "free_weight": "https://img.icons8.com/ios-filled/100/dumbbell.png",
    "bench": "https://img.icons8.com/ios-filled/100/bench-press.png",
    "flexibility_equipment": "https://img.icons8.com/ios-filled/100/yoga.png",
    "ball": "https://img.icons8.com/ios-filled/100/soccer-ball.png",
    "sports_gear": "https://img.icons8.com/ios-filled/100/tennis.png",
    "protective_gear": "https://img.icons8.com/ios-filled/100/boxing.png",
    "clothing_small": "https://img.icons8.com/ios-filled/100/sneakers.png",
    "accessory": "https://img.icons8.com/ios-filled/100/stopwatch.png",
}


def init_storage() -> None:
    """Создает структуру папок и скачивает недостающие графические ассеты."""
    # 1. Создаем папки
    for folder in [Data, UserData, ItemGeneratorData, Icons, Logs]:
        folder.mkdir(parents=True, exist_ok=True)

    # 2. Скачиваем базовые иконки, если папка пуста (Защита от микрофризов)
    print("Checking system graphical assets...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for icon_name, url in ICON_URLS.items():
        target_path = Icons / f"{icon_name}.png"
        if not target_path.exists():
            try:
                print(f"Downloading asset: {icon_name}.png ...")
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=5) as response:
                    target_path.write_bytes(response.read())
                log_info(f"Asset bootstrapped from cloud storage: {icon_name}.png")
            except Exception as e:
                log_error(f"Failed to download icon {icon_name}: {e}")
                print(
                    f"[WARNING] Could not download {icon_name}.png (No internet or timeout)."
                )


# --- СИСТЕМА ЛОКАЛИЗАЦИИ ---
class AppLanguage(StrEnum):
    RU = "ru"
    EN = "en"


CURRENT_LANGUAGE: AppLanguage = AppLanguage.RU

TRANSLATIONS = {
    AppLanguage.RU: {
        "title_auth": "Авторизация",
        "title_main": "Спортивный инвентарь — Прототип БД",
        "btn_login": "Войти",
        "btn_register": "Регистрация",
        "btn_add": "Добавить предмет",
        "btn_delete": "Удалить",
        "btn_edit": "Изменить",
        "lbl_username": "Имя пользователя:",
        "lbl_password": "Пароль:",
        "prop_name": "Название",
        "prop_manufacturer": "Производитель",
        "prop_amount": "Количество",
        "prop_condition": "Состояние",
        "prop_category": "Категория",
        "cat_cardio_machine": "Кардиотренажёр",
        "cat_strength_machine": "Силовой тренажёр",
        "cat_free_weight": "Свободные веса",
        "cat_bench": "Скамья и стойки",
        "cat_flexibility_equipment": "Оборудование для гибкости",
        "cat_ball": "Мяч",
        "cat_sports_gear": "Игровой инвентарь",
        "cat_protective_gear": "Защитный инвентарь",
        "cat_clothing_small": "Малые вещи",
        "cat_accessory": "Аксессуары",
        "cond_new": "Новое",
        "cond_used": "Б/У",
        "cond_broken": "Требует ремонта",
    },
    AppLanguage.EN: {
        "title_auth": "Authentication",
        "title_main": "Sports Gear — Prototype DB",
        "btn_login": "Log In",
        "btn_register": "Register",
        "btn_add": "Add Item",
        "btn_delete": "Delete",
        "btn_edit": "Edit",
        "lbl_username": "Username:",
        "lbl_password": "Password:",
        "prop_name": "Name",
        "prop_manufacturer": "Manufacturer",
        "prop_amount": "Amount",
        "prop_condition": "Condition",
        "prop_category": "Category",
        "cat_cardio_machine": "Cardio Machine",
        "cat_strength_machine": "Strength Machine",
        "cat_free_weight": "Free Weights",
        "cat_bench": "Benches & Racks",
        "cat_flexibility_equipment": "Flexibility Equipment",
        "cat_ball": "Ball",
        "cat_sports_gear": "Sports Gear",
        "cat_protective_gear": "Protective Gear",
        "cat_clothing_small": "Small Apparel",
        "cat_accessory": "Accessories",
        "cond_new": "New",
        "cond_used": "Used",
        "cond_broken": "Needs Repair",
    },
}


def t(key: str) -> str:
    return TRANSLATIONS[CURRENT_LANGUAGE].get(key, f"[{key}]")
