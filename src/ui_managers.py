import json
import re
from pathlib import Path
from typing import Dict, Optional

# ИМПОРТ КАСТОМНЫХ ОШИБОК
from exceptions import LocalizationError, ThemeError


class LocalizationManager:
    _instance: Optional["LocalizationManager"] = None

    def __new__(cls, *args, **kwargs) -> "LocalizationManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, lang_dir: Path, default_lang: str = "ru") -> None:
        if getattr(self, "_initialized", False):
            return
        self.lang_dir = lang_dir
        self.current_lang = default_lang
        self.translations: Dict[str, str] = {}
        self.fallback_translations: Dict[str, str] = {}

        # Инициализируем переводы. Если дефолтного файла нет, будет сбой
        if not self.load_language(self.current_lang):
            raise LocalizationError(
                f"Root localization map at '{self.current_lang}' failed to deploy."
            )

        if self.current_lang != "ru":
            self._load_fallback()
        self._initialized = True

    def load_language(self, lang_code: str) -> bool:
        """Загружает пакет локализации. Возвращает статус операции."""
        file_path = self.lang_dir / f"{lang_code}.json"
        if not file_path.exists():
            return False
        try:
            self.translations = json.loads(file_path.read_text(encoding="utf-8"))
            self.current_lang = lang_code
            return True
        except Exception as e:
            raise LocalizationError(
                f"Corrupted translation stream in {lang_code}.json: {e}"
            )

    def _load_fallback(self) -> None:
        file_path = self.lang_dir / "ru.json"
        if file_path.exists():
            try:
                self.fallback_translations = json.loads(
                    file_path.read_text(encoding="utf-8")
                )
            except Exception:
                pass

    def translate(self, key: str, **kwargs: str | int) -> str:
        """Возвращает переведенную строку с подстановкой именованных аргументов."""
        template = self.translations.get(
            key, self.fallback_translations.get(key, f"[{key}]")
        )
        if kwargs:
            try:
                return template.format(**kwargs)
            except KeyError as e:
                return f"[Bad formatting key {e} for {key}]"
        return template


class ThemeManager:
    _instance: Optional["ThemeManager"] = None

    def __new__(cls, *args, **kwargs) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, theme_dir: Path, default_theme: str = "dark") -> None:
        if getattr(self, "_initialized", False):
            return
        self.theme_dir = theme_dir
        self.current_theme_name = default_theme
        self.theme_tokens: Dict[str, str] = {}

        if not self.load_theme(default_theme):
            raise ThemeError(
                f"Primary theme layout context '{default_theme}' is inaccessible."
            )
        self._initialized = True

    def load_theme(self, theme_name: str) -> bool:
        file_path = self.theme_dir / f"{theme_name}.json"
        if not file_path.exists():
            return False
        try:
            self.theme_tokens = json.loads(file_path.read_text(encoding="utf-8"))
            self.current_theme_name = theme_name
            return True
        except Exception as e:
            raise ThemeError(
                f"Critical error token sequence compilation in theme '{theme_name}': {e}"
            )

    def get_token(self, token_key: str, default_color: str = "#000000") -> str:
        return self.theme_tokens.get(token_key, default_color)

    def compile_qss(self, qss_template: str) -> str:
        """Заменяет абстрактные токены вида @bg_main на реальные HEX-цвета."""
        compiled_qss = qss_template
        tokens_found = re.findall(r"@[a-zA-Z0-9_]+", qss_template)

        for token in tokens_found:
            clean_key = token.lstrip("@")
            if clean_key in self.theme_tokens:
                compiled_qss = compiled_qss.replace(token, self.theme_tokens[clean_key])
            else:
                # Если дизайнер ошибся в QSS шаблоне — бросаем кастомную ошибку
                raise ThemeError(
                    f"QSS stylesheet compilation failure. Token reference '{token}' is unresolved."
                )
        return compiled_qss
