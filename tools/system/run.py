import os
import subprocess

from tools.base import BaseTool
from utils.logger import setup_logger

logger = setup_logger("Tool:run")


class RunTool(BaseTool):

    name = "run"
    description = "Запускает файл или программу"

    required_args = ["path"]
    optional_args = ["args"]

    category = "system"
    risk_level = "high"
    requires_confirmation = True

    def run(self, path: str, args: list = None):

        logger.info(f"RUN: {path} {args}")

        # -------------------------
        # 🔥 проверки
        # -------------------------
        if not path:
            return self.error("Не передан путь")

        if not os.path.exists(path):
            return self.error(f"Файл не существует: {path}")

        try:
            # -------------------------
            # 🔥 команда
            # -------------------------
            cmd = [path]

            if args:
                cmd.extend(args)

            # -------------------------
            # 🔥 запуск
            # -------------------------
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=True
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            logger.debug(f"STDOUT: {stdout}")
            logger.debug(f"STDERR: {stderr}")

            # -------------------------
            # 🔥 успешный запуск
            # -------------------------
            if result.returncode == 0:
                return self.success(
                    data={
                        "path": path,
                        "output": stdout
                    },
                    message=stdout or f"Выполнено: {path}",
                    meta={
                        "return_code": result.returncode
                    }
                )

            # -------------------------
            # 🔥 ошибка выполнения
            # -------------------------
            return self.error(stderr or "Ошибка выполнения")

        except Exception as e:
            logger.exception("run error")
            return self.error(str(e))