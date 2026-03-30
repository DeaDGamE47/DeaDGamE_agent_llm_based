import os
import subprocess
import platform

from tools.base import BaseTool
from utils.logger import setup_logger

logger = setup_logger("Tool:open")


class OpenTool(BaseTool):
    """
    Открывает файл или папку в системе.
    """

    name = "open"
    description = "Открывает файл или папку"

    required_args = ["path"]
    optional_args = []

    category = "file"
    risk_level = "low"

    def run(self, path):
        """
        Args:
            path: Путь к файлу/папке (строка или dict с ключом 'path')
        """
        # 🔥 FIX: Если пришел dict, извлекаем path
        if isinstance(path, dict):
            path = path.get("path")
            if not path:
                return self.error("В path dict отсутствует ключ 'path'")
        
        # 🔥 FIX: Если пришел None
        if not path:
            return self.error("Путь не указан")

        logger.info(f"OPEN: {path}")

        if not os.path.exists(path):
            return self.error(f"Не существует: {path}")

        try:
            system = platform.system()
            
            if system == "Windows":
                os.startfile(path)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", path], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", path], check=True)
            
            logger.info(f"OPENED: {path}")
            return self.success(
                data={"path": path},
                message=f"Открыто: {path}"
            )

        except Exception as e:
            logger.error(f"OPEN FAILED: {e}")
            return self.error(f"Не удалось открыть: {str(e)}")