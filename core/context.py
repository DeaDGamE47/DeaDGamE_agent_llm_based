from utils.logger import setup_logger

logger = setup_logger("Context")


class ContextResolver:

    def __init__(self, memory):
        self.memory = memory

    def resolve(self, interpreted):
        entities = interpreted.get("entities", {})
        mem = self.memory.get("entities", {})

        for k, v in list(entities.items()):
            if isinstance(v, dict) and v.get("ref") == "last":
                if k in mem:
                    entities[k] = mem[k]

        interpreted["entities"] = entities
        return interpreted