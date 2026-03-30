import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from utils.logger import setup_logger

logger = setup_logger("MemoryManager")


@dataclass
class Action:
    """Запись о выполненном действии для undo/redo"""
    id: str
    timestamp: str
    tool_name: str
    args: Dict[str, Any]
    result: Dict[str, Any]
    undo_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Action":
        return cls(**data)


class MemoryManager:
    """
    Центральный менеджер памяти агента.
    Управляет: runtime state, threads, action history (undo/redo), profile, RAG
    """

    def __init__(self, base_path: str = "memory"):
        self.base_path = base_path

        # -------------------------
        # 🔥 PATHS
        # -------------------------
        self.threads_path = os.path.join(base_path, "threads")
        self.profile_path = os.path.join(base_path, "profile")
        self.rag_path = os.path.join(base_path, "rag")
        self.learning_path = os.path.join(base_path, "learning")
        self.history_path = os.path.join(base_path, "history")

        self._ensure_dirs()

        # -------------------------
        # 🔥 RUNTIME MEMORY (не сохраняется между сессиями)
        # -------------------------
        self.state = {
            "entities": {},
            "last_file": None,
            "last_folder": None
        }

        # -------------------------
        # 🔥 ACTION HISTORY (undo/redo стек)
        # -------------------------
        self.undo_stack: List[Action] = []
        self.redo_stack: List[Action] = []
        self.max_history = 50  # Лимит действий в истории

        # Загружаем предыдущую историю если есть
        self._load_history()

        # -------------------------
        # 🔥 THREAD (текущая сессия)
        # -------------------------
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.thread_file = os.path.join(
            self.threads_path, f"thread_{self.session_id}.json"
        )
        self._init_thread()

        logger.info(f"MemoryManager initialized: {base_path}")

    # =========================================================
    # INIT
    # =========================================================

    def _ensure_dirs(self):
        """Создаёт все необходимые директории"""
        for path in [self.threads_path, self.profile_path, self.rag_path, 
                     self.learning_path, self.history_path]:
            os.makedirs(path, exist_ok=True)

    def _init_thread(self):
        """Инициализирует файл текущего диалога"""
        if not os.path.exists(self.thread_file):
            with open(self.thread_file, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    # =========================================================
    # ACTION HISTORY (UNDO/REDO)
    # =========================================================

    def record_action(self, tool_name: str, args: Dict[str, Any], 
                     result: Dict[str, Any]) -> Optional[Action]:
        """
        Записывает действие в историю для возможного undo.
        Вызывается Agent после успешного выполнения.

        Returns:
            Action объект если записано, None если действие не undoable
        """
        # Проверяем есть ли undo_data в результате
        undo_data = result.get("undo_data")
        if not undo_data:
            logger.debug(f"Action {tool_name} has no undo_data, skipping history")
            return None

        # Очищаем redo стек при новом действии
        if self.redo_stack:
            self.redo_stack.clear()
            logger.debug("Redo stack cleared due to new action")

        action = Action(
            id=f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
            timestamp=datetime.now().isoformat(),
            tool_name=tool_name,
            args=args,
            result=result,
            undo_data=undo_data
        )

        self.undo_stack.append(action)

        # Лимитируем размер стека
        if len(self.undo_stack) > self.max_history:
            removed = self.undo_stack.pop(0)
            logger.debug(f"Removed oldest action from history: {removed.id}")

        self._save_history()
        logger.info(f"Action recorded: {tool_name} (undo_stack: {len(self.undo_stack)})")

        return action

    def can_undo(self) -> bool:
        """Проверяет есть ли что отменять"""
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        """Проверяет есть ли что повторить"""
        return len(self.redo_stack) > 0

    def undo(self) -> Dict[str, Any]:
        """
        Отменяет последнее действие.

        Returns:
            {"status": "success", "action": Action} или {"status": "error", "message": str}
        """
        if not self.can_undo():
            return {"status": "error", "message": "Нет действий для отмены"}

        action = self.undo_stack.pop()
        self.redo_stack.append(action)

        self._save_history()

        logger.info(f"Undo: {action.tool_name} (redo_stack: {len(self.redo_stack)})")

        return {
            "status": "success", 
            "action": action.to_dict(),
            "message": f"Отменено: {action.tool_name}"
        }

    def redo(self) -> Dict[str, Any]:
        """
        Повторяет отменённое действие.

        Returns:
            {"status": "success", "action": Action} или {"status": "error", "message": str}
        """
        if not self.can_redo():
            return {"status": "error", "message": "Нет действий для повтора"}

        action = self.redo_stack.pop()
        self.undo_stack.append(action)

        self._save_history()

        logger.info(f"Redo: {action.tool_name} (undo_stack: {len(self.undo_stack)})")

        return {
            "status": "success",
            "action": action.to_dict(),
            "message": f"Повторено: {action.tool_name}"
        }

    def get_history_status(self) -> Dict[str, Any]:
        """Возвращает статус истории для UI"""
        return {
            "can_undo": self.can_undo(),
            "can_redo": self.can_redo(),
            "undo_count": len(self.undo_stack),
            "redo_count": len(self.redo_stack),
            "last_actions": [a.to_dict() for a in self.undo_stack[-5:]]
        }

    def _save_history(self):
        """Сохраняет undo/redo стеки на диск"""
        try:
            history_file = os.path.join(self.history_path, "action_history.json")
            data = {
                "undo_stack": [a.to_dict() for a in self.undo_stack],
                "redo_stack": [a.to_dict() for a in self.redo_stack],
                "saved_at": datetime.now().isoformat()
            }
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save history: {e}")

    def _load_history(self):
        """Загружает undo/redo стеки с диска"""
        try:
            history_file = os.path.join(self.history_path, "action_history.json")
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.undo_stack = [Action.from_dict(a) for a in data.get("undo_stack", [])]
                    self.redo_stack = [Action.from_dict(a) for a in data.get("redo_stack", [])]
                logger.info(f"History loaded: {len(self.undo_stack)} undo, {len(self.redo_stack)} redo")
        except Exception as e:
            logger.warning(f"Failed to load history: {e}")
            self.undo_stack = []
            self.redo_stack = []

    def clear_history(self):
        """Очищает всю историю действий"""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._save_history()
        logger.info("History cleared")

    # =========================================================
    # RUNTIME MEMORY (Entities)
    # =========================================================

    def get(self, key, default=None):
        """Получает значение из runtime state"""
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

    def get_entities(self) -> Dict[str, Any]:
        """Возвращает все текущие entities"""
        return self.state["entities"].copy()

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

            # File locking через временный файл для безопасности
            temp_file = self.thread_file + ".tmp"

            # Читаем текущие данные
            data = []
            if os.path.exists(self.thread_file):
                with open(self.thread_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

            data.append(message)

            # Пишем во временный файл, затем атомарно переименовываем
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            os.replace(temp_file, self.thread_file)

            logger.debug(f"Message saved ({role})")

        except Exception as e:
            logger.warning(f"Thread save failed: {e}")

    def get_thread(self) -> list:
        try:
            with open(self.thread_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    def get_thread_summary(self, limit: int = 10) -> str:
        """Возвращает краткое summary треда для контекста"""
        thread = self.get_thread()
        if not thread:
            return ""

        recent = thread[-limit:]
        summary = []
        for msg in recent:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, dict):
                content = content.get("message", str(content)[:100])
            summary.append(f"{role}: {str(content)[:100]}")

        return "\n".join(summary)

    # =========================================================
    # LEARNING (сохранение действий для анализа)
    # =========================================================

    def save_action_for_learning(self, action: Dict[str, Any]):
        """
        Сохраняет действия для ML/обучения (отдельно от undo history)
        """
        try:
            actions_file = os.path.join(self.learning_path, "actions.json")

            if not os.path.exists(actions_file):
                with open(actions_file, "w", encoding="utf-8") as f:
                    json.dump([], f)

            with open(actions_file, "r+", encoding="utf-8") as f:
                data = json.load(f)
                action["saved_at"] = datetime.now().isoformat()
                data.append(action)

                f.seek(0)
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.debug("Action saved to learning dataset")

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
        """Возвращает полное состояние памяти для отладки"""
        return {
            "runtime_state": self.state,
            "history_status": self.get_history_status(),
            "thread_file": self.thread_file,
            "session_id": self.session_id
        }
