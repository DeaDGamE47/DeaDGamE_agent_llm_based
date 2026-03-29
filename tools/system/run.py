import os
import subprocess

from tools.base import BaseTool
from utils.logger import setup_logger

logger = setup_logger("Tool:run")


class RunTool(BaseTool):

    name = "run"
    description = "Запускает файл или программу"
    required_args = ["path"]

    category = "system"
    risk_level = "high"
    requires_confirmation = True

    def run(self, path: str, args: list = None):
        logger.info(f"RUN: {path} {args}")

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
                "error": f"Файл не существует: {path}"
            }

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

            logger.debug(f"STDOUT: {result.stdout}")
            logger.debug(f"STDERR: {result.stderr}")

            # -------------------------
            # 🔥 успешный запуск
            # -------------------------
            if result.returncode == 0:
                return {
                    "status": "success",
                    "data": result.stdout.strip() or f"Выполнено: {path}"
                }

            # -------------------------
            # 🔥 ошибка выполнения
            # -------------------------
            return {
                "status": "error",
                "error": result.stderr.strip() or "Ошибка выполнения"
            }

        except Exception as e:
            logger.exception("run error")

            return {
                "status": "error",
                "error": str(e)
            }