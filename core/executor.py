import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from utils.logger import setup_logger

logger = setup_logger("Executor")


# =========================================================
# ACTION HISTORY (DB)
# =========================================================

class ActionHistory:

    def __init__(self, db_path: str = "data/action_history.db"):
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    session_id TEXT,
                    action_type TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    args TEXT,
                    result_status TEXT,
                    undo_data TEXT,
                    user_confirmed BOOLEAN
                )
            """)
            conn.commit()

    def record(self, action_type: str, tool_name: str, args: Dict,
               result_status: str, undo_data: Optional[Dict] = None,
               session_id: str = "default"):

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO actions (timestamp, session_id, action_type, tool_name, 
                                   args, result_status, undo_data, user_confirmed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                session_id,
                action_type,
                tool_name,
                json.dumps(args),
                result_status,
                json.dumps(undo_data) if undo_data else None,
                True
            ))
            conn.commit()

        logger.debug(f"Recorded action: {tool_name} ({action_type})")

    def get_last_action(self, session_id: str = "default") -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM actions 
                WHERE session_id = ? AND result_status = 'success'
                ORDER BY id DESC LIMIT 1
            """, (session_id,))
            row = cursor.fetchone()
            return dict(row) if row else None


# =========================================================
# EXECUTOR
# =========================================================

class Executor:

    def __init__(self, tool_registry, memory_manager=None, enable_history: bool = True):
        self.tool_registry = tool_registry
        self.memory_manager = memory_manager
        self.history = ActionHistory() if enable_history else None

        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def execute(self, plan: List[Dict], selected_option: Optional[str] = None) -> Dict[str, Any]:

        logger.info("EXECUTION START")

        context: Dict[str, Any] = {}
        executed_steps: List[Dict] = []

        for i, step in enumerate(plan):

            tool_name = step.get("tool")
            tool = self.tool_registry.get_tool(tool_name)

            if not tool:
                return {"status": "error", "error": f"Tool not found: {tool_name}"}

            args = self._resolve_args(step.get("args", {}), context, selected_option)

            logger.info(f"STEP {i+1}: {tool_name}")
            logger.debug(f"ARGS: {args}")

            validation_error = tool.validate(args)
            if validation_error:
                return validation_error

            # CONFIRMATION
            if getattr(tool, "requires_confirmation", False):
                confirm = input("Введите 'yes' для подтверждения: ").strip().lower()
                if confirm not in ["yes", "y", "да"]:
                    return {"status": "cancelled"}

            # RUN
            try:
                result = tool.run(**args)
            except Exception as e:
                logger.exception("TOOL CRASH")
                self._rollback(executed_steps)
                return {"status": "error", "error": str(e)}

            status = result.get("status")

            if status == "need_clarification":
                return {
                    "status": "need_clarification",
                    "options": result.get("options", []),
                    "message": result.get("message"),
                    "partial_context": context
                }

            if status != "success":
                self._rollback(executed_steps)
                return result

            # -------------------------
            # SUCCESS
            # -------------------------

            undo_data = result.get("undo_data")

            if self.history:
                self.history.record(
                    action_type=step.get("output", "action"),
                    tool_name=tool_name,
                    args=args,
                    result_status="success",
                    undo_data=undo_data,
                    session_id=self.session_id
                )

            # 🔥 MEMORY SAVE (лог действий)
            if self.memory_manager:
                try:
                    action = {
                        "tool": tool_name,
                        "args": args,
                        "result": result.get("data"),
                        "timestamp": datetime.now().isoformat()
                    }

                    self.memory_manager.save_action(action)

                    # 🔥 ВАЖНО: обновляем runtime state
                    self._update_memory_from_result(result)

                except Exception as e:
                    logger.warning(f"Memory save failed: {e}")

            executed_steps.append({
                "tool": tool_name,
                "args": args,
                "undo_data": undo_data
            })

            if "output" in step:
                context[step["output"]] = result.get("data")

            context["__last__"] = result.get("data")

        logger.info("EXECUTION FINISHED")

        return {
            "status": "success",
            "data": context
        }

    # =========================================================
    # MEMORY UPDATE (ЕДИНАЯ ТОЧКА)
    # =========================================================

    def _update_memory_from_result(self, result):

        if not self.memory_manager:
            return

        data = result.get("data")

        if not data:
            return

        path = None

        if isinstance(data, dict):
            path = data.get("path") or data.get("file_path") or data.get("folder_path")

        elif isinstance(data, str):
            path = data

        if not path:
            return

        ext = path.split('.')[-1].lower() if '.' in path else ""

        if ext in ['txt', 'py', 'json', 'md', 'docx', 'pdf']:
            self.memory_manager.state["last_file"] = path

            folder = path.rsplit('/', 1)[0].rsplit('\\', 1)[0]
            self.memory_manager.state["last_folder"] = folder

            logger.debug(f"[MEMORY] file={path}, folder={folder}")

        else:
            self.memory_manager.state["last_folder"] = path.rstrip('/\\')
            logger.debug(f"[MEMORY] folder={path}")

    # =========================================================

    def _resolve_args(self, args, context, selected_option):
        resolved = {}

        for k, v in args.items():
            if v == "__SELECTED__":
                resolved[k] = selected_option
            elif isinstance(v, str) and v in context:
                resolved[k] = context[v]
            else:
                resolved[k] = v

        return resolved

    def _rollback(self, executed_steps):
        logger.warning("ROLLBACK")

        for step in reversed(executed_steps):
            tool = self.tool_registry.get_tool(step["tool"])
            if hasattr(tool, "undo"):
                try:
                    tool.undo(**step["undo_data"])
                except:
                    pass