"""
main.py
Точка входа и главный контроллер приложения.
Инициализирует файловую структуру, генерирует первичные тестовые данные,
запускает графическую оболочку PySide6 и связывает воедино бэкенд и фронтенд.
"""

import sys
from pathlib import Path

# Гарантируем, что папка src находится в системном пути поиска модулей
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from PySide6.QtWidgets import QApplication

from auth import authenticate_user, register_user

# Импорт компонентов бизнес-логики и конфигурации
from config import init_storage, log_error, log_info
from generator import generate_random_item
from ui_screens import MainNavigationWindow


def seed_test_data() -> None:
    """
    Генерирует тестовый профиль пользователя и наполняет его инвентарь
    случайными предметами через генератор для визуальной проверки дешборда.
    """
    test_username = "admin"
    test_password = "password123"

    print(" === Подготовка тестовой конфигурации ===")

    # 1. Проверяем, существует ли уже тестовый пользователь через authenticate_user
    try:
        user = authenticate_user(test_username, test_password)
        print(f" -> Найдена существующая учетная запись '{test_username}'.")
    except Exception:
        # Если пользователя нет — регистрируем нового через register_user
        print(
            f" -> Тестовый пользователь не найден. Регистрация нового аккаунта '{test_username}'..."
        )
        user = register_user(test_username, test_password)

    # 2. Если инвентарь пользователя пуст, наполняем его (25 предметов для проверки пагинации)
    if len(user.inventory.items) == 0:
        print(" -> Наполнение инвентаря случайными предметами (25 позиций)...")
        for _ in range(25):
            try:
                # Генерируем случайный предмет из дефолтного профиля
                random_item = generate_random_item("DefaultItemGen.json")
                user.inventory.add_item(random_item)
            except Exception as e:
                log_error(f"Seed Data Generation Error: {e}")

        # ИСПРАВЛЕНО: Вызываем нативный метод сохранения объекта User
        user.save()
        print(
            f" -> Успешно сгенерировано предметов в базе: {len(user.inventory.items)}"
        )
    else:
        print(
            f" -> Инвентарь пользователя уже содержит {len(user.inventory.items)} предметов. Пропуск генерации."
        )


def main() -> None:
    """Основная точка запуска Qt-приложения."""
    # 1. Шаг сборки инфраструктуры (папки, скачивание базовых ассетов-иконок)
    init_storage()

    # 2. Наполнение БД демонстрационными данными
    try:
        seed_test_data()
    except Exception as e:
        print(f"[WARNING] Не удалось подготовить демонстрационные данные: {e}")
        log_error(f"Data seeding skipped due to execution fault: {e}")

    # 3. Инициализация графической платформы Qt
    print("\n Запуск графической оболочки PySide6...")
    log_info("Application GUI boot sequence initiated.")

    app = QApplication(sys.argv)

    # Создаем и отображаем центральное окно навигации
    main_window = MainNavigationWindow()
    main_window.show()

    # Запуск бесконечного цикла обработки сигналов и событий Qt
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
