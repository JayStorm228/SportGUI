"""
config.py (Скорректированная версия под структуру src/)
"""

import sys
from datetime import datetime
from pathlib import Path

# --- НАСТРОЙКИ ПУТЕЙ (PROJECT PATHS) ---
# SCRIPT_DIR теперь указывает на папку 'src'
SCRIPT_DIR: Path = Path(__file__).resolve().parent

# Проверяем, запущено ли приложение как скомпилированный EXE (PyInstaller)
IS_FROZEN = getattr(sys, "frozen", False)

if IS_FROZEN:
    # В скомпилированном виде корневая папка - это папка с EXE (внутри папки установки)
    ROOT_DIR: Path = Path(sys.executable).resolve().parent
else:
    # В режиме разработки config.py лежит в src/, поэтому корень проекта - это родительская папка src/ (SPORTGUI)
    ROOT_DIR: Path = SCRIPT_DIR.parent

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
    "default": "https://img.icons8.com/ios-filled/100/sports-mode.png",
    "icon": "https://img.icons8.com/ios-filled/100/sports-mode.png",
    "cardio_machine": "https://img.icons8.com/ios-filled/100/treadmill.png",
    "strength_machine": "https://img.icons8.com/ios-filled/100/barbell.png",
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
    """Создает структуру папок. Скачивание ассетов перенесено во вспомогательный поток UI."""
    for folder in [Data, UserData, ItemGeneratorData, Icons, Logs, LangData, ThemeData]:
        folder.mkdir(parents=True, exist_ok=True)
