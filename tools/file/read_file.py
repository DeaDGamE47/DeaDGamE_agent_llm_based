import os
from tools.base import BaseTool
from utils.logger import setup_logger

logger = setup_logger("Tool:read_file")


class ReadFileTool(BaseTool):

    name = "read_file"
    description = "Читает содержимое файла (указанного или из контекста)"
    required_args = []  # 🔥 path теперь не обязательный
    optional_args = ["path"]  # 🔥 можно не указывать (используется последний файл)

    category = "file"
    risk_level = "low"

    def run(self, path: str = None):
        logger.info(f"READ FILE: {path}")

        # -------------------------
        # 🔥 если путь не указан — ошибка (нет дефолта как у list)
        # -------------------------
        if not path:
            return {
                "status": "error",
                "error": "Не указан путь к файлу. Используйте: прочти файл [путь] или сначала откройте файл"
            }

        # -------------------------
        # 🔥 проверки
        # -------------------------
        if not os.path.exists(path):
            return {
                "status": "error",
                "error": f"Файл не найден: {path}"
            }

        if not os.path.isfile(path):
            return {
                "status": "error",
                "error": f"Это не файл: {path}"
            }

        try:
            # -------------------------
            # 🔥 чтение файла
            # -------------------------
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            # Определяем размер для метаданных
            size = os.path.getsize(path)
            lines_count = len(content.splitlines())

            logger.info(f"Read file: {path} ({size} bytes, {lines_count} lines)")

            return {
                "status": "success",
                "data": {
                    "path": path,
                    "type": "file",
                    "content": content,
                    "size_bytes": size,
                    "lines_count": lines_count,
                    "message": f"Содержимое файла {path}:\n\n{content[:500]}{'...' if len(content) > 500 else ''}"
                }
            }

        except UnicodeDecodeError:
            # Пробуем другую кодировку
            try:
                with open(path, "r", encoding="cp1251") as f:
                    content = f.read()
                
                size = os.path.getsize(path)
                lines_count = len(content.splitlines())

                return {
                    "status": "success",
                    "data": {
                        "path": path,
                        "type": "file",
                        "content": content,
                        "size_bytes": size,
                        "lines_count": lines_count,
                        "message": f"Содержимое файла {path} (кодировка cp1251):\n\n{content[:500]}{'...' if len(content) > 500 else ''}"
                    }
                }
            except Exception as e:
                return {
                    "status": "error",
                    "error": f"Не удалось прочитать файл (неподдерживаемая кодировка): {str(e)}"
                }

        except Exception as e:
            logger.exception("read_file error")

            return {
                "status": "error",
                "error": str(e)
            }