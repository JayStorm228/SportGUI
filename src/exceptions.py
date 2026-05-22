"""
exceptions.py
Система кастомных исключений проекта для типизации и обработки ошибок бизнес-логики.
"""


class AppError(Exception):
    """Базовое исключение для всего приложения."""

    pass


# --- ИСКЛЮЧЕНИЯ АВТОРИЗАЦИИ И СЕССИЙ ---
class AuthError(AppError):
    """Базовое исключение для модуля аутентификации."""

    pass


class UserNotFoundError(AuthError):
    """Вызывается, если пользователь не найден в базе данных."""

    pass


class UserAlreadyExistsError(AuthError):
    """Вызывается при попытке зарегистрировать уже существующий логин."""

    pass


class InvalidPasswordError(AuthError):
    """Вызывается при вводе неверного пароля."""

    pass


class SessionError(AuthError):
    """Ошибки управления сессией (например, доступ к неавторизованному состоянию)."""

    pass


# --- ИСКЛЮЧЕНИЯ ИНВЕНТАРЯ ---
class InventoryError(AppError):
    """Базовое исключение для логики инвентаря."""

    pass


class ItemNotFoundError(InventoryError):
    """Вызывается, если предмет с конкретным ID не найден."""

    pass


class ItemStackError(InventoryError):
    """Вызывается при ошибках стекирования или превышении лимитов ячейки."""

    pass


# --- ИСКЛЮЧЕНИЯ UI И РЕСУРСОВ ---
class ResourceError(AppError):
    """Базовое исключение для менеджеров ресурсов (темы, локализации, генераторы)."""

    pass


class LocalizationError(ResourceError):
    """Вызывается, если перевод или языковой пакет отсутствует/поврежден."""

    pass


class ThemeError(ResourceError):
    """Вызывается при критических ошибках разбора или отсутствия файлов тем."""

    pass


class GeneratorError(ResourceError):
    """Вызывается при невозможности сгенерировать предмет из-за повреждения конфигурации."""

    pass
