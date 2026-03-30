from utils.logger import setup_logger


logger = setup_logger("Context")


class ContextResolver:

    def __init__(self, memory):
        self.memory = memory

    def resolve(self, interpreted: dict) -> dict:

        entities = interpreted.get("entities", {})

        logger.debug(f"RESOLVE INPUT: {entities}")

        for key, value in list(entities.items()):

            if not isinstance(value, dict):
                continue

            # =========================================================
            # 🔥 AUTO CONTEXT FROM MEMORY
            # =========================================================

            # folder
            if key == "folder" and not value.get("name"):
                last_folder = self.memory.get("last_folder")

                if last_folder:
                    entities[key] = {"name": last_folder}
                    logger.debug(f"FOLDER FROM MEMORY → {last_folder}")
                else:
                    logger.debug("No last_folder in memory")

            # file
            if key == "file" and not value.get("name"):
                last_file = self.memory.get("last_file")

                if last_file:
                    entities[key] = {"name": last_file}
                    logger.debug(f"FILE FROM MEMORY → {last_file}")
                else:
                    logger.debug("No last_file in memory")

        interpreted["entities"] = entities

        logger.debug(f"RESOLVED OUTPUT: {entities}")

        return interpreted