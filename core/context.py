from utils.logger import setup_logger

logger = setup_logger("Context")


class ContextResolver:

    def __init__(self, memory):
        self.memory = memory

    def resolve(self, interpreted: dict) -> dict:

        entities = interpreted.get("entities", {})
        memory_entities = self.memory.get("entities", {})
        history = self.memory.get("history", [])

        logger.debug(f"RESOLVE INPUT: {entities}")
        logger.debug(f"MEMORY ENTITIES: {memory_entities}")

        for key, value in list(entities.items()):

            if not isinstance(value, dict):
                continue

            # -------------------------
            # 🔥 REF: LAST
            # -------------------------
            if value.get("ref") == "last":

                if key in memory_entities:
                    entities[key] = memory_entities[key]
                    logger.debug(f"RESOLVED {key}.ref=last → {entities[key]}")
                    continue
                else:
                    logger.warning(f"No memory for {key}.ref=last")

            # -------------------------
            # 🔥 REF: LAST CREATED
            # -------------------------
            if value.get("ref") == "last_created":

                found = False

                for action in reversed(history):
                    result = action.get("result", {})
                    data = result.get("data", {})

                    if isinstance(data, dict) and key in data:
                        entities[key] = data[key]
                        logger.debug(f"RESOLVED {key}.ref=last_created → {entities[key]}")
                        found = True
                        break

                if not found:
                    logger.warning(f"No last_created found for {key}")

        interpreted["entities"] = entities

        logger.debug(f"RESOLVED OUTPUT: {entities}")

        return interpreted