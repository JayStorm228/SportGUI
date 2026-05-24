"""
main.py
Точка входа в приложение спортивного инвентаря.
Управляет запуском асинхронного потока загрузки и координирует отображение окон.
"""

import sys

from PySide6.QtWidgets import QApplication

# Импорт необходимых классов и утилит из UI.py
from UI import BootstrapperThread, MainWindow, SplashScreen, ThemeManager, generate_qss

# Глобальная переменная для предотвращения удаления главного окна сборщиком мусора Python
main_win = None


def main():
    global main_win
    app = QApplication(sys.argv)

    # Отображение экрана загрузки при запуске приложения
    splash = SplashScreen()
    splash.show()

    # Инициализация асинхронного потока проверки ресурсов и ассетов
    thread = BootstrapperThread()
    thread.progress_changed.connect(splash.set_progress)

    def on_bootstrap_complete():
        global main_win
        splash.close()

        # Загрузка и инициализация глобальной темы оформления (по умолчанию: dark)
        th = ThemeManager()
        qss = generate_qss(th.theme_data)
        app.setStyleSheet(qss)

        # Создание и отображение главного окна (ссылка сохраняется в глобальной области)
        main_win = MainWindow()
        main_win.show()

    thread.finished_loading.connect(on_bootstrap_complete)
    thread.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
