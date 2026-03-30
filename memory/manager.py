import os
import json
from datetime import datetime
from typing import Dict, Any, Optional

from utils.logger import setup_logger

logger = setup_logger("MemoryManager")


class MemoryManager:

    def __init__(self, base_path: str = "memory"):

        self.base_path = base_path

        # -------------------------
        # 🔥 PATHS
        # -------------------------
        self.threads_path = os.path.join(base_path, "threads")
        self.profile_path = os.path.join(base_path, "profile")
        self.rag_path = os.path.join(base_path, "rag")
        self.learning_path = os.path.join(base_path, "learning")

        self._ensure_dirs()

        # -------------------------
        # 🔥 RUNTIME MEMORY
        # -------------------------
        self.state = {
            "entities": {},
            "last_file": None,
            "last_folder": None
        }

        # текущая сессия
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.thread_file = os.path.join(
            self.threads_path, f"thread_{self.session_id}.json"
        )

        # создаём файл треда
        self._init_thread()

    # =========================================================
    # INIT
    # =========================================================

    def _ensure_dirs(self):
        os.makedirs(self.threads_path, exist_ok=True)
        os.makedirs(self.profile_path, exist_ok=True)
        os.makedirs(self.rag_path, exist_ok=True)
        os.makedirs(self.learning_path, exist_ok=True)

    def _init_thread(self):
        if not os.path.exists(self.thread_file):
            with open(self.thread_file, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    # =========================================================
    # RUNTIME MEMORY
    # =========================================================

    def get(self, key, default=None):
        return self.state.get(key, default)

    def update_entities(self, entities: Dict[str, Any]):
        """
        Обновляет entities + last_file/last_folder
        """

        for k, v in entities.items():
            if not isinstance(v, dict):
                continue

            if v.get("name"):
                self.state["entities"][k] = v

                # 🔥 обновление last_file / last_folder
                if k == "file":
                    self.state["last_file"] = v["name"]
                    logger.debug(f"last_file updated: {v['name']}")

                if k == "folder":
                    self.state["last_folder"] = v["name"]
                    logger.debug(f"last_folder updated: {v['name']}")

    def get_last_file(self) -> Optional[str]:
        return self.state.get("last_file")

    def get_last_folder(self) -> Optional[str]:
        return self.state.get("last_folder")

    # =========================================================
    # THREADS (диалоги)
    # =========================================================

    def save_message(self, role: str, content: Any):
        """
        role: user | agent | system
        """

        try:
            message = {
                "timestamp": datetime.now().isoformat(),
                "role": role,
                "content": content
            }

            with open(self.thread_file, "r+", encoding="utf-8") as f:
                data = json.load(f)
                data.append(message)

                f.seek(0)
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug(f"Message saved ({role})")

        except Exception as e:
            logger.warning(f"Thread save failed: {e}")

    def get_thread(self) -> list:
        try:
            with open(self.thread_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    # =========================================================
    # ACTIONS (с Executor)
    # =========================================================

    def save_action(self, action: Dict[str, Any]):
        """
        Сохраняет действия (для обучения / анализа)
        """

        try:
            actions_file = os.path.join(self.base_path, "learning", "actions.json")

            if not os.path.exists(actions_file):
                with open(actions_file, "w", encoding="utf-8") as f:
                    json.dump([], f)

            with open(actions_file, "r+", encoding="utf-8") as f:
                data = json.load(f)
                data.append(action)

                f.seek(0)
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug("Action saved to memory")

        except Exception as e:
            logger.warning(f"Action save failed: {e}")

    # =========================================================
    # SIMPLE SEARCH (будущий RAG)
    # =========================================================

    def search_in_threads(self, query: str, limit: int = 5) -> list:
        """
        Простой поиск по диалогам (без embeddings)
        """

        results = []
        query = query.lower()

        try:
            for file in os.listdir(self.threads_path):
                full_path = os.path.join(self.threads_path, file)

                with open(full_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                    for msg in data:
                        text = str(msg.get("content", "")).lower()

                        if query in text:
                            results.append(msg)

                            if len(results) >= limit:
                                return results

        except Exception as e:
            logger.warning(f"Search failed: {e}")

        return results

    # =========================================================
    # DEBUG / EXPORT
    # =========================================================

    def dump_state(self) -> Dict[str, Any]:
        return self.state