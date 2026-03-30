import os
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from tools.base import BaseTool
from utils.logger import setup_logger

logger = setup_logger("Tool:delete")


class DeleteTool(BaseTool):
    name = "delete"
    description = "Удаляет файл или папку с возможностью отката"
    required_args = ["path"]

    category = "file"
    risk_level = "high"
    requires_confirmation = True

    def __init__(self):
        # Директория для бэкапов удалённых файлов
        self.backup_dir = Path(tempfile.gettempdir()) / "agent_undo" / "deleted"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"DeleteTool backup dir: {self.backup_dir}")

    def run(self, path: str):
        logger.info(f"DELETE: {path}")

        # -------------------------
        # 🔥 проверки
        # -------------------------
        if not path:
            return {
                "status": "error",
                "error": "Не передан путь"
            }

        if not os.path.exists(path):
            return {
                "status": "error",
                "error": f"Путь не существует: {path}"
            }

        # -------------------------
        # 🔥 бэкап перед удалением
        # -------------------------
        backup_info = self._create_backup(path)
        if not backup_info:
            return {
                "status": "error",
                "error": "Не удалось создать бэкап для undo"
            }

        try:
            # -------------------------
            # 🔥 файл
            # -------------------------
            if os.path.isfile(path):
                os.remove(path)

                return {
                    "status": "success",
                    "data": path,
                    "undo_data": backup_info  # 🔥 для отката
                }

            # -------------------------
            # 🔥 папка
            # -------------------------
            elif os.path.isdir(path):
                shutil.rmtree(path)

                return {
                    "status": "success",
                    "data": path,
                    "undo_data": backup_info  # 🔥 для отката
                }

            else:
                # Откатываем бэкап при неизвестном типе
                self._cleanup_backup(backup_info)
                return {
                    "status": "error",
                    "error": "Неизвестный тип объекта"
                }

        except Exception as e:
            logger.exception("delete error")
            # При ошибке пытаемся восстановить из бэкапа
            self._cleanup_backup(backup_info)
            return {
                "status": "error",
                "error": str(e)
            }

    def undo(self, backup_path: str, original_path: str, is_directory: bool = False):
        """
        Восстанавливает удалённый файл/папку из бэкапа.
        Вызывается Executor при откате.
        """
        logger.info(f"UNDO DELETE: restoring {original_path} from {backup_path}")

        try:
            backup = Path(backup_path)
            original = Path(original_path)

            if not backup.exists():
                return {
                    "status": "error",
                    "error": f"Бэкап не найден: {backup_path}"
                }

            # Если целевой путь уже существует (кем-то создан заново)
            if original.exists():
                # Добавляем суффикс с timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                original = original.parent / f"{original.name}_restored_{timestamp}"

            # Восстановление
            if is_directory:
                shutil.copytree(backup, original)
            else:
                shutil.copy2(backup, original)

            # Удаляем бэкап после успешного восстановления
            self._cleanup_backup({"backup_path": backup_path, "is_directory": is_directory})

            logger.info(f"Restored: {original}")
            return {
                "status": "success",
                "data": str(original)
            }

        except Exception as e:
            logger.exception("undo delete error")
            return {
                "status": "error",
                "error": f"Не удалось восстановить: {str(e)}"
            }

    def _create_backup(self, path: str) -> dict:
        """
        Создаёт бэкап файла/папки перед удалением.
        Возвращает метаданные для undo.
        """
        try:
            source = Path(path)
            is_directory = source.is_dir()

            # Уникальное имя для бэкапа
            backup_name = f"{uuid.uuid4().hex[:8]}_{source.name}"
            backup_path = self.backup_dir / backup_name

            if is_directory:
                # Копируем папку рекурсивно
                shutil.copytree(source, backup_path)
                logger.debug(f"Created directory backup: {backup_path}")
            else:
                # Копируем файл
                shutil.copy2(source, backup_path)
                logger.debug(f"Created file backup: {backup_path}")

            return {
                "backup_path": str(backup_path),
                "original_path": str(source.absolute()),
                "is_directory": is_directory,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.exception("backup creation failed")
            return None

    def _cleanup_backup(self, backup_info: dict):
        """
        Удаляет бэкап (при ошибке или после успешного undo).
        """
        try:
            backup_path = backup_info.get("backup_path")
            if backup_path and os.path.exists(backup_path):
                if os.path.isdir(backup_path):
                    shutil.rmtree(backup_path)
                else:
                    os.remove(backup_path)
                logger.debug(f"Cleaned up backup: {backup_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup backup: {e}")

    def list_backups(self) -> list:
        """
        Возвращает список доступных бэкапов (для отладки).
        """
        try:
            backups = []
            for item in self.backup_dir.iterdir():
                stat = item.stat()
                backups.append({
                    "name": item.name,
                    "path": str(item),
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
            return backups
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []
