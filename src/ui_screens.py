"""
ui_screens.py
Фронтенд-слой приложения на PySide6.
Реализует экраны Загрузки, Авторизации и Главного дешборда инвентаря.
Полностью типизирован для Pylance и интегрирован с подсистемами UI и бизнес-логики.
"""

from enum import IntEnum, auto
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from auth import authenticate_user, register_user, session_manager

# Импорт бэкенд-компонентов, типов и конфигурации
from config import log_info, t, theme_manager
from exceptions import (
    AuthError,
    InvalidPasswordError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from models import Item, ItemCondition, ItemType
from ui_dialogs import ItemFormDialog


class ScreenType(IntEnum):
    """Типизированные индексы для QStackedWidget."""

    LOADING = 0
    AUTH = auto()
    MAIN_DASHBOARD = auto()


class BaseScreen(QWidget):
    """Базовый класс экрана со встроенной автоматической поддержкой тем оформления."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(self.__class__.__name__)

    def refresh_style(self) -> None:
        """Рекурсивно обновляет QSS стили экрана на основе токенов темы."""
        qss_template = f"QWidget#{self.objectName()} {{ background-color: @bg_main; }}"
        self.setStyleSheet(theme_manager.compile_qss(qss_template))


# =====================================================================
# 1) ЭКРАН ЗАГРУЗКИ (LOADING SCREEN)
# =====================================================================
class LoadingScreen(BaseScreen):
    """Имитирует проверку ассетов и переводит приложение на экран авторизации."""

    def __init__(
        self, navigation_callback: Callable[[], None], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.goToAuth = navigation_callback

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel("Sports Gear DB Prototype", self)
        self.title_label.setStyleSheet(
            "font-size: @size_title; font-weight: @weight_bold; color: @text_primary;"
        )

        self.status_label = QLabel(t("lbl_loading"), self)
        self.status_label.setStyleSheet(
            "font-size: @size_body; color: @text_secondary;"
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.title_label)
        layout.addSpacing(20)
        layout.addWidget(self.status_label)

        self.refresh_style()

        self.loading_timer = QTimer(self)
        self.loading_timer.setSingleShot(True)
        self.loading_timer.timeout.connect(self._on_boot_complete)
        self.loading_timer.start(1500)

    @Slot()
    def _on_boot_complete(self) -> None:
        log_info("System boot simulation sequence completed successfully.")
        self.goToAuth()

    def refresh_style(self) -> None:
        base_qss = f"""
            QWidget#{self.objectName()} {{ background-color: {theme_manager.get_token('bg_dark', '#121212')}; }}
            QLabel {{ font-family: @font_main; color: {theme_manager.get_token('text_light', '#FFFFFF')}; }}
        """
        self.setStyleSheet(base_qss)


# =====================================================================
# 2) ЭКРАН АВТОРИЗАЦИИ / РЕГИСТРАЦИИ (AUTH SCREEN)
# =====================================================================
class AuthScreen(BaseScreen):
    """Объединяет в себе состояние входа (Login) и регистрации (Register)."""

    def __init__(
        self, success_callback: Callable[[], None], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.on_success = success_callback
        self.is_register_mode: bool = False

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.setSpacing(15)

        self.title_label = QLabel(self)
        self.title_label.setStyleSheet(
            "font-size: @size_subtitle; font-weight: @weight_bold;"
        )
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.username_input = QLineEdit(self)
        self.username_input.setFixedWidth(280)

        self.password_input = QLineEdit(self)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFixedWidth(280)

        self.action_button = QPushButton(self)
        self.action_button.setFixedWidth(280)
        self.action_button.clicked.connect(self._handle_action)

        self.toggle_mode_button = QPushButton(self)
        self.toggle_mode_button.setStyleSheet(
            "background: transparent; border: none; text-decoration: underline;"
        )
        self.toggle_mode_button.clicked.connect(self._toggle_auth_mode)

        self.main_layout.addWidget(self.title_label)
        self.main_layout.addSpacing(10)
        self.main_layout.addWidget(self.username_input)
        self.main_layout.addWidget(self.password_input)
        self.main_layout.addSpacing(5)
        self.main_layout.addWidget(self.action_button)
        self.main_layout.addWidget(self.toggle_mode_button)

        self._update_ui_text()
        self.refresh_style()

    def _update_ui_text(self) -> None:
        self.username_input.setPlaceholderText(t("lbl_username"))
        self.password_input.setPlaceholderText(t("lbl_password"))

        if not self.is_register_mode:
            self.title_label.setText(t("title_auth"))
            self.action_button.setText(t("btn_login"))
            self.toggle_mode_button.setText(t("btn_goto_register"))
        else:
            self.title_label.setText(t("btn_register"))
            self.action_button.setText(t("btn_register"))
            self.toggle_mode_button.setText(t("btn_goto_login"))

    def _toggle_auth_mode(self) -> None:
        self.is_register_mode = not self.is_register_mode
        self.username_input.clear()
        self.password_input.clear()
        self._update_ui_text()

    @Slot()
    def _handle_action(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(
                self, t("err_validation_title"), t("err_validation_empty")
            )
            return

        try:
            if not self.is_register_mode:
                user = authenticate_user(username, password)
                session_manager.start_session(user)
            else:
                user = register_user(username, password)
                session_manager.start_session(user)

            self.on_success()

        except UserNotFoundError:
            QMessageBox.critical(
                self, t("err_title"), t("err_user_not_found", username=username)
            )
        except UserAlreadyExistsError:
            QMessageBox.critical(
                self, t("err_title"), t("err_user_already_exists", username=username)
            )
        except InvalidPasswordError:
            QMessageBox.critical(self, t("err_title"), t("err_invalid_password"))
        except AuthError as e:
            QMessageBox.critical(self, t("err_title"), f"{t('err_core_fault')}: {e}")

    def refresh_style(self) -> None:
        raw_qss = """
            QWidget#AuthScreen { background-color: @bg_main; font-family: @font_main; }
            QLabel { color: @text_primary; }
            QLineEdit {
                background-color: @bg_card;
                color: @text_primary;
                border: 1px solid @border_color;
                border-radius: 4px;
                padding: 6px;
                font-size: @size_body;
            }
            QLineEdit:focus { border: 1px solid @accent_primary; }
            QPushButton {
                background-color: @accent_primary;
                color: @text_light;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: @size_body;
                font-weight: @weight_bold;
            }
            QPushButton:hover { background-color: @accent_hover; }
            QPushButton#toggle_mode_button { color: @accent_primary; font-weight: @weight_normal; font-size: @size_small; }
        """
        self.toggle_mode_button.setObjectName("toggle_mode_button")
        self.setStyleSheet(theme_manager.compile_qss(raw_qss))


# =====================================================================
# 3) ГЛАВНЫЙ ЭКРАН ИНВЕНТАРЯ (DASHBOARD SCREEN)
# =====================================================================
class DashboardScreen(BaseScreen):
    """
    Основное рабочее пространство приложения (Страница 1 и 2 макета GUI.pdf).
    Реализует поиск, фильтрацию, постраничный вывод табличных данных
    и вызовы CRUD операций над объектами спортивного снаряжения.
    """

    ITEMS_PER_PAGE: int = 12

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_page: int = 1
        self._cached_filtered_items: List[Item] = []

        # Базовая верстка: Верхняя панель, Центральный блок (Таблица + Команды), Нижняя панель
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # --- ВЕРХНЯЯ ПАНЕЛЬ СФИЛЬТРАМИ (TOP CONTROLS LAYOUT) ---
        top_layout = QHBoxLayout()
        top_layout.setSpacing(10)

        self.search_input = QLineEdit(self)
        self.search_input.textChanged.connect(self._reset_and_refresh_data)

        self.category_combo = QComboBox(self)
        self.category_combo.currentIndexChanged.connect(self._reset_and_refresh_data)

        self.condition_combo = QComboBox(self)
        self.condition_combo.currentIndexChanged.connect(self._reset_and_refresh_data)

        top_layout.addWidget(self.search_input, stretch=4)
        top_layout.addWidget(self.category_combo, stretch=2)
        top_layout.addWidget(self.condition_combo, stretch=2)
        main_layout.addLayout(top_layout)

        # --- ЦЕНТРАЛЬНЫЙ БЛОК: ТАБЛИЦА + БОКОВЫЕ КНОПКИ ---
        center_layout = QHBoxLayout()
        center_layout.setSpacing(15)

        # Конфигурация таблицы PySide6
        self.table_widget = QTableWidget(self)
        self.table_widget.setColumnCount(5)
        self.table_widget.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_widget.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        center_layout.addWidget(self.table_widget, stretch=6)

        # Боковая панель CRUD-команд
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        sidebar_layout.setSpacing(10)

        self.btn_add = QPushButton(self)
        self.btn_add.clicked.connect(self._on_add_clicked)

        self.btn_edit = QPushButton(self)
        self.btn_edit.clicked.connect(self._on_edit_clicked)

        self.btn_delete = QPushButton(self)
        self.btn_delete.clicked.connect(self._on_delete_clicked)

        sidebar_layout.addWidget(self.btn_add)
        sidebar_layout.addWidget(self.btn_edit)
        sidebar_layout.addWidget(self.btn_delete)
        center_layout.addLayout(sidebar_layout, stretch=1)

        main_layout.addLayout(center_layout)

        # --- НИЖНЯЯ ПАНЕЛЬ ПАГИНАЦИИ (PAGINATION FOOTER) ---
        footer_layout = QHBoxLayout()

        self.btn_prev = QPushButton("◀", self)
        self.btn_prev.setFixedWidth(45)
        self.btn_prev.clicked.connect(self._on_prev_page)

        self.page_info_label = QLabel(self)
        self.page_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_next = QPushButton("▶", self)
        self.btn_next.setFixedWidth(45)
        self.btn_next.clicked.connect(self._on_next_page)

        footer_layout.addWidget(self.btn_prev)
        footer_layout.addWidget(self.page_info_label, stretch=1)
        footer_layout.addWidget(self.btn_next)
        main_layout.addLayout(footer_layout)

        # Первичная сборка текстов
        self._rebuild_combobox_structures()
        self.update_ui_text()
        self.refresh_style()

    @Slot()
    def _on_add_clicked(self) -> None:
        """Создает модальное окно формы и добавляет новую позицию в инвентарь."""
        dialog = ItemFormDialog(item_to_edit=None, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_item = dialog.get_constructed_item_payload()

            # Атомарно пушим через ядро бэкенда (инвентарь сам вызовет _notify_listeners)
            session_manager.current_user.inventory.add_item(new_item)
            log_info(
                f"Dashboard: Inserted new item '{new_item.name}' into core active storage."
            )

    @Slot()
    def _on_edit_clicked(self) -> None:
        """Извлекает выбранный объект и открывает форму в режиме редактирования."""
        item_id = self._get_selected_item_id()
        if not item_id:
            QMessageBox.information(
                self,
                t("title_main"),
                "Пожалуйста, выберите предмет для редактирования.",
            )
            return

        # Находим нужный объект в памяти инвентаря
        inventory_ref = session_manager.current_user.inventory
        target_item = next((it for it in inventory_ref.items if it.id == item_id), None)

        if not target_item:
            return

        dialog = ItemFormDialog(item_to_edit=target_item, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_payload = dialog.get_constructed_item_payload()

            # Вызываем метод перезаписи данных в бэкенде
            inventory_ref.update_item(
                item_id=item_id,
                new_name=updated_payload.name,
                new_manufacturer=updated_payload.manufacturer,
                new_amount=updated_payload.amount,
                new_category=updated_payload.category,
                new_condition=updated_payload.condition,
            )
            log_info(
                f"Dashboard: Mutation commit applied successfully for item sequence: {item_id}"
            )

    def update_ui_text(self) -> None:
        """Переводит заголовки, плейсхолдеры и надписи кнопок дешборда."""
        self.search_input.setPlaceholderText(
            f"🔍 {t('prop_name')} / {t('prop_manufacturer')}..."
        )

        # Заголовки колонок таблицы
        headers = [
            t("prop_name"),
            t("prop_manufacturer"),
            t("prop_amount"),
            t("prop_condition"),
            t("prop_category"),
        ]
        self.table_widget.setHorizontalHeaderLabels(headers)

        # Кнопки команд
        self.btn_add.setText(f"➕ {t('btn_add')}")
        self.btn_edit.setText(f"✏️ {t('btn_edit')}")
        self.btn_delete.setText(f"❌ {t('btn_delete')}")

        self._refresh_table_viewonly()

    def _rebuild_combobox_structures(self) -> None:
        """Наполняет выпадающие списки фильтров локализованными элементами."""
        self.category_combo.blockSignals(True)
        self.condition_combo.blockSignals(True)

        self.category_combo.clear()
        self.category_combo.addItem("— Все Категории —", None)
        for cat in ItemType:
            self.category_combo.addItem(cat.get_label(), cat)

        self.condition_combo.clear()
        self.condition_combo.addItem("— Все Состояния —", None)
        for cond in ItemCondition:
            self.condition_combo.addItem(cond.get_label(), cond)

        self.category_combo.blockSignals(False)
        self.condition_combo.blockSignals(False)

    def load_user_data(self) -> None:
        """Точка входа: вызывается контейнером при успешном входе пользователя."""
        # Подписываем дешборд на изменения инвентаря бэкенда (Observer pattern)
        session_manager.current_user.inventory.subscribe(self._reset_and_refresh_data)
        self._reset_and_refresh_data()

    @Slot()
    def _reset_and_refresh_data(self, *args) -> None:
        """Сбрасывает индекс пагинации на 1 и пересчитывает кэш отфильтрованных строк."""
        if not session_manager.is_active():
            return

        search_q = self.search_input.text()
        selected_cat = self.category_combo.currentData()
        selected_cond = self.condition_combo.currentData()

        # Вызов оптимизированного метода фильтрации из бэкенда (models.py)
        self._cached_filtered_items = (
            session_manager.current_user.inventory.get_filtered_and_sorted(
                category=selected_cat, condition=selected_cond, search_query=search_q
            )
        )
        self.current_page = 1
        self._refresh_table_viewonly()

    def _refresh_table_viewonly(self) -> None:
        """Отрисовывает срез элементов для текущей страницы без сброса фильтров."""
        if not session_manager.is_active():
            return

        total_items = len(self._cached_filtered_items)
        max_pages = max(
            1, (total_items + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE
        )

        # Корректируем рамки страницы при динамическом удалении элементов
        if self.current_page > max_pages:
            self.current_page = max_pages

        # Обновление надписи пагинации через форматированный токен словаря
        self.page_info_label.setText(
            t("dashboard_page_info", current=self.current_page, total=max_pages)
        )

        # Блокировка кнопок на границах
        self.btn_prev.setEnabled(self.current_page > 1)
        self.btn_next.setEnabled(self.current_page < max_pages)

        # Вычисление среза данных для таблицы
        start_idx = (self.current_page - 1) * self.ITEMS_PER_PAGE
        end_idx = start_idx + self.ITEMS_PER_PAGE
        page_items = self._cached_filtered_items[start_idx:end_idx]

        self.table_widget.setRowCount(len(page_items))

        for row, item in enumerate(page_items):
            # Создаем ячейки с флагом только для чтения
            name_item = QTableWidgetItem(item.name)
            name_item.setData(
                Qt.ItemDataRole.UserRole, item.id
            )  # Прячем ID в метаданные ячейки

            manuf_item = QTableWidgetItem(item.manufacturer)
            amount_item = QTableWidgetItem(str(item.amount))
            cond_item = QTableWidgetItem(item.condition.get_label())
            cat_item = QTableWidgetItem(item.category.get_label())

            for col, widget_item in enumerate(
                [name_item, manuf_item, amount_item, cond_item, cat_item]
            ):
                widget_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                self.table_widget.setItem(row, col, widget_item)

    @Slot()
    def _on_prev_page(self) -> None:
        if self.current_page > 1:
            self.current_page -= 1
            self._refresh_table_viewonly()

    @Slot()
    def _on_next_page(self) -> None:
        total_items = len(self._cached_filtered_items)
        max_pages = (total_items + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE
        if self.current_page < max_pages:
            self.current_page += 1
            self._refresh_table_viewonly()

    def _get_selected_item_id(self) -> Optional[str]:
        """Вспомогательный метод: извлекает ID выделенного в таблице предмета."""
        selected_ranges = self.table_widget.selectedRanges()
        if not selected_ranges:
            return None
        row = selected_ranges[0].topRow()
        name_item = self.table_widget.item(row, 0)
        if name_item:
            return str(name_item.data(Qt.ItemDataRole.UserRole))
        return None

    # --- ЗАГЛУШКИ ДЛЯ CRUD ОПЕРАЦИЙ (ИНТЕГРАЦИЯ С ДИАЛОГАМИ НА СЛЕДУЮЩЕМ ЭТАПЕ) ---
    @Slot()
    def _on_add_clicked(self) -> None:
        log_info("Dashboard: Add new item dialog trigger triggered.")
        # Будет связано с вызовом кастомного диалогового окна формы создания предмета

    @Slot()
    def _on_edit_clicked(self) -> None:
        item_id = self._get_selected_item_id()
        if not item_id:
            QMessageBox.information(
                self,
                t("title_main"),
                "Пожалуйста, выберите предмет для редактирования.",
            )
            return
        log_info(f"Dashboard: Edit item initiated for sequence ID {item_id}")

    @Slot()
    def _on_delete_clicked(self) -> None:
        item_id = self._get_selected_item_id()
        if not item_id:
            QMessageBox.information(
                self, t("title_main"), "Пожалуйста, выберите предмет для удаления."
            )
            return

        # Прямое атомарное удаление через ядро инвентаря нашего бэкенда
        try:
            session_manager.current_user.inventory.remove_item(item_id)
            log_info(
                f"Dashboard: Item {item_id} purged from state profile database by user request."
            )
        except Exception as e:
            QMessageBox.critical(
                self, t("err_title"), f"Не удалось удалить предмет: {e}"
            )

    def refresh_style(self) -> None:
        """Компилирует специализированную QSS-карту для токенов таблиц, комбобоксов и полей ввода."""
        raw_qss = """
            QWidget#DashboardScreen { background-color: @bg_main; font-family: @font_main; }
            QLabel { color: @text_primary; font-size: @size_body; }

            QLineEdit, QComboBox {
                background-color: @bg_card;
                color: @text_primary;
                border: 1px solid @border_color;
                border-radius: 4px;
                padding: 5px;
                font-size: @size_body;
            }
            QLineEdit:focus, QComboBox:focus { border: 1px solid @accent_primary; }

            QTableWidget {
                background-color: @bg_card;
                color: @text_primary;
                gridline-color: @border_color;
                border: 1px solid @border_color;
                border-radius: 4px;
                font-size: @size_body;
            }
            QHeaderView::section {
                background-color: @bg_dark;
                color: @text_secondary;
                padding: 6px;
                font-weight: bold;
                border: 1px solid @border_color;
            }
            QTableWidget::item:selected {
                background-color: @accent_primary;
                color: @text_light;
            }

            QPushButton {
                background-color: @bg_card;
                color: @text_primary;
                border: 1px solid @border_color;
                border-radius: 4px;
                padding: 8px 12px;
                font-size: @size_body;
            }
            QPushButton:hover { background-color: @border_color; }
            QPushButton:disabled { color: @text_secondary; background-color: @bg_dark; }

            QPushButton#btn_add {
                background-color: @accent_primary;
                color: @text_light;
                border: none;
                font-weight: bold;
            }
            QPushButton#btn_add:hover { background-color: @accent_hover; }
        """
        self.btn_add.setObjectName("btn_add")
        self.setStyleSheet(theme_manager.compile_qss(raw_qss))


# =====================================================================
# ЦЕНТРАЛЬНОЕ ОКНО ПРИЛОЖЕНИЯ (MAIN INTERFACE ARCHITECTURE)
# =====================================================================
class MainNavigationWindow(QMainWindow):
    """Глобальный контейнер приложения. Управляет QStackedWidget и переключением экранов."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(t("title_main"))
        self.resize(1100, 800)

        self.stacked_widget = QStackedWidget(self)
        self.setCentralWidget(self.stacked_widget)

        # Сборка стека экранов с передачей типизированных колбэков
        self.loading_screen = LoadingScreen(
            navigation_callback=self.show_auth_screen, parent=self
        )
        self.auth_screen = AuthScreen(
            success_callback=self.show_main_dashboard, parent=self
        )
        self.dashboard_screen = DashboardScreen(parent=self)

        self.stacked_widget.addWidget(self.loading_screen)
        self.stacked_widget.addWidget(self.auth_screen)
        self.stacked_widget.addWidget(self.dashboard_screen)

        self.stacked_widget.setCurrentIndex(ScreenType.LOADING)

    @Slot()
    def show_auth_screen(self) -> None:
        self.stacked_widget.setCurrentIndex(ScreenType.AUTH)

    @Slot()
    def show_main_dashboard(self) -> None:
        """Переводит интерфейс на рабочий стол инвентаря авторизованного профиля."""
        # Накатываем данные пользователя в дешборд и запускаем его внутренние механизмы
        self.dashboard_screen.load_user_data()

        # Обновляем тексты дешборда в соответствии с языком, выбранным на момент входа
        self.dashboard_screen.update_ui_text()

        # Переключаем стек отображения
        self.stacked_widget.setCurrentIndex(ScreenType.MAIN_DASHBOARD)
        log_info("Navigation: Seamless transition to DashboardScreen executed.")
