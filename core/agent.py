from utils.logger import setup_logger

logger = setup_logger("Agent")


class Agent:

    def __init__(self, interpreter, planner, router, executor, memory, context):

        self.interpreter = interpreter
        self.planner = planner
        self.router = router
        self.executor = executor
        self.memory = memory
        self.context = context

        # Состояние для обработки clarification
        self.pending_options = None
        self.pending_plan = None

        # 🔥 ДОБАВИЛ
        self.pending_context = None
        self.pending_step = None

        logger.info("Agent initialized")

    # =========================================================

    def handle_input(self, user_input: str) -> dict:

        logger.info(f"USER INPUT: {user_input}")

        self.memory.save_message("user", user_input)

        if self.pending_options:
            return self._handle_selection(user_input)

        # -------------------------
        # INTERPRET
        # -------------------------
        thread_context = self.memory.get_thread_summary(limit=5)

        interpreted = self.interpreter.interpret(
            user_input,
            thread_context=thread_context
        )

        logger.debug(f"INTERPRETED: {interpreted}")

        # -------------------------
        # CONTEXT
        # -------------------------
        interpreted = self.context.resolve(interpreted)

        logger.debug(f"RESOLVED: {interpreted}")

        # -------------------------
        # PLAN
        # -------------------------
        plan = self.planner.build_plan(interpreted)

        if not plan:
            result = {"status": "error", "error": "План не построен"}
            self.memory.save_message("agent", result)
            return result

        logger.debug(f"PLAN: {plan}")

        # -------------------------
        # ROUTE
        # -------------------------
        plan = self.router.route(plan)

        # -------------------------
        # EXECUTE
        # -------------------------
        result = self._execute_plan(plan)

        return result

    # =========================================================

    def _handle_selection(self, user_input: str) -> dict:

        if user_input.isdigit():
            idx = int(user_input) - 1

            if 0 <= idx < len(self.pending_options):
                selected = self.pending_options[idx]

                logger.debug(f"OPTION SELECTED: {selected}")

                # 🔥 ВОТ ГЛАВНОЕ ИСПРАВЛЕНИЕ
                result = self.executor.continue_execution(
                    plan=self.pending_plan,
                    context=self.pending_context,
                    selected_option=selected,
                    start_step=self.pending_step
                )

                # сброс состояния
                self.pending_options = None
                self.pending_plan = None
                self.pending_context = None
                self.pending_step = None

                return self._process_execution_result(result)

            return {"status": "error", "error": "Неверный выбор"}

        return {"status": "error", "error": "Введите номер варианта"}

    # =========================================================

    def _execute_plan(self, plan: list) -> dict:

        result = self.executor.execute(plan)
        return self._process_execution_result(result)

    # =========================================================

    def _process_execution_result(self, result: dict) -> dict:

        # =====================================================
        # NEED CLARIFICATION
        # =====================================================
        if result.get("status") == "need_clarification":

            self.pending_options = result.get("options", [])

            # 🔥 ИСПРАВЛЕНО
            self.pending_plan = result.get("plan")
            self.pending_context = result.get("context")
            self.pending_step = result.get("next_step")

            logger.info(f"WAITING USER CHOICE: {self.pending_options}")

            return {
                "status": "need_clarification",
                "options": self.pending_options,
                "message": result.get("message", "Выбери вариант:")
            }

        # =====================================================
        # SUCCESS
        # =====================================================
        if result.get("status") == "success":

            # 🔥 ТВОЙ КОД (НЕ ТРОГАЛ)
            for step in result.get("executed_steps", []):
                data = step.get("result", {}).get("data")

                if isinstance(data, dict) and "path" in data:
                    path = data["path"]

                    if "." in path:
                        self.memory.state["last_file"] = path
                        self.memory.state["last_folder"] = path.rsplit("/", 1)[0].rsplit("\\", 1)[0]
                    else:
                        self.memory.state["last_folder"] = path

                    logger.debug(f"[MEMORY UPDATE] path={path}")

            # 🔥 история
            for step in result.get("executed_steps", []):
                self.memory.record_action(
                    tool_name=step["tool"],
                    args=step["args"],
                    result=step["result"]
                )

            self.memory.save_message("agent", result)

            logger.info("Execution successful")

            return result

        # =====================================================
        # ERROR / CANCEL
        # =====================================================
        self.memory.save_message("agent", result)

        if result.get("status") == "cancelled":
            logger.info("Action cancelled")
        else:
            logger.error(f"Execution error: {result.get('error')}")

        return result

    # =========================================================

    def undo(self) -> dict:

        if not self.memory.can_undo():
            return {"status": "error", "message": "Нет действий для отмены"}

        undo_result = self.memory.undo()

        if undo_result["status"] != "success":
            return undo_result

        action = undo_result["action"]

        self.memory.save_message("agent", {
            "status": "undo",
            "message": f"Отменено: {action['tool_name']}",
            "action": action
        })

        return {
            "status": "success",
            "message": f"✅ Отменено: {action['tool_name']}",
            "action": action
        }

    # =========================================================

    def redo(self) -> dict:

        if not self.memory.can_redo():
            return {"status": "error", "message": "Нет действий для повтора"}

        redo_result = self.memory.redo()

        if redo_result["status"] != "success":
            return redo_result

        action = redo_result["action"]

        self.memory.save_message("agent", {
            "status": "redo",
            "message": f"Повторено: {action['tool_name']}",
            "action": action
        })

        return {
            "status": "success",
            "message": f"✅ Повторено: {action['tool_name']}",
            "action": action
        }

    # =========================================================

    def get_status(self) -> dict:

        history_status = self.memory.get_history_status()

        return {
            "can_undo": history_status["can_undo"],
            "can_redo": history_status["can_redo"],
            "undo_count": history_status["undo_count"],
            "redo_count": history_status["redo_count"],
            "pending_selection": self.pending_options is not None,
            "entities": self.memory.get_entities()
        }