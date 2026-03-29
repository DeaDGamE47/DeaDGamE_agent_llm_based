from utils.logger import setup_logger

logger = setup_logger("Memory")


class Memory:

    def __init__(self):
        self.state = {
            "entities": {}
        }

    def get(self, key, default=None):
        return self.state.get(key, default)

    def update_entities(self, entities):
        for k, v in entities.items():
            if isinstance(v, dict) and v.get("name"):
                self.state["entities"][k] = v