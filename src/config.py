"""
config.py
Глобальная конфигурация приложения. Включает автоматическую сборку
инфраструктуры папок, загрузку ассетов и инициализацию подсистем UI.
"""

import urllib.request
from datetime import datetime
from pathlib import Path

# --- НАСТРОЙКИ ПУТЕЙ (PROJECT PATHS) ---
SCRIPT_DIR: Path = Path(__file__).resolve().parent
ROOT_DIR: Path = SCRIPT_DIR.parent

# Выделенные папки под архитектуру UI по твоему запросу
LangData: Path = ROOT_DIR / "local" / "lang"
ThemeData: Path = ROOT_DIR / "local" / "theme"

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


# --- ССЫЛКИ НА ИКОНКИ ---
ICON_URLS: dict[str, str] = {
    "icon": "https://img.icons8.com/ios-filled/100/sports-mode.png",
    "cardio_machine": "https://img.icons8.com/ios-filled/100/treadmill.png",
    "strength_machine": "https://img.icons8.com/ios-filled/100/gym.png",  # <-- Новый рабочий URL
    "free_weight": "https://img.icons8.com/ios-filled/100/dumbbell.png",
    "bench": "https://img.icons8.com/ios-filled/100/bench-press.png",
    "flexibility_equipment": "https://img.icons8.com/ios-filled/100/yoga.png",
    "ball": "https://img.icons8.com/ios-filled/100/basketball.png",
    "sports_gear": "https://img.icons8.com/ios-filled/100/badminton.png",
    "protective_gear": "https://img.icons8.com/ios-filled/100/boxing-glove.png",
    "clothing_small": "https://img.icons8.com/ios-filled/100/sneakers.png",
    "accessory": "https://img.icons8.com/ios-filled/100/stopwatch.png",
}


def init_storage() -> None:
    """Создает структуру папок и генерирует базовые ассеты/конфиги."""
    # 1. Генерируем папки, включая новые директории локализации и тем
    for folder in [Data, UserData, ItemGeneratorData, Icons, Logs, LangData, ThemeData]:
        folder.mkdir(parents=True, exist_ok=True)

    # 2. Скачиваем базовые иконки
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
                print(f"[WARNING] Could not download {icon_name}.png")


# --- ИНИЦИАЛИЗАЦИЯ ПОД СИСТЕМ UI МЕНЕДЖЕРОВ ---
# Импортируем созданные классы
from ui_managers import LocalizationManager, ThemeManager

# Инициализируем синглтоны. При первом запуске они подгрузят дефолтные файлы.
# (В реальном приложении мы бы сначала проверили наличие json, но синглтоны умеют возвращать заглушки)
lang_manager = LocalizationManager(LangData, default_lang="ru")
theme_manager = ThemeManager(ThemeData, default_theme="dark")


# Прокси-функция перевода, чтобы остальному коду не пришлось менять сигнатуру вызова
def t(key: str, **kwargs: str | int) -> str:
    """
    Глобальный мост локализации.
    ТИПИЗАЦИЯ: kwargs принимает только строки или числа для подстановки в шаблоны строк.
    """
    return lang_manager.translate(key, **kwargs)
