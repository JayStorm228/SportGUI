"""
ui_dialogs.py
Компонент фронтенда. Реализует универсальное модальное окно (QDialog)
для создания и редактирования сущностей инвентаря с валидацией полей.
"""

import uuid
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from config import Icons, t, theme_manager
from models import Item, ItemCondition, ItemType


class ItemFormDialog(QDialog):
    """Универсальная форма CRUD для создания и изменения спортивного инвентаря."""

    def __init__(
        self, item_to_edit: Optional[Item] = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.item_to_edit = item_to_edit
        self.selected_icon_path: Path = (
            item_to_edit.icon_path if item_to_edit else Icons / "icon.png"
        )

        # Настройка окна
        self.setWindowTitle(t("btn_edit") if item_to_edit else t("btn_add"))
        self.setMinimumWidth(420)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # Главный макет
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)

        # Форм-макет для полей ввода
        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(10)
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        # Инициализация виджетов управления
        self.txt_name = QLineEdit(self)
        self.txt_manufacturer = QLineEdit(self)

        self.spin_amount = QSpinBox(self)
        self.spin_amount.setRange(1, 10000)

        self.combo_category = QComboBox(self)
        for cat in ItemType:
            self.combo_category.addItem(cat.get_label(), cat)

        self.combo_condition = QComboBox(self)
        for cond in ItemCondition:
            self.combo_condition.addItem(cond.get_label(), cond)

        # Логика стекирования (из бэкенда)
        self.chk_stackable = QCheckBox(self)
        self.chk_stackable.toggled.connect(self._toggle_max_stack_visibility)

        self.spin_max_stack = QSpinBox(self)
        self.spin_max_stack.setRange(1, 999)
        self.spin_max_stack.setValue(20)
        self.lbl_max_stack = QLabel("Макс. размер стека:", self)

        # Панель выбора кастомной иконки предмета
        self.icon_layout = QHBoxLayout()
        self.lbl_icon_status = QLabel(self.selected_icon_path.name, self)
        self.lbl_icon_status.setStyleSheet(
            "color: @text_secondary; font-size: @size_small;"
        )
        self.btn_select_icon = QPushButton("📁 Выбрать...", self)
        self.btn_select_icon.clicked.connect(self._handle_icon_selection)
        self.icon_layout.addWidget(self.lbl_icon_status, stretch=1)
        self.icon_layout.addWidget(self.btn_select_icon)

        # Добавляем строки в форму с локализованными заголовками
        self.form_layout.addRow(t("prop_name") + ":", self.txt_name)
        self.form_layout.addRow(t("prop_manufacturer") + ":", self.txt_manufacturer)
        self.form_layout.addRow(t("prop_amount") + ":", self.spin_amount)
        self.form_layout.addRow(t("prop_category") + ":", self.combo_category)
        self.form_layout.addRow(t("prop_condition") + ":", self.combo_condition)
        self.form_layout.addRow("Разрешить стек:", self.chk_stackable)
        self.form_layout.addRow(self.lbl_max_stack, self.spin_max_stack)
        self.form_layout.addRow("Иконка ассета:", self.icon_layout)

        self.main_layout.addLayout(self.form_layout)

        # Нижние системные кнопки Диалога (Сохранить / Отмена)
        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.setSpacing(10)

        self.btn_save = QPushButton("Сохранить", self)
        self.btn_save.setObjectName("btn_dialog_save")
        self.btn_save.clicked.connect(self._validate_and_accept)

        self.btn_cancel = QPushButton("Отмена", self)
        self.btn_cancel.clicked.connect(self.reject)

        self.buttons_layout.addStretch()
        self.buttons_layout.addWidget(self.btn_cancel)
        self.buttons_layout.addWidget(self.btn_save)
        self.main_layout.addLayout(self.buttons_layout)

        # Заполнение полей, если мы вошли в режиме редактирования
        if self.item_to_edit:
            self._fill_form_with_existing_data()
        else:
            self._toggle_max_stack_visibility(False)

        self._apply_dialog_styles()

    def _fill_form_with_existing_data(self) -> None:
        """Переносит текущие метаданные изменяемого объекта в интерфейс формы."""
        item = self.item_to_edit
        if not item:
            return
        self.txt_name.setText(item.name)
        self.txt_manufacturer.setText(item.manufacturer)
        self.spin_amount.setValue(item.amount)

        # Выставляем индексы комбобоксов по сохраненным StrEnum
        cat_idx = self.combo_category.findData(item.category)
        if cat_idx != -1:
            self.combo_category.setCurrentIndex(cat_idx)

        cond_idx = self.combo_condition.findData(item.condition)
        if cond_idx != -1:
            self.combo_condition.setCurrentIndex(cond_idx)

        self.chk_stackable.setChecked(item.stackable)
        self.spin_max_stack.setValue(item.max_stack if item.max_stack else 20)
        self._toggle_max_stack_visibility(item.stackable)

    @Slot(bool)
    def _toggle_max_stack_visibility(self, visible: bool) -> None:
        """Динамически скрывает/показывает лимит стека в зависимости от чекбокса."""
        self.spin_max_stack.setVisible(visible)
        self.lbl_max_stack.setVisible(visible)

    @Slot()
    def _handle_icon_selection(self) -> None:
        """Вызывает системный файловый диалог для импорта кастомной графики."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать иконку инвентаря", "", "Images (*.png *.jpg *.jpeg)"
        )
        if file_path:
            self.selected_icon_path = Path(file_path)
            self.lbl_icon_status.setText(self.selected_icon_path.name)

    @Slot()
    def _validate_and_accept(self) -> None:
        """Проводит валидацию полей сущности перед фиксацией транзакции бэкенда."""
        if not self.txt_name.text().strip() or not self.txt_manufacturer.text().strip():
            QMessageBox.warning(
                self, t("err_validation_title"), t("err_validation_empty")
            )
            return
        self.accept()

    def get_constructed_item_payload(self) -> Item:
        """
        Фабричный метод сбора измененных полей формы.
        Генерирует готовый экземпляр Item для интеграции в ядро БД.
        """
        return Item(
            id=self.item_to_edit.id if self.item_to_edit else str(uuid.uuid4()),
            category=self.combo_category.currentData(),
            name=self.txt_name.text().strip(),
            manufacturer=self.txt_manufacturer.text().strip(),
            amount=self.spin_amount.value(),
            condition=self.combo_condition.currentData(),
            icon_path=self.selected_icon_path,
            stackable=self.chk_stackable.isChecked(),
            max_stack=(
                self.spin_max_stack.value() if self.chk_stackable.isChecked() else None
            ),
        )

    def _apply_dialog_styles(self) -> None:
        """Кастомизирует диалоговое окно под текущую QSS тему оформления."""
        dialog_qss = """
            QDialog { background-color: @bg_main; font-family: @font_main; }
            QLabel { color: @text_primary; font-size: @size_body; }
            QLineEdit, QComboBox, QSpinBox {
                background-color: @bg_card;
                color: @text_primary;
                border: 1px solid @border_color;
                border-radius: 4px;
                padding: 5px;
                font-size: @size_body;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid @accent_primary; }
            QPushButton {
                background-color: @bg_card;
                color: @text_primary;
                border: 1px solid @border_color;
                border-radius: 4px;
                padding: 6px 14px;
                font-size: @size_body;
            }
            QPushButton:hover { background-color: @border_color; }
            QPushButton#btn_dialog_save {
                background-color: @accent_primary;
                color: @text_light;
                border: none;
                font-weight: bold;
            }
            QPushButton#btn_dialog_save:hover { background-color: @accent_hover; }
        """
        self.setStyleSheet(theme_manager.compile_qss(dialog_qss))
