import os
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

from tools.base import BaseTool
from utils.logger import setup_logger

logger = setup_logger("Tool:create_file")


class CreateFileTool(BaseTool):
    name = "create_file"
    description = "Создаёт файл или папку с возможностью отката"
    
    required_args = ["path"]
    optional_args = ["content", "overwrite", "is_directory"]
    
    category = "file"
    risk_level = "medium"

    def __init__(self):
        # Директория для бэкапов (для undo)
        self.backup_dir = Path(tempfile.gettempdir()) / "agent_undo" / "created"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"CreateFileTool backup dir: {self.backup_dir}")

    def run(self, **kwargs):
        path = kwargs.get("path")
        content = kwargs.get("content", "")
        overwrite = kwargs.get("overwrite", False)
        is_directory = kwargs.get("is_directory", False)

        logger.info(f"CREATE: {path} (is_directory={is_directory})")

        try:
            if not path:
                return {"status": "error", "error": "Path not specified"}

            # Нормализация пути
            path = os.path.abspath(path)

            # -------------------------
            # 🔥 СОЗДАНИЕ ПАПКИ
            # -------------------------
            if is_directory or path.endswith(('/', '\\')):
                return self._create_directory(path, overwrite)

            # -------------------------
            # 🔥 СОЗДАНИЕ ФАЙЛА
            # -------------------------
            return self._create_file(path, content, overwrite)

        except Exception as e:
            logger.exception("Create failed")
            return {"status": "error", "error": str(e)}

    def _create_directory(self, path: str, overwrite: bool):
        """Создаёт папку рекурсивно."""
        try:
            # Убираем trailing slash для проверок
            clean_path = path.rstrip('/\\')
            
            # Проверка существования
            if os.path.exists(clean_path):
                if not overwrite:
                    return {
                        "status": "error", 
                        "error": f"Directory already exists: {clean_path}"
                    }
                logger.info(f"Directory exists, skipping creation: {clean_path}")
                return {
                    "status": "success",
                    "data": {"path": clean_path, "type": "directory"},
                    "undo_data": None  # Нечего откатывать, папка уже была
                }

            # Создаём рекурсивно (все родительские папки тоже)
            os.makedirs(clean_path, exist_ok=True)
            logger.info(f"Created directory: {clean_path}")

            return {
                "status": "success",
                "data": {"path": clean_path, "type": "directory"},
                "undo_data": {
                    "path": clean_path,
                    "is_directory": True,
                    "backup_path": None  # Для папки просто удаляем при undo
                }
            }

        except Exception as e:
            logger.exception("Create directory failed")
            return {"status": "error", "error": str(e)}

    def _create_file(self, path: str, content: str, overwrite: bool):
        """Создаёт файл (и родительские папки если нужно)."""
        try:
            folder = os.path.dirname(path)

            # 🔥 Создаём родительские папки если их нет
            if folder and not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)
                logger.info(f"Created parent directories: {folder}")

            # Проверка существования файла
            backup_info = None
            if os.path.exists(path):
                if not overwrite:
                    return {
                        "status": "error", 
                        "error": f"File already exists: {path}"
                    }
                # Бэкап существующего файла перед перезаписью
                backup_info = self._backup_existing_file(path)
                logger.info(f"Overwriting with backup: {path}")

            # Создание файла
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            # Тип файла
            ext = os.path.splitext(path)[1].lower()
            file_type = {
                ".txt": "text",
                ".py": "Python",
                ".json": "JSON",
                ".md": "Markdown",
                ".docx": "Word"
            }.get(ext, "unknown")

            logger.info(f"Created [{file_type}]: {path}")

            # Формируем undo_data
            undo_data = {
                "path": path,
                "is_directory": False,
                "backup_path": backup_info["backup_path"] if backup_info else None,
                "had_existing_file": backup_info is not None
            }

            return {
                "status": "success",
                "data": {"path": path, "type": file_type},
                "undo_data": undo_data
            }

        except Exception as e:
            logger.exception("Create file failed")
            return {"status": "error", "error": str(e)}

    def _backup_existing_file(self, path: str) -> dict:
        """Создаёт бэкап существующего файла перед перезаписью."""
        try:
            source = Path(path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}_{source.name}"
            backup_path = self.backup_dir / backup_name
            
            shutil.copy2(source, backup_path)
            logger.debug(f"Backed up existing file: {backup_path}")
            
            return {
                "backup_path": str(backup_path),
                "original_path": path
            }
        except Exception as e:
            logger.warning(f"Failed to backup file: {e}")
            return None

    def undo(self, path: str, is_directory: bool, backup_path: str = None, 
             had_existing_file: bool = False):
        """
        Откатывает создание файла/папки.
        - Для файла: удаляет созданный файл, восстанавливает бэкап если был
        - Для папки: удаляет папку рекурсивно
        """
        logger.info(f"UNDO CREATE: {path} (is_directory={is_directory})")

        try:
            target = Path(path)

            if not target.exists():
                logger.warning(f"Nothing to undo, path doesn't exist: {path}")
                return {"status": "success", "data": "Nothing to undo"}

            # -------------------------
            # 🔥 ОТКАТ ФАЙЛА
            # -------------------------
            if not is_directory:
                # Удаляем созданный файл
                os.remove(target)
                logger.info(f"Deleted created file: {path}")

                # Восстанавливаем бэкап если был
                if had_existing_file and backup_path and os.path.exists(backup_path):
                    shutil.copy2(backup_path, target)
                    os.remove(backup_path)  # Чистим бэкап
                    logger.info(f"Restored previous version: {path}")
                    return {
                        "status": "success",
                        "data": f"Удалён созданный файл, восстановлена предыдущая версия: {path}"
                    }
                
                return {
                    "status": "success",
                    "data": f"Удалён созданный файл: {path}"
                }

            # -------------------------
            # 🔥 ОТКАТ ПАПКИ
            # -------------------------
            else:
                # Удаляем папку рекурсивно
                shutil.rmtree(target)
                logger.info(f"Deleted created directory: {path}")
                return {
                    "status": "success",
                    "data": f"Удалена созданная папка: {path}"
                }

        except Exception as e:
            logger.exception(f"Undo create failed: {path}")
            return {"status": "error", "error": f"Undo failed: {str(e)}"}