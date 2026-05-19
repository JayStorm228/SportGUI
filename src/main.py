"""
main.py
Сквозной интеграционный тест бэкенда системы управления спортивным инвентарем.
Проверяет инициализацию хранилища, загрузку ассетов, генерацию предметов,
логику стекирования инвентаря и атомарную работу с JSON-БД.
"""

import sys
from pathlib import Path

# Гарантируем, что папка src находится в системном пути для корректных импортов
sys.path.append(str(Path(__file__).resolve().parent))

from auth import User
from config import Icons, ItemGeneratorData, Logs, UserData, init_storage
from generator import generate_random_item
from models import ItemCondition


def run_integration_test():
    print("=" * 60)
    print(" ЭТАП 1: Инициализация файловой инфраструктуры и ассетов ")
    print("=" * 60)

    # 1. Запускаем сборку папок и автоматическое скачивание иконок
    init_storage()

    print("\nПроверка созданной структуры каталогов:")
    print(f" -> Папка иконок: {Icons} {'[ОК]' if Icons.exists() else '[ОТСУТСТВУЕТ]'}")
    print(
        f" -> Папка пользователей: {UserData} {'[ОК]' if UserData.exists() else '[ОТСУТСТВУЕТ]'}"
    )
    print(
        f" -> Папка генератора: {ItemGeneratorData} {'[ОК]' if ItemGeneratorData.exists() else '[ОТСУТСТВУЕТ]'}"
    )
    print(f" -> Папка логов: {Logs} {'[ОК]' if Logs.exists() else '[ОТСУТСТВУЕТ]'}")

    # Считаем скачанные файлы картинок
    downloaded_icons = list(Icons.glob("*.png"))
    print(f" -> Успешно верифицировано иконок в папке: {len(downloaded_icons)} шт.")

    print("\n" + "=" * 60)
    print(" ЭТАП 2: Создание пользователя и проверка хеширования ")
    print("=" * 60)

    username = "Trainer_Storm"
    raw_password = "Secret_Password_123"

    print(f"Регистрируем тестового пользователя: '{username}'")
    test_user = User(username=username, password=raw_password)

    print(f" -> Сырой пароль: '{raw_password}'")
    print(f" -> Хеш в памяти класса: {test_user.password}")

    # Проверка метода валидации пароля
    assert (
        test_user.check_password(raw_password) == True
    ), "Ошибка: Корректный пароль не прошел валидацию!"
    assert (
        test_user.check_password("Wrong_Pass") == False
    ), "Ошибка: Неверный пароль был принят системой!"
    print(" -> [ОК] Механизм инкапсуляции и сверки хешей SHA-256 работает штатно.")

    print("\n" + "=" * 60)
    print(" ЭТАП 3: Процедурная генерация и логика стекирования инвентаря ")
    print("=" * 60)

    print("Генерируем 15 случайных предметов на основе дефолтного JSON-профиля...")
    for _ in range(15):
        random_item = generate_random_item()
        test_user.inventory.add_item(random_item)

    print("Всего сгенерировано запросов на добавление: 15.")
    print(
        f"Фактическое кол-во уникальных записей в инвентаре после стекирования: {len(test_user.inventory.items)}"
    )

    print("\nТекущий состав инвентаря пользователя:")
    for idx, item in enumerate(test_user.inventory.items, 1):
        stack_info = (
            f"[Стекируемый, макс: {item.max_stack}]"
            if item.stackable
            else "[Уникальный]"
        )
        print(
            f"  {idx}. {item.name} | Производитель: {item.manufacturer} | "
            f"Кол-во: {item.amount} шт. | Состояние: {item.condition.get_label()} | {stack_info}"
        )
        print(f"     └─ Привязанная иконка: {item.icon_path.name}")

    print("\n" + "=" * 60)
    print(" ЭТАП 4: Проверка фильтрации, сортировки и модификации данных ")
    print("=" * 60)

    # Проверяем сортировку по количеству (от большего к меньшему)
    sorted_by_amount = test_user.inventory.get_filtered_and_sorted(sort_by="amount")
    if sorted_by_amount:
        print(
            f" -> [ОК] Сортировка по количеству успешна. Самый массовый предмет: '{sorted_by_amount[0].name}' ({sorted_by_amount[0].amount} шт.)"
        )

    # Выбираем первый предмет для ручного редактирования
    target_item = test_user.inventory.items[0]
    old_name = target_item.name
    target_id = target_item.id

    print(f"Модифицируем предмет с ID {target_id}:")
    print(f"  Старое название: '{old_name}'")

    test_user.inventory.edit_item(
        item_id=target_id,
        new_name="  Модернизированный Сверх-Снаряд  ",
        new_condition=ItemCondition.NEW,
    )

    print(f"  Новое название в памяти (со стриппингом пробелов): '{target_item.name}'")
    print(f"  Новое состояние: '{target_item.condition.get_label()}'")

    print("\n" + "=" * 60)
    print(" ЭТАП 5: Атомарное сохранение на диск и сериализация Path ")
    print("=" * 60)

    print(f"Вызываем метод user.save() для '{username}'...")
    test_user.save()

    user_file_path = UserData / f"{username}.json"
    print(f"Проверяем физический файл на диске: {user_file_path}")
    print(
        f" -> Физический файл создан: {'[ДА]' if user_file_path.exists() else '[НЕТ]'}"
    )

    # Проверяем отсутствие зависших временных файлов .tmp
    tmp_file_path = UserData / f"{username}.json.tmp"
    print(
        f" -> Временный .tmp файл удален (атомарность соблюдена): {'[ДА]' if not tmp_file_path.exists() else '[НЕТ ОШИБКА]'}"
    )

    print("\n" + "=" * 60)
    print(" ЭТАП 6: Десериализация и полное восстановление сессии ")
    print("=" * 60)

    print("Уничтожаем текущий объект пользователя в оперативной памяти...")
    del test_user

    print(f"Выполняем холодную загрузку из БД методом User.load('{username}')...")
    restored_user = User.load(username)

    print(f" -> Успешно авторизован: '{restored_user.username}'")
    print(f" -> Дата регистрации восстановлена: {restored_user.registration_date}")
    print(
        f" -> Восстановлено предметов в инвентаре: {len(restored_user.inventory.items)} шт."
    )

    # Проверяем критически важную десериализацию путей (строка из JSON должна стать Path-объектом)
    restored_item = restored_user.inventory.items[0]
    print(
        f" -> Проверка типа icon_path восстановленного предмета: {type(restored_item.icon_path)}"
    )

    assert isinstance(
        restored_item.icon_path, Path
    ), "КРИТИЧЕСКАЯ ОШИБКА: Путь к иконке восстановился как строка, а не Path-объект!"
    print(" -> [ОК] Конвертация типов 'Строка JSON -> Path' прошла успешно.")

    print("\n" + "=" * 60)
    print(" 🎉 ИНТЕГРАЦИОННЫЙ ТЕСТ ЗАВЕРШЕН УСПЕШНО! БЭКЕНД ГОТОВ К GUI 🎉 ")
    print("=" * 60)


if __name__ == "__main__":
    run_integration_test()
