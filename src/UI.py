"""
UI.py
Модуль графических компонентов интерфейса PySide6.
Содержит виджеты, диалоги, страницы авторизации, дешборда и настройки стилей.
"""

import json
import re
import ssl
import time
import urllib.request
import uuid
from pathlib import Path

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPointF,
    QPropertyAnimation,
    Qt,
    QThread,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from auth import authenticate_user, register_user, session_manager

# Импорты бэкенд-компонентов
from config import (
    ICON_URLS,
    Icons,
    ItemGeneratorData,
    LangData,
    ThemeData,
    init_storage,
    log_error,
    log_info,
)
from exceptions import InvalidPasswordError, UserAlreadyExistsError, UserNotFoundError
from generator import generate_random_item
from models import Item, ItemCondition, ItemType


# =====================================================================
# МЕНЕДЖЕРЫ РЕСУРСОВ (ЛОКАЛИЗАЦИЯ И ТЕМАТИЗАЦИЯ - SINGLETON)
# =====================================================================
class TranslationManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.current_lang = "ru"
            cls._instance.translations = {}
        return cls._instance

    def load_lang(self, lang_code: str):
        file_path = LangData / f"{lang_code}.json"
        if file_path.exists():
            try:
                self.translations = json.loads(file_path.read_text(encoding="utf-8"))
                self.current_lang = lang_code
            except Exception as e:
                log_error(f"Failed to load translation {lang_code}: {e}")

    def get(self, key: str, default: str = None, **kwargs) -> str:
        val = self.translations.get(key, default or key)
        if kwargs:
            try:
                return val.format(**kwargs)
            except Exception:
                return val
        return val


class ThemeManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.current_theme = "dark"
            cls._instance.theme_data = {}
        return cls._instance

    def load_theme(self, theme_name: str):
        file_path = ThemeData / f"{theme_name}.json"
        if file_path.exists():
            try:
                self.theme_data = json.loads(file_path.read_text(encoding="utf-8"))
                self.current_theme = theme_name
            except Exception as e:
                log_error(f"Failed to load theme {theme_name}: {e}")

    def get(self, key: str, default: str = "") -> str:
        return self.theme_data.get(key, default)


def generate_qss(theme: dict) -> str:
    """Генератор глобального QSS на основе переданного словаря темы."""
    bg_main = theme.get("bg_main", "#1e1e1e")
    bg_dark = theme.get("bg_dark", "#121212")
    bg_card = theme.get("bg_card", "#2d2d2d")
    text_primary = theme.get("text_primary", "#ffffff")
    text_secondary = theme.get("text_secondary", "#aaaaaa")
    text_light = theme.get("text_light", "#ffffff")
    border_color = theme.get("border_color", "#3f3f46")
    accent_primary = theme.get("accent_primary", "#007acc")
    accent_hover = theme.get("accent_hover", "#1f8ad2")
    font_main = theme.get("font_main", "'Segoe UI'")

    qss = f"""
    QWidget {{
        background-color: {bg_main};
        color: {text_primary};
        font-family: {font_main};
        font-size: 13px;
    }}

    QMainWindow {{
        background-color: {bg_dark};
    }}

    QFrame#AuthCard {{
        background-color: {bg_card};
        border: 1px solid {border_color};
        border-radius: 12px;
    }}

    QLineEdit {{
        background-color: {bg_dark};
        border: 1px solid {border_color};
        border-radius: 6px;
        padding: 8px;
        color: {text_primary};
    }}

    QLineEdit:focus {{
        border: 1px solid {accent_primary};
    }}

    QPushButton {{
        background-color: {accent_primary};
        color: {text_light};
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: bold;
    }}

    QPushButton:hover {{
        background-color: {accent_hover};
    }}

    QPushButton:disabled {{
        background-color: {border_color};
        color: {text_secondary};
    }}

    QComboBox {{
        background-color: {bg_card};
        border: 1px solid {border_color};
        border-radius: 6px;
        padding: 6px;
        color: {text_primary};
    }}

    QComboBox::drop-down {{
        border: none;
    }}

    QFrame#MenuGroup {{
        background-color: {bg_dark};
        border: 1px solid {border_color};
        border-radius: 8px;
    }}

    QFrame#EmptyCell {{
        border: 2px dashed {border_color};
        border-radius: 8px;
        background-color: transparent;
    }}

    QScrollBar:vertical {{
        border: none;
        background: {bg_dark};
        width: 10px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background: {border_color};
        min-height: 20px;
        border-radius: 5px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {accent_primary};
    }}

    QSplitter::handle {{
        background-color: {border_color};
    }}
    """
    return qss


# =====================================================================
# КОМПОНЕНТЫ ЗАГРУЗКИ И ШЕСТЕРНИ (PAINT-ЭЛЕМЕНТЫ)
# =====================================================================
class RotatingGearWidget(QWidget):
    """Кастомный виджет рендеринга и анимации шестерни на чистом QPainter."""

    def __init__(self, parent=None, size=64):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_angle)
        self.timer.start(16)  # ~60 fps
        self.color = QColor("#007acc")

    def set_color(self, hex_color):
        self.color = QColor(hex_color)
        self.update()

    def update_angle(self):
        self.angle = (self.angle + 1) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() / 2.0
        cy = self.height() / 2.0

        painter.translate(cx, cy)
        painter.rotate(self.angle)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.color)

        num_teeth = 8
        outer_r = self.width() / 2.0
        inner_r = outer_r * 0.7
        hole_r = outer_r * 0.25

        path = QPainterPath()
        path.addEllipse(QPointF(0, 0), inner_r, inner_r)

        for _ in range(num_teeth):
            painter.rotate(360 / num_teeth)
            tooth_path = QPainterPath()
            poly = QPolygonF(
                [
                    QPointF(-outer_r * 0.15, -inner_r + 1),
                    QPointF(-outer_r * 0.1, -outer_r),
                    QPointF(outer_r * 0.1, -outer_r),
                    QPointF(outer_r * 0.15, -inner_r + 1),
                ]
            )
            tooth_path.addPolygon(poly)
            path = path.united(tooth_path).simplified()

        hole_path = QPainterPath()
        hole_path.addEllipse(QPointF(0, 0), hole_r, hole_r)
        gear_path = path.subtracted(hole_path)

        painter.drawPath(gear_path)


class BootstrapperThread(QThread):
    """Асинхронный бутстраппер для инициализации системы и загрузки ассетов."""

    progress_changed = Signal(int, str)
    finished_loading = Signal()

    def run(self):
        # Шаг 1: Инициализация файловой структуры
        self.progress_changed.emit(10, "lbl_loading_folders")
        time.sleep(0.3)
        init_storage()

        # Шаг 2: Генерация конфигураций
        self.progress_changed.emit(30, "lbl_loading_configs")
        time.sleep(0.3)
        self.write_blueprints()

        # Шаг 3: Проверка и асинхронное скачивание ассетов
        self.progress_changed.emit(60, "lbl_loading_assets")
        self.download_assets()

        # Инициализация менеджеров ресурсов перед открытием окон
        TranslationManager().load_lang("ru")
        ThemeManager().load_theme("dark")

        self.progress_changed.emit(100, "lbl_loading_ready")
        time.sleep(0.3)
        self.finished_loading.emit()

    def write_blueprints(self):
        """Инсталляция переводов и тем по умолчанию, если они отсутствуют."""
        # Тема Dark
        dark_file = ThemeData / "dark.json"
        if not dark_file.exists():
            dark_file.write_text(
                json.dumps(
                    {
                        "bg_main": "#1e1e1e",
                        "bg_dark": "#121212",
                        "bg_card": "#2d2d2d",
                        "text_primary": "#ffffff",
                        "text_secondary": "#aaaaaa",
                        "text_light": "#ffffff",
                        "border_color": "#3f3f46",
                        "accent_primary": "#007acc",
                        "accent_hover": "#1f8ad2",
                        "font_main": "'Segoe UI', sans-serif",
                        "size_body": "13px",
                    },
                    indent=4,
                ),
                encoding="utf-8",
            )

        # Тема Light
        light_file = ThemeData / "light.json"
        if not light_file.exists():
            light_file.write_text(
                json.dumps(
                    {
                        "bg_main": "#f4f4f5",
                        "bg_dark": "#e4e4e7",
                        "bg_card": "#ffffff",
                        "text_primary": "#18181b",
                        "text_secondary": "#71717a",
                        "text_light": "#ffffff",
                        "border_color": "#d4d4d8",
                        "accent_primary": "#2563eb",
                        "accent_hover": "#1d4ed8",
                        "font_main": "'Segoe UI', sans-serif",
                        "size_body": "13px",
                    },
                    indent=4,
                ),
                encoding="utf-8",
            )

        # Локализация ru.json
        ru_file = LangData / "ru.json"
        if not ru_file.exists():
            ru_file.write_text(
                json.dumps(
                    {
                        "title_auth": "Авторизация",
                        "title_register": "Регистрация",
                        "title_main": "Спортивный инвентарь — Прототип БД",
                        "lbl_loading": "Загрузка системы... ",
                        "lbl_username": "Имя пользователя",
                        "lbl_password": "Пароль",
                        "lbl_total_items": "Предметов: {count}",
                        "lbl_version": "Версия: {version}",
                        "lbl_filters_title": "Фильтры и поиск",
                        "lbl_search_placeholder": "Поиск по названию/производителю...",
                        "lbl_sort_placeholder": "Сортировка...",
                        "btn_login": "Войти",
                        "btn_register": "Зарегистрироваться",
                        "btn_goto_register": "Зарегистрировать новый профиль",
                        "btn_goto_login": "Уже есть аккаунт? Войти",
                        "btn_add": "Добавить предмет",
                        "btn_add_manual": "Новый предмет",
                        "btn_add_rand": "Случайный предмет",
                        "btn_delete": "Удалить",
                        "btn_edit": "Редактировать",
                        "prop_name": "Наименование",
                        "prop_manufacturer": "Производитель",
                        "prop_amount": "Количество",
                        "prop_condition": "Состояние",
                        "prop_category": "Категория",
                        "cat_cardio_machine": "Кардиотренажеры",
                        "cat_strength_machine": "Силовые тренажеры",
                        "cat_free_weight": "Свободные веса",
                        "cat_bench": "Скамьи и стойки",
                        "cat_flexibility_equipment": "Снаряды для растяжки",
                        "cat_ball": "Мячи",
                        "cat_sports_gear": "Игровой инвентарь",
                        "cat_protective_gear": "Защитный инвентарь",
                        "cat_clothing_small": "Малые вещи",
                        "cat_accessory": "Аксессуары",
                        "cond_new": "Новое",
                        "cond_used": "Б/У",
                        "cond_broken": "Требует ремонта",
                        "sort_none": "Без сортировки",
                        "sort_name": "По названию",
                        "sort_amount": "По количеству",
                        "sort_manufacturer": "По производителю",
                        "err_title": "Ошибка выполнения",
                        "err_validation_title": "Ошибка валидации",
                        "err_validation_empty": "Все поля обязательны.",
                        "err_user_not_found": "Пользователь '{username}' не найден.",
                        "err_user_already_exists": "Логин '{username}' уже занят.",
                        "err_invalid_password": "Неверный пароль.",
                        "err_core_fault": "Сбой ядра авторизации",
                        "msg_welcome_title": "Успешный вход",
                        "msg_welcome_desc": "Добро пожаловать, {username}!",
                        "lbl_total_used": "Б/У: {count}",
                        "lbl_total_broken": "Сломано: {count}",
                        "btn_upload_icon": "Загрузить иконку",
                        "prop_stackable": "Стакается?",
                        "prop_max_stack": "Макс. стак",
                        "btn_save": "Сохранить",
                        "btn_cancel": "Отменить",
                        "lbl_icon_path": "Иконка",
                        "lbl_default": "стандартная",
                        "lbl_theme": "Тема",
                        "lbl_language": "Язык",
                        "btn_change_account": "Сменить аккаунт",
                        "lbl_loading_folders": "Инициализация директорий...",
                        "lbl_loading_configs": "Развертывание конфигураций...",
                        "lbl_loading_assets": "Проверка графических иконок...",
                        "lbl_loading_ready": "Инициализация завершена!",
                        "err_validation_chars": "Допустима только латиница, цифры и _ (3-20 символов).",
                        "lbl_enter_password": "Пароль для {username}:",
                    },
                    indent=4,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

        # Локализация en.json
        en_file = LangData / "en.json"
        if not en_file.exists():
            en_file.write_text(
                json.dumps(
                    {
                        "title_auth": "Authentication",
                        "title_register": "Registration",
                        "title_main": "Sports Equipment Database",
                        "lbl_loading": "Loading... ",
                        "lbl_username": "Username",
                        "lbl_password": "Password",
                        "lbl_total_items": "Items: {count}",
                        "lbl_version": "Version: {version}",
                        "lbl_filters_title": "Filters & Search",
                        "lbl_search_placeholder": "Search by name/manufacturer...",
                        "lbl_sort_placeholder": "Sort...",
                        "btn_login": "Login",
                        "btn_register": "Register",
                        "btn_goto_register": "Register new profile",
                        "btn_goto_login": "Already have an account? Login",
                        "btn_add": "Add Item",
                        "btn_add_manual": "Add New Item",
                        "btn_add_rand": "Add Random",
                        "btn_delete": "Delete",
                        "btn_edit": "Edit",
                        "prop_name": "Name",
                        "prop_manufacturer": "Manufacturer",
                        "prop_amount": "Amount",
                        "prop_condition": "Condition",
                        "prop_category": "Category",
                        "cat_cardio_machine": "Cardio",
                        "cat_strength_machine": "Strength",
                        "cat_free_weight": "Free Weights",
                        "cat_bench": "Benches & Racks",
                        "cat_flexibility_equipment": "Flexibility",
                        "cat_ball": "Balls",
                        "cat_sports_gear": "Sports Gear",
                        "cat_protective_gear": "Protective",
                        "cat_clothing_small": "Apparel",
                        "cat_accessory": "Accessories",
                        "cond_new": "New",
                        "cond_used": "Used",
                        "cond_broken": "Broken",
                        "sort_none": "No sorting",
                        "sort_name": "By name",
                        "sort_amount": "By amount",
                        "sort_manufacturer": "By manufacturer",
                        "err_title": "Error",
                        "err_validation_title": "Validation Error",
                        "err_validation_empty": "Fields are required.",
                        "err_user_not_found": "User '{username}' not found.",
                        "err_user_already_exists": "Username '{username}' taken.",
                        "err_invalid_password": "Wrong password.",
                        "err_core_fault": "Core failure",
                        "msg_welcome_title": "Success",
                        "msg_welcome_desc": "Welcome, {username}!",
                        "lbl_total_used": "Used: {count}",
                        "lbl_total_broken": "Broken: {count}",
                        "btn_upload_icon": "Upload Icon",
                        "prop_stackable": "Stackable?",
                        "prop_max_stack": "Max stack",
                        "btn_save": "Save",
                        "btn_cancel": "Cancel",
                        "lbl_icon_path": "Icon path",
                        "lbl_default": "default",
                        "lbl_theme": "Theme",
                        "lbl_language": "Language",
                        "btn_change_account": "Switch Account",
                        "lbl_loading_folders": "Initializing system storage...",
                        "lbl_loading_configs": "Deploying default blueprints...",
                        "lbl_loading_assets": "Checking core graphical elements...",
                        "lbl_loading_ready": "System ready!",
                        "err_validation_chars": "Only letters, digits, and underscores (3-20).",
                        "lbl_enter_password": "Password for {username}:",
                    },
                    indent=4,
                ),
                encoding="utf-8",
            )

        # Дефолтный пресет генератора DefaultItemGen.json
        gen_file = ItemGeneratorData / "DefaultItemGen.json"
        if not gen_file.exists():
            gen_file.write_text(
                json.dumps(
                    {
                        "manufacturers": [
                            "Adidas",
                            "Nike",
                            "Puma",
                            "Reebok",
                            "Decathlon",
                            "Kettler",
                        ],
                        "presets": {
                            "cardio_machine": [
                                "Treadmill T-500",
                                "Elliptical E-820",
                                "Rowing Machine R-10",
                            ],
                            "strength_machine": [
                                "Leg Press L-1",
                                "Chest Press C-2",
                                "Smith Machine S-5",
                            ],
                            "free_weight": [
                                "Dumbbell 10kg",
                                "Barbell Set 50kg",
                                "Kettlebell 16kg",
                            ],
                            "bench": [
                                "Flat Bench FB-10",
                                "Incline Bench IB-20",
                                "Utility Bench UB-30",
                            ],
                            "flexibility_equipment": [
                                "Yoga Mat",
                                "Pilates Ring",
                                "Stretching Band",
                            ],
                            "ball": [
                                "Basketball Size 7",
                                "Soccer Ball Size 5",
                                "Medicine Ball 5kg",
                            ],
                            "sports_gear": [
                                "Tennis Racket",
                                "Badminton Set",
                                "Table Tennis Paddle",
                            ],
                            "protective_gear": [
                                "Boxing Gloves 12oz",
                                "Shin Guards",
                                "Helmet Pro",
                            ],
                            "clothing_small": [
                                "Running Socks",
                                "Sweatband",
                                "Training Gloves",
                            ],
                            "accessory": ["Stopwatch S1", "Shaker Bottle", "Gym Towel"],
                        },
                    },
                    indent=4,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

    def download_assets(self):
        """Проверяет наличие и скачивает базовые иконки без блокировки основного GUI."""
        headers = {"User-Agent": "Mozilla/5.0"}

        # Обход проверки SSL для стабильности скачивания
        try:
            ssl_context = ssl._create_unverified_context()
        except AttributeError:
            ssl_context = None

        for icon_name, url in ICON_URLS.items():
            target_path = Icons / f"{icon_name}.png"
            if not target_path.exists():
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(
                        req, context=ssl_context, timeout=5
                    ) as r:
                        target_path.write_bytes(r.read())
                    log_info(f"Asset fetched via network: {icon_name}.png")
                except Exception as e:
                    log_error(f"Asset fetch aborted for {icon_name}: {e}")

        # Резервное создание default.png, если он отсутствует, а icon.png есть
        default_png = Icons / "default.png"
        icon_png = Icons / "icon.png"
        if not default_png.exists() and icon_png.exists():
            try:
                default_png.write_bytes(icon_png.read_bytes())
            except Exception as e:
                log_error(f"Failed to copy placeholder default.png: {e}")


class SplashScreen(QWidget):
    """Полноэкранное окно инициализации со спиннером и статус-баром."""

    def __init__(self):
        super().__init__(
            None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(480, 320)

        # Центрирование
        screen_geom = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen_geom.width() - self.width()) // 2,
            (screen_geom.height() - self.height()) // 2,
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(32, 32, 32, 32)
        main_layout.setSpacing(24)

        # Кастомная анимированная шестеренка
        self.gear = RotatingGearWidget(self, size=80)
        main_layout.addWidget(self.gear, alignment=Qt.AlignmentFlag.AlignCenter)

        # Кастомный прогресс-бар
        self.progress_container = QFrame(self)
        self.progress_container.setFixedHeight(6)
        self.progress_container.setStyleSheet(
            "background-color: #121212; border-radius: 3px;"
        )
        self.progress_container.setFixedWidth(360)

        self.progress_inner = QFrame(self.progress_container)
        self.progress_inner.setFixedHeight(6)
        self.progress_inner.setStyleSheet(
            "background-color: #007acc; border-radius: 3px;"
        )
        self.progress_inner.setFixedWidth(0)

        main_layout.addWidget(
            self.progress_container, alignment=Qt.AlignmentFlag.AlignCenter
        )

        self.lbl_status = QLabel(self)
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("font-size: 13px; color: #aaaaaa;")
        main_layout.addWidget(self.lbl_status)

        self.setStyleSheet(
            "background-color: #1e1e1e; border: 1px solid #3f3f46; border-radius: 12px;"
        )

    def set_progress(self, percentage: int, msg_key: str):
        """Обновляет значение шкалы прогресса и статус-строки с безопасной анимацией."""
        tm = TranslationManager()
        self.lbl_status.setText(tm.get(msg_key, msg_key))

        target_width = int((percentage / 100.0) * 360)

        self.anim = QVariantAnimation(self)
        self.anim.setDuration(250)
        self.anim.setStartValue(self.progress_inner.width())
        self.anim.setEndValue(target_width)
        self.anim.valueChanged.connect(lambda w: self.progress_inner.setFixedWidth(w))
        self.anim.start()


# =====================================================================
# СИСТЕМА ПЕРЕКЛЮЧЕНИЯ ЭКРАНОВ С ЭФФЕКТАМИ СЛАЙДА И ЗАТУХАНИЯ
# =====================================================================
class SlidingStackedWidget(QWidget):
    """Контейнер виджетов, реализующий эффект Slide + Fade перехода."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.widgets = []
        self.current_idx = -1
        self.anim_group = None

    def addWidget(self, widget):
        widget.setParent(self)
        widget.hide()
        self.widgets.append(widget)
        if self.current_idx == -1:
            self.current_idx = 0
            widget.show()

    def setCurrentIndex(self, index):
        if index == self.current_idx or index < 0 or index >= len(self.widgets):
            return

        old_idx = self.current_idx
        self.current_idx = index

        old_widget = self.widgets[old_idx]
        new_widget = self.widgets[index]

        if (
            self.anim_group
            and self.anim_group.state() == QAbstractAnimation.State.Running
        ):
            self.anim_group.stop()

        width = self.width()

        eff_old = QGraphicsOpacityEffect(old_widget)
        old_widget.setGraphicsEffect(eff_old)

        eff_new = QGraphicsOpacityEffect(new_widget)
        new_widget.setGraphicsEffect(eff_new)

        new_widget.resize(self.size())
        new_widget.show()

        if index > old_idx:
            start_pos_new = QPoint(width, 0)
            end_pos_old = QPoint(-width, 0)
        else:
            start_pos_new = QPoint(-width, 0)
            end_pos_old = QPoint(width, 0)

        new_widget.move(start_pos_new)

        anim_op_old = QPropertyAnimation(eff_old, b"opacity")
        anim_op_old.setDuration(350)
        anim_op_old.setStartValue(1.0)
        anim_op_old.setEndValue(0.0)

        anim_op_new = QPropertyAnimation(eff_new, b"opacity")
        anim_op_new.setDuration(350)
        anim_op_new.setStartValue(0.0)
        anim_op_new.setEndValue(1.0)

        anim_pos_old = QPropertyAnimation(old_widget, b"pos")
        anim_pos_old.setDuration(350)
        anim_pos_old.setStartValue(QPoint(0, 0))
        anim_pos_old.setEndValue(end_pos_old)
        anim_pos_old.setEasingCurve(QEasingCurve.Type.OutCubic)

        anim_pos_new = QPropertyAnimation(new_widget, b"pos")
        anim_pos_new.setDuration(350)
        anim_pos_new.setStartValue(start_pos_new)
        anim_pos_new.setEndValue(QPoint(0, 0))
        anim_pos_new.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.anim_group = QParallelAnimationGroup(self)
        self.anim_group.addAnimation(anim_op_old)
        self.anim_group.addAnimation(anim_op_new)
        self.anim_group.addAnimation(anim_pos_old)
        self.anim_group.addAnimation(anim_pos_new)

        def cleanup():
            old_widget.hide()
            old_widget.setGraphicsEffect(None)
            new_widget.setGraphicsEffect(None)
            new_widget.move(0, 0)

        self.anim_group.finished.connect(cleanup)
        self.anim_group.start()

    def resizeEvent(self, event):
        for w in self.widgets:
            w.resize(event.size())
        super().resizeEvent(event)


# =====================================================================
# ЭКРАНЫ АВТОРИЗАЦИИ И РЕГИСТРАЦИИ
# =====================================================================
class LoginForm(QWidget):
    goto_register = Signal()
    submit = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        tm = TranslationManager()

        title = QLabel(tm.get("title_auth"), self)
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 12px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        lbl_user = QLabel(tm.get("lbl_username"), self)
        lbl_user.setStyleSheet("font-weight: bold; font-size: 11px; margin-top: 4px;")
        layout.addWidget(lbl_user)

        self.edt_user = QLineEdit(self)
        layout.addWidget(self.edt_user)

        self.lbl_user_err = QLabel("", self)
        self.lbl_user_err.setStyleSheet("color: #ef4444; font-size: 11px;")
        layout.addWidget(self.lbl_user_err)

        lbl_pass = QLabel(tm.get("lbl_password"), self)
        lbl_pass.setStyleSheet("font-weight: bold; font-size: 11px; margin-top: 4px;")
        layout.addWidget(lbl_pass)

        self.edt_pass = QLineEdit(self)
        self.edt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.edt_pass)

        self.lbl_pass_err = QLabel("", self)
        self.lbl_pass_err.setStyleSheet("color: #ef4444; font-size: 11px;")
        layout.addWidget(self.lbl_pass_err)

        self.btn_submit = QPushButton(tm.get("btn_login"), self)
        layout.addWidget(self.btn_submit)

        self.btn_goto = QPushButton(tm.get("btn_goto_register"), self)
        self.btn_goto.setStyleSheet(
            "background: transparent; border: none; text-decoration: underline; color: #007acc;"
        )
        self.btn_goto.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.btn_goto)

        self.edt_user.textChanged.connect(self.clear_user_error)
        self.edt_pass.textChanged.connect(self.clear_pass_error)
        self.btn_submit.clicked.connect(self.on_submit)
        self.btn_goto.clicked.connect(self.goto_register.emit)

    def clear_user_error(self):
        self.lbl_user_err.clear()
        self.edt_user.setStyleSheet("")

    def clear_pass_error(self):
        self.lbl_pass_err.clear()
        self.edt_pass.setStyleSheet("")

    def on_submit(self):
        tm = TranslationManager()
        user = self.edt_user.text().strip()
        pwd = self.edt_pass.text()

        valid = True
        if not user:
            self.lbl_user_err.setText(tm.get("err_validation_empty"))
            self.edt_user.setStyleSheet("border: 1px solid #ef4444;")
            valid = False
        elif not re.match(r"^[a-zA-Z0-9_]{3,20}$", user):
            self.lbl_user_err.setText(tm.get("err_validation_chars"))
            self.edt_user.setStyleSheet("border: 1px solid #ef4444;")
            valid = False

        if not pwd:
            self.lbl_pass_err.setText(tm.get("err_validation_empty"))
            self.edt_pass.setStyleSheet("border: 1px solid #ef4444;")
            valid = False
        elif any(ord(c) >= 128 for c in pwd) or len(pwd) < 3 or len(pwd) > 30:
            self.lbl_pass_err.setText(tm.get("err_validation_chars"))
            self.edt_pass.setStyleSheet("border: 1px solid #ef4444;")
            valid = False

        if valid:
            self.submit.emit(user, pwd)


class RegisterForm(QWidget):
    goto_login = Signal()
    submit = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        tm = TranslationManager()

        title = QLabel(tm.get("title_register"), self)
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 12px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        lbl_user = QLabel(tm.get("lbl_username"), self)
        lbl_user.setStyleSheet("font-weight: bold; font-size: 11px; margin-top: 4px;")
        layout.addWidget(lbl_user)

        self.edt_user = QLineEdit(self)
        layout.addWidget(self.edt_user)

        self.lbl_user_err = QLabel("", self)
        self.lbl_user_err.setStyleSheet("color: #ef4444; font-size: 11px;")
        layout.addWidget(self.lbl_user_err)

        lbl_pass = QLabel(tm.get("lbl_password"), self)
        lbl_pass.setStyleSheet("font-weight: bold; font-size: 11px; margin-top: 4px;")
        layout.addWidget(lbl_pass)

        self.edt_pass = QLineEdit(self)
        self.edt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.edt_pass)

        self.lbl_pass_err = QLabel("", self)
        self.lbl_pass_err.setStyleSheet("color: #ef4444; font-size: 11px;")
        layout.addWidget(self.lbl_pass_err)

        self.btn_submit = QPushButton(tm.get("btn_register"), self)
        layout.addWidget(self.btn_submit)

        self.btn_goto = QPushButton(tm.get("btn_goto_login"), self)
        self.btn_goto.setStyleSheet(
            "background: transparent; border: none; text-decoration: underline; color: #007acc;"
        )
        self.btn_goto.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.btn_goto)

        self.edt_user.textChanged.connect(self.clear_user_error)
        self.edt_pass.textChanged.connect(self.clear_pass_error)
        self.btn_submit.clicked.connect(self.on_submit)
        self.btn_goto.clicked.connect(self.goto_login.emit)

    def clear_user_error(self):
        self.lbl_user_err.clear()
        self.edt_user.setStyleSheet("")

    def clear_pass_error(self):
        self.lbl_pass_err.clear()
        self.edt_pass.setStyleSheet("")

    def on_submit(self):
        tm = TranslationManager()
        user = self.edt_user.text().strip()
        pwd = self.edt_pass.text()

        valid = True
        if not user:
            self.lbl_user_err.setText(tm.get("err_validation_empty"))
            self.edt_user.setStyleSheet("border: 1px solid #ef4444;")
            valid = False
        elif not re.match(r"^[a-zA-Z0-9_]{3,20}$", user):
            self.lbl_user_err.setText(tm.get("err_validation_chars"))
            self.edt_user.setStyleSheet("border: 1px solid #ef4444;")
            valid = False

        if not pwd:
            self.lbl_pass_err.setText(tm.get("err_validation_empty"))
            self.edt_pass.setStyleSheet("border: 1px solid #ef4444;")
            valid = False
        elif any(ord(c) >= 128 for c in pwd) or len(pwd) < 3 or len(pwd) > 30:
            self.lbl_pass_err.setText(tm.get("err_validation_chars"))
            self.edt_pass.setStyleSheet("border: 1px solid #ef4444;")
            valid = False

        if valid:
            self.submit.emit(user, pwd)


class AuthWindow(QWidget):
    """Контейнер авторизации, центрирующий форму на экране с эффектом мягкой тени."""

    auth_successful = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QGridLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame(self)
        self.card.setObjectName("AuthCard")
        self.card.setFixedSize(380, 460)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 90))
        shadow.setOffset(0, 6)
        self.card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)

        self.stacked = SlidingStackedWidget(self.card)
        card_layout.addWidget(self.stacked)

        self.login_form = LoginForm(self.stacked)
        self.register_form = RegisterForm(self.stacked)

        self.stacked.addWidget(self.login_form)
        self.stacked.addWidget(self.register_form)

        self.login_form.goto_register.connect(lambda: self.stacked.setCurrentIndex(1))
        self.register_form.goto_login.connect(lambda: self.stacked.setCurrentIndex(0))

        self.login_form.submit.connect(self.handle_login)
        self.register_form.submit.connect(self.handle_register)

        main_layout.addWidget(self.card, 0, 0, Qt.AlignmentFlag.AlignCenter)

    def handle_login(self, username, password):
        tm = TranslationManager()
        try:
            user = authenticate_user(username, password)
            session_manager.start_session(user)
            self.auth_successful.emit()
        except UserNotFoundError:
            self.login_form.lbl_user_err.setText(
                tm.get("err_user_not_found", username=username)
            )
            self.login_form.edt_user.setStyleSheet("border: 1px solid #ef4444;")
        except InvalidPasswordError:
            self.login_form.lbl_pass_err.setText(tm.get("err_invalid_password"))
            self.login_form.edt_pass.setStyleSheet("border: 1px solid #ef4444;")
        except Exception as e:
            log_error(f"Login failure: {e}")
            self.login_form.lbl_user_err.setText(tm.get("err_core_fault"))

    def handle_register(self, username, password):
        tm = TranslationManager()
        try:
            user = register_user(username, password)
            session_manager.start_session(user)
            self.auth_successful.emit()
        except UserAlreadyExistsError:
            self.register_form.lbl_user_err.setText(
                tm.get("err_user_already_exists", username=username)
            )
            self.register_form.edt_user.setStyleSheet("border: 1px solid #ef4444;")
        except Exception as e:
            log_error(f"Registration failure: {e}")
            self.register_form.lbl_user_err.setText(tm.get("err_core_fault"))


# =====================================================================
# ДИАЛОГ БЫСТРОЙ СМЕНЫ АККАУНТОВ (SWITCH ACCOUNT - TELEGRAM STYLE)
# =====================================================================
class QuickSwitchAccountDialog(QDialog):
    """Окно для быстрой смены профиля без полной перезагрузки интерфейса."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        tm = TranslationManager()
        th = ThemeManager()

        self.container = QFrame(self)
        self.container.setObjectName("SwitchAccountContainer")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.container)

        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(12)
        self.container_layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel(tm.get("btn_change_account"), self)
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.container_layout.addWidget(title)

        self.list_widget = QListWidget(self)
        self.container_layout.addWidget(self.list_widget)

        usernames = session_manager.get_available_usernames()
        try:
            current_user = session_manager.current_user.username
        except Exception:
            current_user = ""

        for u in usernames:
            if u != current_user:
                self.list_widget.addItem(u)

        # Режим 1: Ввод пароля для существующего аккаунта
        self.pass_widget = QWidget(self)
        pass_lay = QVBoxLayout(self.pass_widget)
        pass_lay.setContentsMargins(0, 0, 0, 0)
        pass_lay.setSpacing(6)

        self.lbl_prompt = QLabel("", self)
        pass_lay.addWidget(self.lbl_prompt)

        self.edt_pass = QLineEdit(self)
        self.edt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        pass_lay.addWidget(self.edt_pass)

        self.lbl_err = QLabel("", self)
        self.lbl_err.setStyleSheet("color: #ef4444; font-size: 11px;")
        pass_lay.addWidget(self.lbl_err)

        self.btn_confirm = QPushButton(tm.get("btn_login"), self)
        pass_lay.addWidget(self.btn_confirm)

        self.container_layout.addWidget(self.pass_widget)
        self.pass_widget.hide()

        # Режим 2: Регистрация нового аккаунта (Добавлено по запросу)
        self.reg_widget = QWidget(self)
        reg_lay = QVBoxLayout(self.reg_widget)
        reg_lay.setContentsMargins(0, 0, 0, 0)
        reg_lay.setSpacing(6)

        self.lbl_reg_user = QLabel(tm.get("lbl_username"), self)
        reg_lay.addWidget(self.lbl_reg_user)
        self.edt_reg_user = QLineEdit(self)
        reg_lay.addWidget(self.edt_reg_user)

        self.lbl_reg_pass = QLabel(tm.get("lbl_password"), self)
        reg_lay.addWidget(self.lbl_reg_pass)
        self.edt_reg_pass = QLineEdit(self)
        self.edt_reg_pass.setEchoMode(QLineEdit.EchoMode.Password)
        reg_lay.addWidget(self.edt_reg_pass)

        self.lbl_reg_err = QLabel("", self)
        self.lbl_reg_err.setStyleSheet("color: #ef4444; font-size: 11px;")
        reg_lay.addWidget(self.lbl_reg_err)

        self.btn_confirm_reg = QPushButton(tm.get("btn_register"), self)
        reg_lay.addWidget(self.btn_confirm_reg)

        self.btn_reg_back = QPushButton(tm.get("btn_cancel"), self)
        self.btn_reg_back.setStyleSheet(
            "background-color: transparent; border: 1px solid #3f3f46;"
        )
        reg_lay.addWidget(self.btn_reg_back)

        self.container_layout.addWidget(self.reg_widget)
        self.reg_widget.hide()

        # Кнопка перехода к регистрации нового пользователя
        self.btn_switch_reg = QPushButton(tm.get("btn_goto_register"), self)
        self.btn_switch_reg.setStyleSheet(
            "background-color: transparent; border: none; text-decoration: underline; color: #007acc; font-size: 11px;"
        )
        self.container_layout.addWidget(self.btn_switch_reg)

        self.btn_close = QPushButton(tm.get("btn_cancel"), self)
        self.btn_close.setStyleSheet(
            "background-color: transparent; border: 1px solid #3f3f46;"
        )
        self.container_layout.addWidget(self.btn_close)

        self.btn_close.clicked.connect(self.reject)
        self.list_widget.itemClicked.connect(self.on_account_clicked)
        self.btn_confirm.clicked.connect(self.on_confirm_login)
        self.btn_switch_reg.clicked.connect(self.show_reg_mode)
        self.btn_confirm_reg.clicked.connect(self.on_confirm_register)
        self.btn_reg_back.clicked.connect(self.show_list_mode)

        self.selected_user = None

        self.container.setStyleSheet(
            f"""
            QFrame#SwitchAccountContainer {{
                background-color: {th.get('bg_card', '#2d2d2d')};
                border: 2px solid {th.get('border_color', '#3f3f46')};
                border-radius: 12px;
            }}
            QListWidget {{
                background-color: {th.get('bg_dark', '#121212')};
                border: 1px solid {th.get('border_color', '#3f3f46')};
                border-radius: 6px;
                color: {th.get('text_primary', '#ffffff')};
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-radius: 4px;
            }}
            QListWidget::item:hover {{
                background-color: {th.get('accent_primary', '#007acc')};
                color: white;
            }}
            QLabel {{
                color: {th.get('text_primary', '#ffffff')};
            }}
        """
        )

    def on_account_clicked(self, item):
        self.selected_user = item.text()
        tm = TranslationManager()
        self.lbl_prompt.setText(
            tm.get("lbl_enter_password", username=self.selected_user)
        )
        self.edt_pass.clear()
        self.lbl_err.clear()
        self.pass_widget.show()
        self.list_widget.hide()
        self.btn_switch_reg.hide()

    def on_confirm_login(self):
        tm = TranslationManager()
        pwd = self.edt_pass.text()
        if not pwd:
            self.lbl_err.setText(tm.get("err_validation_empty"))
            return

        try:
            user = authenticate_user(self.selected_user, pwd)
            session_manager.close_session()
            session_manager.start_session(user)
            self.accept()
        except Exception:
            self.lbl_err.setText(tm.get("err_invalid_password"))

    def show_reg_mode(self):
        self.reg_widget.show()
        self.list_widget.hide()
        self.pass_widget.hide()
        self.btn_switch_reg.hide()
        self.edt_reg_user.clear()
        self.edt_reg_pass.clear()
        self.lbl_reg_err.clear()

    def show_list_mode(self):
        self.reg_widget.hide()
        self.list_widget.show()
        self.btn_switch_reg.show()

    def on_confirm_register(self):
        tm = TranslationManager()
        user = self.edt_reg_user.text().strip()
        pwd = self.edt_reg_pass.text()

        valid = True
        if not user:
            self.lbl_reg_err.setText(tm.get("err_validation_empty"))
            valid = False
        elif not re.match(r"^[a-zA-Z0-9_]{3,20}$", user):
            self.lbl_reg_err.setText(tm.get("err_validation_chars"))
            valid = False

        if not pwd:
            self.lbl_reg_err.setText(tm.get("err_validation_empty"))
            valid = False
        elif any(ord(c) >= 128 for c in pwd) or len(pwd) < 3 or len(pwd) > 30:
            self.lbl_reg_err.setText(tm.get("err_validation_chars"))
            valid = False

        if valid:
            try:
                new_user = register_user(user, pwd)
                session_manager.close_session()
                session_manager.start_session(new_user)
                self.accept()
            except UserAlreadyExistsError:
                self.lbl_reg_err.setText(
                    tm.get("err_user_already_exists", username=user)
                )
            except Exception as e:
                log_error(f"Quick dialog registration failed: {e}")
                self.lbl_reg_err.setText(tm.get("err_core_fault"))


# =====================================================================
# ВСПЛЫВАЮЩАЯ HOVER-КАРТОЧКА ПРЕДМЕТА (FLUID INFO CARD)
# =====================================================================
class HoverCard(QWidget):
    """Свободно позиционируемая карточка со сведениями о предмете при наведении."""

    def __init__(self, parent=None):
        super().__init__(
            parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.container = QFrame(self)
        self.container.setObjectName("HoverCardContainer")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.container)

        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(12, 12, 12, 12)
        self.container_layout.setSpacing(8)

        # Шапка карточки
        self.category_label = QLabel(self)
        self.category_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.category_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; padding: 4px; border-bottom: 1px solid #3f3f46;"
        )
        self.container_layout.addWidget(self.category_label)

        # Средний блок
        middle_widget = QWidget(self)
        middle_layout = QHBoxLayout(middle_widget)
        middle_layout.setContentsMargins(0, 4, 0, 4)

        self.info_label = QLabel(self)
        self.info_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.info_label.setWordWrap(True)
        middle_layout.addWidget(self.info_label, stretch=3)

        self.icon_label = QLabel(self)
        self.icon_label.setFixedSize(56, 56)
        self.icon_label.setScaledContents(True)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        middle_layout.addWidget(self.icon_label, stretch=1)

        self.container_layout.addWidget(middle_widget)

        # Нижний блок
        bottom_widget = QWidget(self)
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(4)

        self.stack_label = QLabel(self)
        bottom_layout.addWidget(self.stack_label)

        self.amount_label = QLabel(self)
        bottom_layout.addWidget(self.amount_label)

        self.container_layout.addWidget(bottom_widget)

        # Идентификатор предмета (ID)
        self.id_label = QLabel(self)
        self.id_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.id_label.setStyleSheet("font-size: 10px; color: #888888; margin-top: 4px;")
        self.container_layout.addWidget(self.id_label)

        self.setFixedWidth(290)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(150)

    def show_item(self, item: Item, pos: QPoint):
        self.anim.stop()

        tm = TranslationManager()
        th = ThemeManager()

        cat_key = f"cat_{item.category.value}"
        self.category_label.setText(tm.get(cat_key, item.category.name).upper())

        cond_key = f"cond_{item.condition.value}"
        cond_text = tm.get(cond_key, item.condition.name)

        cond_color = "#10b981"
        if item.condition == ItemCondition.BROKEN:
            cond_color = "#ef4444"
        elif item.condition == ItemCondition.USED:
            cond_color = "#f59e0b"

        info_html = f"""
        <p style="margin: 0px 0px 4px 0px;"><b>• {tm.get('prop_name')}:</b> {item.name}</p>
        <p style="margin: 4px 0px 4px 0px;"><b>• {tm.get('prop_manufacturer')}:</b> {item.manufacturer}</p>
        <p style="margin: 4px 0px 0px 0px;"><b>• {tm.get('prop_condition')}:</b> <span style="color: {cond_color};"><b>{cond_text}</b></span></p>
        """
        self.info_label.setText(info_html)

        if item.icon_path and Path(item.icon_path).exists():
            pix = QPixmap(str(item.icon_path))
        else:
            pix = QPixmap(str(Icons / "default.png"))
        self.icon_label.setPixmap(pix)

        stackable_text = "✔" if item.stackable else "❌"
        self.stack_label.setText(f"<b>{tm.get('prop_stackable')}:</b> {stackable_text}")

        max_str = str(item.max_stack) if item.max_stack is not None else "—"
        self.amount_label.setText(
            f"<b>{tm.get('prop_amount')}:</b> {item.amount} / {max_str}"
        )

        self.id_label.setText(f"#{item.id}")

        self.container.setStyleSheet(
            f"""
            QFrame#HoverCardContainer {{
                background-color: {th.get('bg_card', '#2d2d2d')};
                border: 2px solid {th.get('border_color', '#3f3f46')};
                border-radius: 12px;
            }}
            QLabel {{
                color: {th.get('text_primary', '#ffffff')};
            }}
        """
        )

        self.move(pos + QPoint(16, 16))
        self.show()

        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def hide_card(self):
        self.anim.stop()
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(0.0)

        def on_fade_out():
            if self.opacity_effect.opacity() == 0.0:
                self.hide()

        try:
            self.anim.finished.disconnect()
        except RuntimeError:
            pass
        self.anim.finished.connect(on_fade_out)
        self.anim.start()


# =====================================================================
# КОМПОНЕНТЫ ГРИДА ПРЕДМЕТОВ (МАТРИЦА С ВЫБОРОМ МАСШТАБА)
# =====================================================================
class ItemWidget(QFrame):
    """Индивидуальная плитка предмета инвентаря."""

    clicked = Signal(str)
    double_clicked = Signal(str)

    def __init__(self, item: Item, parent=None):
        super().__init__(parent)
        self.item = item
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("ItemCell")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self.show_hover_card)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self.icon_label = QLabel(self)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setScaledContents(True)

        if item.icon_path and Path(item.icon_path).exists():
            pix = QPixmap(str(item.icon_path))
        else:
            pix = QPixmap(str(Icons / "default.png"))

        self.icon_label.setPixmap(pix)
        layout.addWidget(self.icon_label)

        if item.amount > 1:
            self.amount_label = QLabel(f"x{item.amount}", self)
            # ИСПРАВЛЕНИЕ: Увеличен размер и контрастность индикатора количества на сетке
            self.amount_label.setStyleSheet(
                "color: white; "
                "font-weight: bold; "
                "font-size: 12px; "
                "background-color: rgba(18, 18, 18, 230); "
                "border: 1px solid #52525b; "
                "border-radius: 4px; "
                "padding: 2px 5px;"
            )
            self.amount_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "amount_label"):
            self.amount_label.adjustSize()
            self.amount_label.move(
                self.width() - self.amount_label.width() - 4,
                self.height() - self.amount_label.height() - 4,
            )

    def enterEvent(self, event):
        self.hover_timer.start(250)

    def leaveEvent(self, event):
        self.hover_timer.stop()
        main_win = self.window()
        hide_func = getattr(main_win, "hide_hover_card", None)
        if callable(hide_func):
            hide_func()

    def show_hover_card(self):
        main_win = self.window()
        show_func = getattr(main_win, "show_hover_card", None)
        if callable(show_func):
            show_func(self.item, QCursor.pos())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item.id)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.item.id)

    def update_style(self, theme):
        cond = self.item.condition
        color = theme.get("border_color", "#3f3f46")

        if cond == ItemCondition.BROKEN:
            color = "#ef4444"
        elif cond == ItemCondition.USED:
            color = "#f59e0b"
        elif cond == ItemCondition.NEW:
            color = "#10b981"

        self.setStyleSheet(
            f"""
            QFrame#ItemCell {{
                border: 2px solid {color};
                border-radius: 8px;
                background-color: {theme.get('bg_card', '#2d2d2d')};
            }}
            QFrame#ItemCell:hover {{
                background-color: {theme.get('bg_dark', '#121212')};
                border: 2px solid {theme.get('accent_primary', '#007acc')};
            }}
        """
        )


class EmptyCellWidget(QFrame):
    """Плитка-заглушка для отрисовки пустых ячеек инвентаня."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("EmptyCell")
        self.setMinimumSize(64, 64)


# =====================================================================
# ИНВЕНТАРНАЯ СЕТКА И БОКОВАЯ ПАНЕЛЬ МЕНЮ
# =====================================================================
class InventoryGridView(QWidget):
    """Табличный грид предметов с пагинацией и настройками масштаба сетки."""

    edit_requested = Signal(str)
    create_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.toolbar = QHBoxLayout()

        self.btn_hamburger = QPushButton("☰", self)
        self.btn_hamburger.setFixedSize(36, 36)
        self.btn_hamburger.setStyleSheet("font-size: 16px;")
        self.toolbar.addWidget(self.btn_hamburger)

        # ИСПРАВЛЕНИЕ: Кнопки добавления разделены на ручное заполнение и случайное (генератор)
        tm = TranslationManager()

        self.btn_add_manual = QPushButton(tm.get("btn_add_manual"), self)
        self.btn_add_manual.setStyleSheet("padding: 6px 12px;")
        self.toolbar.addWidget(self.btn_add_manual)

        self.btn_add_rand = QPushButton(tm.get("btn_add_rand"), self)
        self.btn_add_rand.setStyleSheet(
            "padding: 6px 12px; background-color: transparent; border: 1px solid #3f3f46;"
        )
        self.toolbar.addWidget(self.btn_add_rand)

        self.toolbar.addStretch()

        self.cmb_scale = QComboBox(self)
        self.cmb_scale.addItem("4 x 4", 4)
        self.cmb_scale.addItem("5 x 5", 5)
        self.cmb_scale.addItem("6 x 6", 6)
        self.cmb_scale.setCurrentIndex(1)  # Дефолт 5х5
        self.toolbar.addWidget(self.cmb_scale)

        layout.addLayout(self.toolbar)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("GridScrollArea")

        self.grid_container = QWidget(self)
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(10)
        self.scroll_area.setWidget(self.grid_container)

        layout.addWidget(self.scroll_area)

        # Подвал пагинации (Footer)
        self.footer = QHBoxLayout()

        self.btn_first = QPushButton("<<", self)
        self.btn_prev = QPushButton("<", self)
        self.lbl_page = QLabel("1 / 1", self)
        self.lbl_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_page.setFixedWidth(80)
        self.btn_next = QPushButton(">", self)
        self.btn_last = QPushButton(">>", self)

        self.btn_first.setFixedSize(36, 30)
        self.btn_prev.setFixedSize(36, 30)
        self.btn_next.setFixedSize(36, 30)
        self.btn_last.setFixedSize(36, 30)

        self.footer.addStretch()
        self.footer.addWidget(self.btn_first)
        self.footer.addWidget(self.btn_prev)
        self.footer.addWidget(self.lbl_page)
        self.footer.addWidget(self.btn_next)
        self.footer.addWidget(self.btn_last)
        self.footer.addStretch()

        self.lbl_version = QLabel("v1.0.0", self)
        self.lbl_version.setStyleSheet("color: gray; font-size: 11px;")
        self.footer.addWidget(
            self.lbl_version,
            alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
        )

        layout.addLayout(self.footer)

        self.current_page = 1
        self.grid_size = 5
        self.items = []
        self.total_pages = 1

        self.cmb_scale.currentIndexChanged.connect(self.on_scale_changed)
        self.btn_first.clicked.connect(self.go_first)
        self.btn_prev.clicked.connect(self.go_prev)
        self.btn_next.clicked.connect(self.go_next)
        self.btn_last.clicked.connect(self.go_last)

        self.btn_add_manual.clicked.connect(self.create_requested.emit)
        self.btn_add_rand.clicked.connect(self.add_random_item)

    def retranslate(self):
        tm = TranslationManager()
        self.btn_add_manual.setText(tm.get("btn_add_manual"))
        self.btn_add_rand.setText(tm.get("btn_add_rand"))
        self.lbl_version.setText(tm.get("lbl_version", version="1.0.0"))

    def on_scale_changed(self, index):
        self.grid_size = self.cmb_scale.currentData()
        self.current_page = 1
        self.refresh_grid()

    def go_first(self):
        self.current_page = 1
        self.refresh_grid()

    def go_prev(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_grid()

    def go_next(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.refresh_grid()

    def go_last(self):
        self.current_page = self.total_pages
        self.refresh_grid()

    def add_random_item(self):
        try:
            item = generate_random_item()
            session_manager.current_user.inventory.add_item(item)
        except Exception as e:
            log_error(f"Error generating random item: {e}")

    def set_items_source(self, items):
        self.items = items
        self.refresh_grid()

    def refresh_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        p_size = self.grid_size * self.grid_size
        total_items = len(self.items)
        self.total_pages = max(1, (total_items + p_size - 1) // p_size)

        if self.current_page > self.total_pages:
            self.current_page = self.total_pages
        if self.current_page < 1:
            self.current_page = 1

        start_idx = (self.current_page - 1) * p_size
        end_idx = start_idx + p_size
        page_items = self.items[start_idx:end_idx]

        self.grid_layout.setRowStretch(self.grid_size, 0)
        self.grid_layout.setColumnStretch(self.grid_size, 0)

        for r in range(self.grid_size):
            self.grid_layout.setRowStretch(r, 1)
            self.grid_layout.setColumnStretch(r, 1)

        th = ThemeManager()
        for idx in range(p_size):
            row = idx // self.grid_size
            col = idx % self.grid_size

            if idx < len(page_items):
                item = page_items[idx]
                cell = ItemWidget(item, self)
                cell.update_style(th.theme_data)
                cell.double_clicked.connect(self.edit_requested.emit)
                self.grid_layout.addWidget(cell, row, col)
            else:
                cell = EmptyCellWidget(self)
                self.grid_layout.addWidget(cell, row, col)

        self.lbl_page.setText(f"{self.current_page} / {self.total_pages}")

        self.btn_first.setEnabled(self.current_page > 1)
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < self.total_pages)
        self.btn_last.setEnabled(self.current_page < self.total_pages)


class LeftMenuWidget(QWidget):
    """Выдвижное левое боковое меню с фильтрами, поиском и настройками системы."""

    filters_changed = Signal()
    change_account_clicked = Signal()
    theme_changed = Signal(str)
    lang_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LeftMenu")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        tm = TranslationManager()

        # Зона 1: Пользователь и Статистика
        self.user_group = QFrame(self)
        self.user_group.setObjectName("MenuGroup")
        user_lay = QVBoxLayout(self.user_group)
        user_lay.setContentsMargins(8, 8, 8, 8)
        user_lay.setSpacing(6)

        self.lbl_user = QLabel(self)
        self.lbl_user.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #007acc;"
        )
        user_lay.addWidget(self.lbl_user)

        self.lbl_stats = QLabel(self)
        self.lbl_stats.setStyleSheet("font-size: 11px; line-height: 1.4;")
        user_lay.addWidget(self.lbl_stats)

        self.btn_switch = QPushButton(tm.get("btn_change_account"), self)
        self.btn_switch.setStyleSheet("font-size: 11px; padding: 4px;")
        user_lay.addWidget(self.btn_switch)

        layout.addWidget(self.user_group)

        # Зона 2: Поиск и Фильтрация
        self.filter_group = QFrame(self)
        self.filter_group.setObjectName("MenuGroup")
        filter_lay = QVBoxLayout(self.filter_group)
        filter_lay.setContentsMargins(8, 8, 8, 8)
        filter_lay.setSpacing(8)

        # ИСПРАВЛЕНИЕ: Метки сохранены как атрибуты класса для полной динамической локализации
        self.lbl_filters_title = QLabel(tm.get("lbl_filters_title"), self)
        self.lbl_filters_title.setStyleSheet("font-weight: bold;")
        filter_lay.addWidget(self.lbl_filters_title)

        self.edt_search = QLineEdit(self)
        self.edt_search.setPlaceholderText(tm.get("lbl_search_placeholder"))
        filter_lay.addWidget(self.edt_search)

        self.lbl_cat = QLabel(tm.get("prop_category"), self)
        self.lbl_cat.setStyleSheet("font-size: 11px; color: gray;")
        filter_lay.addWidget(self.lbl_cat)

        self.cmb_category = QComboBox(self)
        filter_lay.addWidget(self.cmb_category)

        self.lbl_cond = QLabel(tm.get("prop_condition"), self)
        self.lbl_cond.setStyleSheet("font-size: 11px; color: gray;")
        filter_lay.addWidget(self.lbl_cond)

        self.chk_new = QCheckBox(tm.get("cond_new"), self)
        self.chk_used = QCheckBox(tm.get("cond_used"), self)
        self.chk_broken = QCheckBox(tm.get("cond_broken"), self)

        self.chk_new.setChecked(True)
        self.chk_used.setChecked(True)
        self.chk_broken.setChecked(True)

        filter_lay.addWidget(self.chk_new)
        filter_lay.addWidget(self.chk_used)
        filter_lay.addWidget(self.chk_broken)

        self.lbl_sort = QLabel(tm.get("lbl_sort_placeholder"), self)
        self.lbl_sort.setStyleSheet("font-size: 11px; color: gray;")
        filter_lay.addWidget(self.lbl_sort)

        self.cmb_sort = QComboBox(self)
        filter_lay.addWidget(self.cmb_sort)

        layout.addWidget(self.filter_group)
        layout.addStretch()

        # Зона 3: Системные Настройки
        self.sys_group = QFrame(self)
        self.sys_group.setObjectName("MenuGroup")
        sys_lay = QVBoxLayout(self.sys_group)
        sys_lay.setContentsMargins(8, 8, 8, 8)
        sys_lay.setSpacing(6)

        self.lbl_theme = QLabel(tm.get("lbl_theme"), self)
        self.lbl_theme.setStyleSheet("font-size: 11px; color: gray;")
        sys_lay.addWidget(self.lbl_theme)

        self.cmb_theme = QComboBox(self)
        sys_lay.addWidget(self.cmb_theme)

        self.lbl_lang = QLabel(tm.get("lbl_language"), self)
        self.lbl_lang.setStyleSheet("font-size: 11px; color: gray;")
        sys_lay.addWidget(self.lbl_lang)

        self.cmb_lang = QComboBox(self)
        sys_lay.addWidget(self.cmb_lang)

        layout.addWidget(self.sys_group)

        self.edt_search.textChanged.connect(lambda: self.filters_changed.emit())
        self.cmb_category.currentIndexChanged.connect(
            lambda: self.filters_changed.emit()
        )
        self.cmb_sort.currentIndexChanged.connect(lambda: self.filters_changed.emit())
        self.chk_new.stateChanged.connect(lambda: self.filters_changed.emit())
        self.chk_used.stateChanged.connect(lambda: self.filters_changed.emit())
        self.chk_broken.stateChanged.connect(lambda: self.filters_changed.emit())

        self.btn_switch.clicked.connect(self.change_account_clicked.emit)
        self.cmb_theme.currentIndexChanged.connect(self.on_theme_selected)
        self.cmb_lang.currentIndexChanged.connect(self.on_lang_selected)

        self.retranslate()

    def retranslate(self):
        """Интернационализация текстовых элементов интерфейса бокового меню."""
        tm = TranslationManager()

        # Динамический перевод меток описаний
        self.lbl_filters_title.setText(tm.get("lbl_filters_title"))
        self.lbl_cat.setText(tm.get("prop_category"))
        self.lbl_cond.setText(tm.get("prop_condition"))
        self.lbl_sort.setText(tm.get("lbl_sort_placeholder"))
        self.lbl_theme.setText(tm.get("lbl_theme"))
        self.lbl_lang.setText(tm.get("lbl_language"))

        self.cmb_category.blockSignals(True)
        self.cmb_category.clear()
        self.cmb_category.addItem("— " + tm.get("sort_none") + " —", None)
        for cat in ItemType:
            self.cmb_category.addItem(tm.get(f"cat_{cat.value}"), cat)
        self.cmb_category.blockSignals(False)

        self.cmb_sort.blockSignals(True)
        self.cmb_sort.clear()
        self.cmb_sort.addItem(tm.get("sort_none"), "none")
        self.cmb_sort.addItem(tm.get("sort_name"), "name")
        self.cmb_sort.addItem(tm.get("sort_amount"), "amount")
        # ИСПРАВЛЕНИЕ: Интегрирована сортировка по производителю
        self.cmb_sort.addItem(tm.get("sort_manufacturer"), "manufacturer")
        self.cmb_sort.blockSignals(False)

        self.cmb_theme.blockSignals(True)
        self.cmb_theme.clear()
        self.cmb_theme.addItem("Dark", "dark")
        self.cmb_theme.addItem("Light", "light")
        self.cmb_theme.addItem("Custom...", "custom")

        current_theme = ThemeManager().current_theme
        if current_theme == "dark":
            self.cmb_theme.setCurrentIndex(0)
        elif current_theme == "light":
            self.cmb_theme.setCurrentIndex(1)
        else:
            self.cmb_theme.setCurrentIndex(2)
        self.cmb_theme.blockSignals(False)

        self.cmb_lang.blockSignals(True)
        self.cmb_lang.clear()
        self.cmb_lang.addItem("Русский", "ru")
        self.cmb_lang.addItem("English", "en")

        current_lang = TranslationManager().current_lang
        if current_lang == "ru":
            self.cmb_lang.setCurrentIndex(0)
        else:
            self.cmb_lang.setCurrentIndex(1)
        self.cmb_lang.blockSignals(False)

        self.btn_switch.setText(tm.get("btn_change_account"))
        self.edt_search.setPlaceholderText(tm.get("lbl_search_placeholder"))
        self.chk_new.setText(tm.get("cond_new"))
        self.chk_used.setText(tm.get("cond_used"))
        self.chk_broken.setText(tm.get("cond_broken"))

        self.update_user_info()

    def update_user_info(self):
        tm = TranslationManager()
        try:
            user = session_manager.current_user
            self.lbl_user.setText(user.username)

            total = len(user.inventory.items)
            used = sum(
                1 for it in user.inventory.items if it.condition == ItemCondition.USED
            )
            broken = sum(
                1 for it in user.inventory.items if it.condition == ItemCondition.BROKEN
            )

            self.lbl_stats.setText(
                f"• {tm.get('lbl_total_items', count=total)}\n"
                f"• {tm.get('lbl_total_used', count=used)}\n"
                f"• {tm.get('lbl_total_broken', count=broken)}"
            )
        except Exception:
            self.lbl_user.setText("")
            self.lbl_stats.setText("")

    def on_theme_selected(self, index):
        data = self.cmb_theme.itemData(index)
        if data == "custom":
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Theme JSON", str(ThemeData), "JSON Files (*.json)"
            )
            if file_path:
                theme_name = Path(file_path).stem
                ThemeManager().load_theme(theme_name)
                self.theme_changed.emit(theme_name)
            else:
                self.retranslate()
        else:
            ThemeManager().load_theme(data)
            self.theme_changed.emit(data)

    def on_lang_selected(self, index):
        data = self.cmb_lang.itemData(index)
        TranslationManager().load_lang(data)
        self.lang_changed.emit(data)


# =====================================================================
# СТРАНИЦА РЕДАКТИРОВАНИЯ ПРЕДМЕТА (ВКЛАДКА MAIN STACKED)
# =====================================================================
class EditItemPage(QWidget):
    """Страница конфигурирования и редактирования элемента инвентаря."""

    save_clicked = Signal(str, dict)
    cancel_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("EditItemPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        h_layout = QHBoxLayout()

        # Левая панель с иконкой
        self.left_panel = QFrame(self)
        self.left_panel.setObjectName("EditPanel")
        left_lay = QVBoxLayout(self.left_panel)
        left_lay.setContentsMargins(16, 16, 16, 16)
        left_lay.setSpacing(12)

        self.lbl_large_icon = QLabel(self)
        self.lbl_large_icon.setFixedSize(128, 128)
        self.lbl_large_icon.setScaledContents(True)
        self.lbl_large_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_lay.addWidget(self.lbl_large_icon, alignment=Qt.AlignmentFlag.AlignCenter)

        self.lbl_path = QLabel(self)
        self.lbl_path.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_path.setWordWrap(True)
        self.lbl_path.setStyleSheet("font-size: 11px; color: gray;")
        left_lay.addWidget(self.lbl_path)

        tm = TranslationManager()
        self.btn_upload = QPushButton(tm.get("btn_upload_icon"), self)
        left_lay.addWidget(self.btn_upload, alignment=Qt.AlignmentFlag.AlignCenter)

        left_lay.addStretch()
        h_layout.addWidget(self.left_panel, stretch=2)

        # Правая панель с формой
        self.right_panel = QFrame(self)
        self.right_panel.setObjectName("EditPanel")
        right_lay = QVBoxLayout(self.right_panel)
        right_lay.setContentsMargins(16, 16, 16, 16)
        right_lay.setSpacing(8)

        # Категория
        self.lbl_cat = QLabel(tm.get("prop_category"), self)
        self.lbl_cat.setStyleSheet("font-weight: bold;")
        right_lay.addWidget(self.lbl_cat)

        self.cmb_category = QComboBox(self)
        right_lay.addWidget(self.cmb_category)

        # Наименование
        self.lbl_name = QLabel(tm.get("prop_name"), self)
        self.lbl_name.setStyleSheet("font-weight: bold;")
        right_lay.addWidget(self.lbl_name)

        self.edt_name = QLineEdit(self)
        right_lay.addWidget(self.edt_name)

        self.lbl_name_err = QLabel("", self)
        self.lbl_name_err.setStyleSheet("color: #ef4444; font-size: 11px;")
        right_lay.addWidget(self.lbl_name_err)

        # Производитель
        self.lbl_mfr = QLabel(tm.get("prop_manufacturer"), self)
        self.lbl_mfr.setStyleSheet("font-weight: bold;")
        right_lay.addWidget(self.lbl_mfr)

        self.edt_mfr = QLineEdit(self)
        right_lay.addWidget(self.edt_mfr)

        self.lbl_mfr_err = QLabel("", self)
        self.lbl_mfr_err.setStyleSheet("color: #ef4444; font-size: 11px;")
        right_lay.addWidget(self.lbl_mfr_err)

        # Состояние
        self.lbl_cond = QLabel(tm.get("prop_condition"), self)
        self.lbl_cond.setStyleSheet("font-weight: bold;")
        right_lay.addWidget(self.lbl_cond)

        self.cmb_condition = QComboBox(self)
        right_lay.addWidget(self.cmb_condition)

        # Флаг стакаемости
        self.chk_stackable = QCheckBox(tm.get("prop_stackable"), self)
        right_lay.addWidget(self.chk_stackable)

        # Скрываемые числовые поля (для стаков)
        self.amount_widget = QWidget(self)
        amount_lay = QVBoxLayout(self.amount_widget)
        amount_lay.setContentsMargins(0, 0, 0, 0)
        amount_lay.setSpacing(6)

        self.lbl_amount = QLabel(tm.get("prop_amount"), self)
        self.lbl_amount.setStyleSheet("font-weight: bold;")
        amount_lay.addWidget(self.lbl_amount)

        self.edt_amount = QLineEdit(self)
        amount_lay.addWidget(self.edt_amount)

        self.lbl_amount_err = QLabel("", self)
        self.lbl_amount_err.setStyleSheet("color: #ef4444; font-size: 11px;")
        amount_lay.addWidget(self.lbl_amount_err)

        self.lbl_max_stack = QLabel(tm.get("prop_max_stack"), self)
        self.lbl_max_stack.setStyleSheet("font-weight: bold;")
        amount_lay.addWidget(self.lbl_max_stack)

        self.edt_max_stack = QLineEdit(self)
        amount_lay.addWidget(self.edt_max_stack)

        self.lbl_max_stack_err = QLabel("", self)
        self.lbl_max_stack_err.setStyleSheet("color: #ef4444; font-size: 11px;")
        amount_lay.addWidget(self.lbl_max_stack_err)

        right_lay.addWidget(self.amount_widget)
        right_lay.addStretch()

        h_layout.addWidget(self.right_panel, stretch=3)
        layout.addLayout(h_layout)

        # Кнопки управления
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton(tm.get("btn_cancel"), self)
        self.btn_cancel.setStyleSheet(
            "background-color: transparent; border: 1px solid #3f3f46; color: gray;"
        )
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton(tm.get("btn_save"), self)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

        self.current_item_id = None
        self.custom_icon_path = None

        self.chk_stackable.stateChanged.connect(self.toggle_amount_fields)
        self.btn_upload.clicked.connect(self.upload_icon)
        self.btn_cancel.clicked.connect(self.cancel_clicked.emit)
        self.btn_save.clicked.connect(self.save_item)

        self.edt_name.textChanged.connect(self.clear_name_error)
        self.edt_mfr.textChanged.connect(self.clear_mfr_error)
        self.edt_amount.textChanged.connect(self.clear_amount_error)
        self.edt_max_stack.textChanged.connect(self.clear_max_stack_error)

        self.retranslate()

    def retranslate(self):
        """Полная локализация текстовых меток формы редактирования."""
        tm = TranslationManager()
        self.lbl_cat.setText(tm.get("prop_category"))
        self.lbl_name.setText(tm.get("prop_name"))
        self.lbl_mfr.setText(tm.get("prop_manufacturer"))
        self.lbl_cond.setText(tm.get("prop_condition"))
        self.chk_stackable.setText(tm.get("prop_stackable"))
        self.lbl_amount.setText(tm.get("prop_amount"))
        self.lbl_max_stack.setText(tm.get("prop_max_stack"))
        self.btn_upload.setText(tm.get("btn_upload_icon"))
        self.btn_cancel.setText(tm.get("btn_cancel"))
        self.btn_save.setText(tm.get("btn_save"))

        self.cmb_category.blockSignals(True)
        self.cmb_category.clear()
        for cat in ItemType:
            self.cmb_category.addItem(tm.get(f"cat_{cat.value}"), cat)
        self.cmb_category.blockSignals(False)

        self.cmb_condition.blockSignals(True)
        self.cmb_condition.clear()
        for cond in ItemCondition:
            self.cmb_condition.addItem(tm.get(f"cond_{cond.value}"), cond)
        self.cmb_condition.blockSignals(False)

    def clear_name_error(self):
        self.lbl_name_err.clear()
        self.edt_name.setStyleSheet("")

    def clear_mfr_error(self):
        self.lbl_mfr_err.clear()
        self.edt_mfr.setStyleSheet("")

    def clear_amount_error(self):
        self.lbl_amount_err.clear()
        self.edt_amount.setStyleSheet("")

    def clear_max_stack_error(self):
        self.lbl_max_stack_err.clear()
        self.edt_max_stack.setStyleSheet("")

    def toggle_amount_fields(self):
        if self.chk_stackable.isChecked():
            self.amount_widget.show()
        else:
            self.amount_widget.hide()

    def edit_item(self, item: Item):
        self.current_item_id = item.id
        self.custom_icon_path = item.icon_path

        self.edt_name.setText(item.name)
        self.edt_mfr.setText(item.manufacturer)

        cat_idx = self.cmb_category.findData(item.category)
        if cat_idx != -1:
            self.cmb_category.setCurrentIndex(cat_idx)

        cond_idx = self.cmb_condition.findData(item.condition)
        if cond_idx != -1:
            self.cmb_condition.setCurrentIndex(cond_idx)

        self.chk_stackable.setChecked(item.stackable)
        self.toggle_amount_fields()

        self.edt_amount.setText(str(item.amount))
        self.edt_max_stack.setText(
            str(item.max_stack) if item.max_stack is not None else "20"
        )

        self.clear_name_error()
        self.clear_mfr_error()
        self.clear_amount_error()
        self.clear_max_stack_error()

        self.update_icon_view()

    # ИСПРАВЛЕНИЕ: Создание пустого шаблона под форму добавления нового элемента инвентаря
    def prepare_for_creation(self):
        """Подготавливает форму для создания совершенно нового предмета."""
        self.current_item_id = str(uuid.uuid4())
        self.custom_icon_path = None

        self.edt_name.clear()
        self.edt_mfr.clear()

        self.cmb_category.setCurrentIndex(0)
        self.cmb_condition.setCurrentIndex(0)

        self.chk_stackable.setChecked(False)
        self.toggle_amount_fields()

        self.edt_amount.setText("1")
        self.edt_max_stack.setText("20")

        self.clear_name_error()
        self.clear_mfr_error()
        self.clear_amount_error()
        self.clear_max_stack_error()

        self.update_icon_view()

    def update_icon_view(self):
        tm = TranslationManager()
        if self.custom_icon_path and self.custom_icon_path.exists():
            pix = QPixmap(str(self.custom_icon_path))
            self.lbl_path.setText(
                f"{tm.get('lbl_icon_path')}: {self.custom_icon_path.name}"
            )
        else:
            pix = QPixmap(str(Icons / "default.png"))
            self.lbl_path.setText(f"{tm.get('lbl_icon_path')}: {tm.get('lbl_default')}")

        self.lbl_large_icon.setPixmap(pix)

    def upload_icon(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if file_path:
            try:
                temp_item = Item(
                    id=self.current_item_id,
                    category=self.cmb_category.currentData(),
                    name=self.edt_name.text(),
                    manufacturer=self.edt_mfr.text(),
                    amount=1,
                )
                temp_item.change_custom_icon(Path(file_path))
                self.custom_icon_path = temp_item.icon_path
                self.update_icon_view()
            except Exception as e:
                log_error(f"Image scaling deployment failed: {e}")

    def save_item(self):
        tm = TranslationManager()
        name = self.edt_name.text().strip()
        mfr = self.edt_mfr.text().strip()

        valid = True
        if not name:
            self.lbl_name_err.setText(tm.get("err_validation_empty"))
            self.edt_name.setStyleSheet("border: 1px solid #ef4444;")
            valid = False

        if not mfr:
            self.lbl_mfr_err.setText(tm.get("err_validation_empty"))
            self.edt_mfr.setStyleSheet("border: 1px solid #ef4444;")
            valid = False

        amount = 1
        max_stack = None

        if self.chk_stackable.isChecked():
            try:
                amount = int(self.edt_amount.text())
                if amount <= 0:
                    raise ValueError()
            except ValueError:
                self.lbl_amount_err.setText(tm.get("err_validation_empty"))
                self.edt_amount.setStyleSheet("border: 1px solid #ef4444;")
                valid = False

            try:
                max_stack = int(self.edt_max_stack.text())
                if max_stack <= 0:
                    raise ValueError()
                if amount > max_stack:
                    self.lbl_amount_err.setText(tm.get("err_validation_title"))
                    self.edt_amount.setStyleSheet("border: 1px solid #ef4444;")
                    valid = False
            except ValueError:
                self.lbl_max_stack_err.setText(tm.get("err_validation_empty"))
                self.edt_max_stack.setStyleSheet("border: 1px solid #ef4444;")
                valid = False

        if valid:
            updated_data = {
                "new_name": name,
                "new_manufacturer": mfr,
                "new_category": self.cmb_category.currentData(),
                "new_condition": self.cmb_condition.currentData(),
                "new_stackable": self.chk_stackable.isChecked(),
                "new_amount": amount,
                "new_max_stack": max_stack,
                "new_icon_path": self.custom_icon_path,
            }
            self.save_clicked.emit(self.current_item_id, updated_data)

    def update_styles(self, th):
        self.left_panel.setStyleSheet(
            f"""
            QFrame#EditPanel {{
                background-color: {th.get('bg_card', '#2d2d2d')};
                border: 1px solid {th.get('border_color', '#3f3f46')};
                border-radius: 12px;
            }}
            QLabel {{
                color: {th.get('text_primary', '#ffffff')};
            }}
        """
        )
        self.right_panel.setStyleSheet(
            f"""
            QFrame#EditPanel {{
                background-color: {th.get('bg_card', '#2d2d2d')};
                border: 1px solid {th.get('border_color', '#3f3f46')};
                border-radius: 12px;
            }}
            QLabel {{
                color: {th.get('text_primary', '#ffffff')};
            }}
        """
        )


# =====================================================================
# ДЕШБОРД (ГЛАВНОЕ РАБОЧЕЕ ПРОСТРАНСТВО С РАЗДЕЛИТЕЛЕМ)
# =====================================================================
class DashboardWindow(QWidget):
    """Главная рабочая область, координирующая меню, грид и редактирование."""

    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        main_layout.addWidget(self.splitter)

        self.menu = LeftMenuWidget(self.splitter)
        self.splitter.addWidget(self.menu)

        self.right_stack = QStackedWidget(self.splitter)
        self.splitter.addWidget(self.right_stack)

        self.grid_view = InventoryGridView(self.right_stack)
        self.edit_page = EditItemPage(self.right_stack)

        self.right_stack.addWidget(self.grid_view)
        self.right_stack.addWidget(self.edit_page)

        self.splitter.setSizes([240, 760])
        self.splitter.setCollapsible(0, True)

        self.menu.filters_changed.connect(self.apply_filters)
        self.menu.change_account_clicked.connect(self.quick_change_account)
        self.menu.theme_changed.connect(self.on_theme_swapped)
        self.menu.lang_changed.connect(self.on_lang_swapped)

        self.grid_view.btn_hamburger.clicked.connect(self.toggle_menu)
        self.grid_view.edit_requested.connect(self.open_edit_page)
        self.grid_view.create_requested.connect(self.open_creation_page)

        self.edit_page.save_clicked.connect(self.save_item_edits)
        self.edit_page.cancel_clicked.connect(self.close_edit_page)

        self.last_menu_width = 240
        self.active_inventory = None

    def start_dashboard(self):
        user = session_manager.current_user
        self.active_inventory = user.inventory
        self.active_inventory.subscribe(self.on_inventory_changed)

        self.menu.retranslate()
        self.grid_view.retranslate()
        self.edit_page.retranslate()

        self.apply_filters()
        self.right_stack.setCurrentIndex(0)

    def stop_dashboard(self):
        if self.active_inventory:
            self.active_inventory.unsubscribe(self.on_inventory_changed)
            self.active_inventory = None

    def on_inventory_changed(self):
        self.apply_filters()
        self.menu.update_user_info()

    def toggle_menu(self):
        """Анимированное скрытие / развертывание бокового меню (Hamburger)."""
        sizes = self.splitter.sizes()
        menu_w = sizes[0]

        if (
            hasattr(self, "menu_anim")
            and self.menu_anim.state() == QAbstractAnimation.State.Running
        ):
            self.menu_anim.stop()

        if menu_w > 0:
            self.last_menu_width = menu_w
            start_w = menu_w
            end_w = 0
        else:
            start_w = 0
            end_w = self.last_menu_width if self.last_menu_width >= 100 else 240

        self.menu_anim = QVariantAnimation(self)
        self.menu_anim.setDuration(250)
        self.menu_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.menu_anim.setStartValue(start_w)
        self.menu_anim.setEndValue(end_w)

        def set_sizes(val):
            total = sum(self.splitter.sizes())
            self.splitter.setSizes([val, total - val])

        self.menu_anim.valueChanged.connect(set_sizes)
        self.menu_anim.start()

    def apply_filters(self):
        if not session_manager.is_active():
            return

        query = self.menu.edt_search.text()
        cat = self.menu.cmb_category.currentData()

        conds = []
        if self.menu.chk_new.isChecked():
            conds.append(ItemCondition.NEW)
        if self.menu.chk_used.isChecked():
            conds.append(ItemCondition.USED)
        if self.menu.chk_broken.isChecked():
            conds.append(ItemCondition.BROKEN)

        sort_by = self.menu.cmb_sort.currentData()

        user = session_manager.current_user
        filtered_items = user.inventory.get_filtered_and_sorted(
            category=cat, search_query=query, sort_by=sort_by
        )

        filtered_items = [it for it in filtered_items if it.condition in conds]
        self.grid_view.set_items_source(filtered_items)

    def quick_change_account(self):
        dlg = QuickSwitchAccountDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.stop_dashboard()
            self.start_dashboard()

    def open_edit_page(self, item_id):
        user = session_manager.current_user
        target_item = next(
            (it for it in user.inventory.items if it.id == item_id), None
        )
        if target_item:
            self.edit_page.edit_item(target_item)
            self.right_stack.setCurrentIndex(1)

    def open_creation_page(self):
        self.edit_page.prepare_for_creation()
        self.right_stack.setCurrentIndex(1)

    def close_edit_page(self):
        self.right_stack.setCurrentIndex(0)

    # ИСПРАВЛЕНИЕ: Интегрирована одновременная обработка сохранения редактирования и создания нового предмета
    def save_item_edits(self, item_id, updated_data):
        user = session_manager.current_user
        try:
            is_new = True
            if item_id:
                is_new = not any(it.id == item_id for it in user.inventory.items)

            if is_new:
                new_item = Item(
                    id=item_id,
                    category=updated_data["new_category"],
                    name=updated_data["new_name"],
                    manufacturer=updated_data["new_manufacturer"],
                    amount=updated_data["new_amount"],
                    condition=updated_data["new_condition"],
                    stackable=updated_data["new_stackable"],
                    max_stack=updated_data["new_max_stack"],
                    icon_path=updated_data["new_icon_path"],
                )
                user.inventory.add_item(new_item)
            else:
                user.inventory.edit_item(
                    item_id=item_id,
                    new_name=updated_data["new_name"],
                    new_manufacturer=updated_data["new_manufacturer"],
                    new_condition=updated_data["new_condition"],
                    new_category=updated_data["new_category"],
                    new_amount=updated_data["new_amount"],
                    new_stackable=updated_data["new_stackable"],
                    new_max_stack=updated_data["new_max_stack"],
                    new_icon_path=updated_data["new_icon_path"],
                )
            self.right_stack.setCurrentIndex(0)
        except Exception as e:
            log_error(f"Failed to submit edits: {e}")

    def on_theme_swapped(self, theme_name):
        th = ThemeManager()
        qss = generate_qss(th.theme_data)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(qss)

        self.edit_page.update_styles(th.theme_data)
        self.apply_filters()

    def on_lang_swapped(self, lang_code):
        self.menu.retranslate()
        self.grid_view.retranslate()
        self.edit_page.retranslate()
        self.apply_filters()


# =====================================================================
# ОСНОВНОЕ ОКНО ПРИЛОЖЕНИЯ (MAINWINDOW)
# =====================================================================
class MainWindow(QMainWindow):
    """Главный контейнер, управляющий переходами между авторизацией и дешбордом."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(960, 680)

        tm = TranslationManager()
        self.setWindowTitle(tm.get("title_main"))

        self.central = QStackedWidget(self)
        self.setCentralWidget(self.central)

        self.auth_win = AuthWindow(self.central)
        self.dash_win = DashboardWindow(self.central)

        self.central.addWidget(self.auth_win)
        self.central.addWidget(self.dash_win)

        self.auth_win.auth_successful.connect(self.on_auth_success)

        # Контейнер для всплывающих hover-окон
        self.hover_card = HoverCard(None)

    def on_auth_success(self):
        self.central.setCurrentIndex(1)
        self.dash_win.start_dashboard()

    def show_hover_card(self, item, pos):
        self.hover_card.show_item(item, pos)

    def hide_hover_card(self):
        self.hover_card.hide_card()

    def closeEvent(self, event):
        self.dash_win.stop_dashboard()
        session_manager.close_session()
        self.hover_card.close()
        super().closeEvent(event)
