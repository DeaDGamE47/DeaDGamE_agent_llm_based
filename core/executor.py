import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

from utils.logger import setup_logger

logger = setup_logger("Executor")


class ActionHistory:
    """
    SQLite-based история действий для undo функциональности.
    """
    
    def __init__(self, db_path: str = "data/action_history.db"):
        self.db_path = db_path
        self._ensure_db()
    
    def _ensure_db(self):
        """Создаёт таблицу если не существует."""
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
        """Записывает действие в историю."""
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
                True  # user_confirmed - пока всегда True
            ))
            conn.commit()
            
        logger.debug(f"Recorded action: {tool_name} ({action_type})")
    
    def get_last_action(self, session_id: str = "default") -> Optional[Dict]:
        """Получает последнее действие для undo."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM actions 
                WHERE session_id = ? AND result_status = 'success'
                ORDER BY id DESC LIMIT 1
            """, (session_id,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def get_recent_actions(self, limit: int = 10, session_id: str = "default") -> List[Dict]:
        """Получает последние N действий."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM actions 
                WHERE session_id = ?
                ORDER BY id DESC LIMIT ?
            """, (session_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]


class Executor:

    def __init__(self, tool_registry, enable_history: bool = True):
        self.tool_registry = tool_registry
        self.history = ActionHistory() if enable_history else None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Текущий план для возможного rollback
        self.current_plan: List[Dict] = []
        self.current_step_index: int = 0

    def execute(self, plan: List[Dict], selected_option: Optional[str] = None) -> Dict[str, Any]:
        """
        Выполняет план с записью в историю и поддержкой undo.
        
        Args:
            plan: Список шагов плана
            selected_option: Выбранный вариант (для multiple results)
            
        Returns:
            Результат выполнения
        """
        logger.info("EXECUTION START")
        
        self.current_plan = plan
        self.current_step_index = 0
        
        context: Dict[str, Any] = {}
        executed_steps: List[Dict] = []  # Для возможного rollback

        for i, step in enumerate(plan):
            self.current_step_index = i
            tool_name = step.get("tool")
            
            tool = self.tool_registry.get_tool(tool_name)
            if not tool:
                return {"status": "error", "error": f"Tool not found: {tool_name}"}

            # Резолв аргументов
            args = self._resolve_args(step.get("args", {}), context, selected_option)
            logger.debug(f"RUN TOOL: {tool_name} | ARGS: {args}")

            # Валидация
            validation_error = tool.validate(args)
            if validation_error:
                return validation_error

            # Подтверждение опасных действий
            if getattr(tool, "requires_confirmation", False):
                path = args.get("path", "")
                
                print(f"\n⚠️ Подтверждение действия")
                print(f"Tool: {tool.name}")
                print(f"Risk: {getattr(tool, 'risk_level', 'unknown')}")
                if path:
                    print(f"Path: {path}")
                
                confirm = input("Введите 'yes' для подтверждения: ").strip().lower()
                
                if confirm not in ["yes", "y", "да"]:
                    return {
                        "status": "cancelled",
                        "data": "Операция отменена пользователем"
                    }

            # Выполнение
            try:
                result = tool.run(**args)
            except Exception as e:
                logger.exception(f"TOOL ERROR: {tool_name}")
                
                # Rollback при ошибке (если были успешные шаги)
                if executed_steps:
                    self._rollback(executed_steps)
                    
                return {"status": "error", "error": str(e)}

            logger.debug(f"RESULT: {result}")

            # Обработка multiple results (need clarification)
            if result.get("status") == "multiple":
                return {
                    "status": "need_clarification",
                    "options": result.get("data", []),
                    "partial_context": context  # Сохраняем контекст для продолжения
                }

            # Обработка ошибки
            if result.get("status") != "success":
                # Rollback при ошибке
                if executed_steps:
                    self._rollback(executed_steps)
                return result

            # Запись в историю (для undo)
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
            
            executed_steps.append({
                "tool": tool_name,
                "args": args,
                "undo_data": undo_data,
                "result": result
            })

            # Сохранение в контекст
            if "output" in step:
                context[step["output"]] = result.get("data")

        logger.info("EXECUTION FINISHED")
        return {
            "status": "success",
            "data": context,
            "actions_count": len(executed_steps)
        }

    def undo_last(self) -> Dict[str, Any]:
        """
        Отменяет последнее успешное действие.
        
        Returns:
            Результат отката
        """
        if not self.history:
            return {"status": "error", "error": "History not enabled"}
        
        last_action = self.history.get_last_action(self.session_id)
        if not last_action:
            return {"status": "error", "error": "No actions to undo"}
        
        tool_name = last_action["tool_name"]
        undo_data_str = last_action["undo_data"]
        
        if not undo_data_str:
            return {"status": "error", "error": f"Action {tool_name} cannot be undone"}
        
        try:
            undo_data = json.loads(undo_data_str)
        except json.JSONDecodeError:
            return {"status": "error", "error": "Corrupted undo data"}
        
        # Выполняем откат через соответствующий tool
        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            return {"status": "error", "error": f"Tool {tool_name} not found for undo"}
        
        # Проверяем, поддерживает ли tool undo
        if not hasattr(tool, 'undo'):
            return {"status": "error", "error": f"Tool {tool_name} does not support undo"}
        
        try:
            result = tool.undo(**undo_data)
            logger.info(f"Undo executed for {tool_name}")
            return {
                "status": "success",
                "data": f"Отменено действие: {tool_name}",
                "undone_action": last_action
            }
        except Exception as e:
            logger.exception(f"Undo failed for {tool_name}")
            return {"status": "error", "error": f"Undo failed: {str(e)}"}

    def get_history(self, limit: int = 10) -> List[Dict]:
        """Возвращает историю действий."""
        if not self.history:
            return []
        return self.history.get_recent_actions(limit, self.session_id)

    def _resolve_args(self, args: Dict, context: Dict, selected_option: Optional[str]) -> Dict:
        """Резолвит аргументы из контекста."""
        resolved = {}

        for k, v in args.items():
            if v == "__SELECTED__":
                resolved[k] = selected_option
                continue
            
            if isinstance(v, str) and v in context:
                resolved[k] = context[v]
                continue
            
            resolved[k] = v

        return resolved

    def _rollback(self, executed_steps: List[Dict]):
        """
        Откатывает выполненные шаги при ошибке.
        Вызывается автоматически.
        """
        logger.warning(f"ROLLBACK: undoing {len(executed_steps)} steps")
        
        # Откатываем в обратном порядке
        for step in reversed(executed_steps):
            undo_data = step.get("undo_data")
            if not undo_data:
                continue
            
            tool = self.tool_registry.get_tool(step["tool"])
            if not tool or not hasattr(tool, 'undo'):
                continue
            
            try:
                tool.undo(**undo_data)
                logger.info(f"Rolled back: {step['tool']}")
            except Exception as e:
                logger.error(f"Rollback failed for {step['tool']}: {e}")
