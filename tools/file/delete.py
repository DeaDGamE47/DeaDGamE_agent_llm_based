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
        self.backup_dir = Path(tempfile.gettempdir()) / "agent_undo" / "deleted"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"DeleteTool backup dir: {self.backup_dir}")

    def run(self, path: str):
        logger.info(f"DELETE: {path}")

        if not path:
            return self.error("Не передан путь")

        if not os.path.exists(path):
            return self.error(f"Путь не существует: {path}")

        backup_info = self._create_backup(path)
        if not backup_info:
            return self.error("Не удалось создать бэкап для undo")

        try:
            if os.path.isfile(path):
                os.remove(path)

                return self.success(
                    data={"path": path, "type": "file"},
                    message=f"Удалён файл: {path}",
                    undo_data=backup_info
                )

            elif os.path.isdir(path):
                shutil.rmtree(path)

                return self.success(
                    data={"path": path, "type": "directory"},
                    message=f"Удалена папка: {path}",
                    undo_data=backup_info
                )

            else:
                self._cleanup_backup(backup_info)
                return self.error("Неизвестный тип объекта")

        except Exception as e:
            logger.exception("delete error")
            self._cleanup_backup(backup_info)
            return self.error(str(e))

    def undo(self, backup_path: str, original_path: str, is_directory: bool = False):
        logger.info(f"UNDO DELETE: restoring {original_path} from {backup_path}")

        try:
            backup = Path(backup_path)
            original = Path(original_path)

            if not backup.exists():
                return self.error(f"Бэкап не найден: {backup_path}")

            if original.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                original = original.parent / f"{original.name}_restored_{timestamp}"

            if is_directory:
                shutil.copytree(backup, original)
            else:
                shutil.copy2(backup, original)

            self._cleanup_backup({
                "backup_path": backup_path,
                "is_directory": is_directory
            })

            return self.success(
                data={"path": str(original)},
                message=f"Восстановлено: {original}"
            )

        except Exception as e:
            logger.exception("undo delete error")
            return self.error(f"Не удалось восстановить: {str(e)}")