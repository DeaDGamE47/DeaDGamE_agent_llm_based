from utils.logger import setup_logger

logger = setup_logger("Context")


class ContextResolver:

    def __init__(self, memory):
        self.memory = memory

        # 🔥 алиасы папок
        self.folder_aliases = {
            "", "тут", "здесь", "эта папка", "в этой папке", "туда", "туда же"
        }

        # 🔥 алиасы файлов
        self.file_aliases = {
            "", "этот файл", "тот файл", "в тот файл", "сюда", "туда", "туда же"
        }

        # 🔥 команды продолжения (особый случай)
        self.continue_aliases = {
            "продолжи", "продолжай", "добавь", "добавь туда", "допиши"
        }

    def resolve(self, interpreted: dict) -> dict:

        entities = interpreted.get("entities", {})
        intent = interpreted.get("intent", "")

        logger.debug(f"RESOLVE INPUT: {entities}")

        # =========================================================
        # 🔥 CONTINUE INTENT (особая логика)
        # =========================================================

        if intent in self.continue_aliases:
            last_file = self.memory.get("last_file")

            if last_file:
                entities["file"] = {"name": last_file}
                logger.debug(f"CONTINUE → FILE FROM MEMORY: {last_file}")

        # =========================================================
        # 🔥 FOLDER
        # =========================================================

        folder = entities.get("folder")

        if isinstance(folder, dict):

            folder_name = (folder.get("name") or "").strip().lower()

            if folder_name in self.folder_aliases:

                last_folder = self.memory.get("last_folder")

                if last_folder:
                    entities["folder"] = {
                        "name": last_folder,
                        "is_path": True
                    }
                    logger.debug(f"FOLDER FROM MEMORY → {last_folder}")
                else:
                    logger.debug("No last_folder in memory")

        # =========================================================
        # 🔥 FILE
        # =========================================================

        file = entities.get("file")

        if isinstance(file, dict):

            file_name = (file.get("name") or "").strip().lower()

            if file_name in self.file_aliases:

                last_file = self.memory.get("last_file")

                if last_file:
                    entities["file"] = {"name": last_file}
                    logger.debug(f"FILE FROM MEMORY → {last_file}")
                else:
                    logger.debug("No last_file in memory")

        interpreted["entities"] = entities

        logger.debug(f"RESOLVED OUTPUT: {entities}")

        return interpreted