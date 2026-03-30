import os
import platform
from difflib import SequenceMatcher
from pathlib import Path

from tools.base import BaseTool
from utils.logger import setup_logger

# -------------------------
# 🔥 CONFIG
# -------------------------
IGNORED_DIRS = {
    "venv", "__pycache__", ".git", "node_modules",
    "site-packages", "dist", "build", ".idea", ".vscode",
    "__pypackages__", ".pytest_cache", ".mypy_cache"
}

MAX_RESULTS = 5
MAX_DEPTH = 5


def similarity(a, b):
    """Вычисляет схожесть двух строк (0.0 - 1.0)"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


logger = setup_logger("Tool:find")


class FindTool(BaseTool):
    """
    Инструмент поиска файлов и папок.
    Кросс-платформенный: Windows, Linux, macOS.
    """

    name = "find"
    description = "Ищет файл или папку по имени"

    required_args = ["name"]
    optional_args = ["type", "start_path"]

    category = "file"
    risk_level = "low"

    def __init__(self):
        super().__init__()
        self._default_start_path = None

    def _get_default_start_path(self):
        """
        Возвращает стартовый путь по умолчанию в зависимости от ОС.
        """
        if self._default_start_path is not None:
            return self._default_start_path

        system = platform.system()

        if system == "Windows":
            path = Path.home().drive + "\\" if hasattr(Path.home(), 'drive') else "C:\\"
        elif system == "Darwin":  # macOS
            path = str(Path.home())
        else:  # Linux и другие Unix
            path = str(Path.home())

        self._default_start_path = path
        logger.debug(f"Default start path ({system}): {path}")
        return path

    def _normalize_path(self, path):
        """
        Нормализует путь для текущей ОС.
        """
        if path is None:
            return None

        # Раскрываем ~ в домашнюю директорию
        if path.startswith("~"):
            path = os.path.expanduser(path)

        # Преобразуем относительный путь в абсолютный
        path = os.path.abspath(path)

        return path

    def run(self, name, type="any", start_path=None, path=None):
        """
        Ищет файл или папку.

        Args:
            name: Имя для поиска
            type: "file", "folder" или "any"
            start_path: Где искать (если None — используется дефолт ОС)
            path: Выбранный путь (для clarification)

        Returns:
            ToolResponse с результатом
        """
        logger.info(f"FIND START: name={name}, type={type}, start_path={start_path}, selected={path}")

        # -------------------------
        # 🔥 SELECTED (multiple results)
        # -------------------------
        if path:
            logger.info(f"FIND SELECTED: {path}")
            return self.success(
                data={"path": path},
                message=f"Выбран путь: {path}"
            )

        if not name:
            return self.error("Имя для поиска не указано")

        name_lower = name.lower()

        # -------------------------
        # 🔥 Определяем стартовый путь
        # -------------------------
        if start_path:
            start_path = self._normalize_path(start_path)
            if not os.path.exists(start_path):
                return self.error(f"Стартовый путь не существует: {start_path}")
        else:
            start_path = self._get_default_start_path()

        logger.debug(f"Searching in: {start_path}")

        results = []
        scanned_dirs = 0
        scanned_items = 0

        try:
            for root, dirs, files in os.walk(start_path):
                scanned_dirs += 1

                # Проверяем глубину
                try:
                    depth = root[len(start_path):].count(os.sep)
                except:
                    depth = 0

                if depth > MAX_DEPTH:
                    del dirs[:]  # Не заходим глубже
                    continue

                # Фильтруем игнорируемые директории
                dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

                # Выбираем что искать
                if type == "folder":
                    items = dirs
                elif type == "file":
                    items = files
                else:
                    items = dirs + files

                for item in items:
                    scanned_items += 1

                    full_path = os.path.join(root, item)
                    item_lower = item.lower()

                    # EXACT MATCH (высший приоритет)
                    if item_lower == name_lower:
                        logger.info(f"FIND EXACT MATCH: {full_path}")
                        return self.success(
                            data={"path": full_path},
                            message=f"Найдено: {full_path}"
                        )

                    # FUZZY MATCH
                    score = similarity(name_lower, item_lower)

                    # Бонус если имя содержится в названии
                    if name_lower in item_lower:
                        score += 0.3

                    # Бонус за близость к корню
                    try:
                        distance = root.count(os.sep)
                        score += max(0, 1 - distance * 0.1)
                    except:
                        pass

                    if score > 0.4:
                        results.append((score, full_path))
                    if score > 1:
                        logger.debug(f"MATCH: {full_path} | score={round(score, 2)}")

        except PermissionError as e:
            logger.warning(f"Permission denied: {e}")
            # Продолжаем поиск, не падаем
        except Exception as e:
            logger.exception(f"Error during search: {e}")
            return self.error(f"Ошибка поиска: {str(e)}")

        logger.debug(f"SCAN COMPLETE: dirs={scanned_dirs}, items={scanned_items}")

        if not results:
            logger.warning(f"FIND FAILED: {name} not found")
            return self.error(f"Не найдено: {name}")

        # Сортируем по score
        results.sort(key=lambda x: x[0], reverse=True)
        top = [p for _, p in results[:MAX_RESULTS]]

        logger.info(f"FIND RESULTS: {len(top)} candidates")

        # SINGLE RESULT
        if len(top) == 1:
            logger.info(f"FIND SINGLE RESULT: {top[0]}")
            return self.success(
                data={"path": top[0]},
                message=f"Найдено: {top[0]}"
            )

        # MULTIPLE RESULTS — нужен выбор
        logger.info(f"FIND MULTIPLE RESULTS: {top}")
        return self.need_clarification(
            options=top,
            message=f"Найдено {len(top)} вариантов для '{name}', выбери:"
        )
