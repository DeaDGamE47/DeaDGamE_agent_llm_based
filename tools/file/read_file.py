import os
from tools.base import BaseTool
from utils.logger import setup_logger

logger = setup_logger("Tool:read_file")


class ReadFileTool(BaseTool):

    name = "read_file"
    description = "Читает содержимое файла (указанного или из контекста)"

    required_args = []
    optional_args = ["path"]

    category = "file"
    risk_level = "low"

    def run(self, path: str = None):

        logger.info(f"READ FILE: {path}")

        if not path:
            return self.error(
                "Не указан путь к файлу. Используйте: прочти файл [путь] или сначала откройте файл"
            )

        if not os.path.exists(path):
            return self.error(f"Файл не найден: {path}")

        if not os.path.isfile(path):
            return self.error(f"Это не файл: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            return self._success_response(path, content, encoding="utf-8")

        except UnicodeDecodeError:
            try:
                with open(path, "r", encoding="cp1251") as f:
                    content = f.read()

                return self._success_response(path, content, encoding="cp1251")

            except Exception as e:
                return self.error(
                    f"Не удалось прочитать файл (неподдерживаемая кодировка): {str(e)}"
                )

        except Exception as e:
            logger.exception("read_file error")
            return self.error(str(e))

    def _success_response(self, path, content, encoding):

        size = os.path.getsize(path)
        lines_count = len(content.splitlines())

        preview = content[:500] + ("..." if len(content) > 500 else "")

        return self.success(
            data={
                "path": path,
                "type": "file",
                "content": content,
                "size_bytes": size,
                "lines_count": lines_count,
                "encoding": encoding
            },
            message=f"Содержимое файла {path}:\n\n{preview}"
        )