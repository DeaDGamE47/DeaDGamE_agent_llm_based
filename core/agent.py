from utils.logger import setup_logger

logger = setup_logger("Agent")


class Agent:
    """
    Центральный контроллер агента.

    Управляет полным pipeline:
    input → interpret → context resolve → plan → route → execute → memory record

    Также управляет undo/redo через MemoryManager.
    """

    def __init__(self, interpreter, planner, router, executor, memory, context):
        """
        Args:
            interpreter: Interpreter — извлекает intent/entities
            planner: Planner — строит план
            router: Router — выбирает модель
            executor: Executor — тупой исполнитель
            memory: MemoryManager — память (state, threads, action history)
            context: ContextResolver — разрешение контекста
        """
        self.interpreter = interpreter
        self.planner = planner
        self.router = router
        self.executor = executor
        self.memory = memory
        self.context = context

        # Состояние для обработки clarification
        self.pending_options = None
        self.pending_plan = None

        logger.info("Agent initialized")

    # =========================================================
    # MAIN INPUT HANDLER
    # =========================================================

    def handle_input(self, user_input: str) -> dict:
        """
        Основной обработчик пользовательского ввода.

        Args:
            user_input: Текст от пользователя

        Returns:
            dict с результатом выполнения
        """
        logger.info(f"USER INPUT: {user_input}")

        # 🔥 Сохраняем сообщение пользователя
        self.memory.save_message("user", user_input)

        # =====================================================
        # ОБРАБОТКА ВЫБОРА (multiple results)
        # =====================================================
        if self.pending_options:
            return self._handle_selection(user_input)

        # =====================================================
        # PIPELINE: Interpret → Context → Plan → Route → Execute
        # =====================================================

        # 🔥 INTERPRET
        thread_context = self.memory.get_thread_summary(limit=5)
        interpreted = self.interpreter.interpret(
            user_input,
            thread_context=thread_context
        )
        logger.debug(f"INTERPRETED: {interpreted}")

        # 🔥 CONTEXT RESOLVE ("эта папка" → last_folder)
        interpreted = self.context.resolve(interpreted)
        logger.debug(f"RESOLVED: {interpreted}")

        # 🔥 Сохраняем entities в память
        self.memory.update_entities(interpreted.get("entities", {}))

        # 🔥 PLAN
        plan = self.planner.build_plan(interpreted)
        if not plan:
            logger.warning("Plan not built")
            result = {"status": "error", "error": "План не построен"}
            self.memory.save_message("agent", result)
            return result

        logger.debug(f"PLAN: {plan}")

        # 🔥 ROUTE (выбор модели)
        plan = self.router.route(plan)

        # 🔥 EXECUTE
        result = self._execute_plan(plan)

        return result

    def _handle_selection(self, user_input: str) -> dict:
        """
        Обрабатывает выбор пользователя при need_clarification.
        """
        if user_input.isdigit():
            idx = int(user_input) - 1

            if 0 <= idx < len(self.pending_options):
                selected = self.pending_options[idx]
                logger.debug(f"OPTION SELECTED: {selected}")

                # Продолжаем выполнение с выбранным вариантом
                result = self.executor.execute(
                    self.pending_plan,
                    selected_option=selected
                )

                # Сбрасываем pending
                self.pending_options = None
                self.pending_plan = None

                # Обрабатываем результат
                return self._process_execution_result(result)

            return {"status": "error", "error": "Неверный выбор"}

        return {"status": "error", "error": "Введите номер варианта"}

    def _execute_plan(self, plan: list) -> dict:
        """
        Выполняет план и обрабатывает результат.
        """
        result = self.executor.execute(plan)
        return self._process_execution_result(result)

    def _process_execution_result(self, result: dict) -> dict:
        """
        Обрабатывает результат execution:
        - Сохраняет успешные действия в history
        - Обрабатывает clarification
        - Сохраняет ответ в thread
        """
        # =====================================================
        # NEED CLARIFICATION (multiple results)
        # =====================================================
        if result.get("status") == "need_clarification":
            self.pending_options = result.get("options", [])
            self.pending_plan = result.get("pending_plan") or self.pending_plan

            logger.info(f"WAITING USER CHOICE: {self.pending_options}")

            return {
                "status": "need_clarification",
                "options": self.pending_options,
                "message": result.get("message", "Выбери вариант:")
            }

        # =====================================================
        # SUCCESS — записываем в history
        # =====================================================
        if result.get("status") == "success":
            # Записываем каждый шаг в action history (для undo)
            for step in result.get("executed_steps", []):
                self.memory.record_action(
                    tool_name=step["tool"],
                    args=step["args"],
                    result=step["result"]
                )

            # Сохраняем ответ агента
            self.memory.save_message("agent", result)
            logger.info("Execution successful, recorded to history")

            return result

        # =====================================================
        # CANCELLED / ERROR — просто сохраняем в thread
        # =====================================================
        self.memory.save_message("agent", result)

        if result.get("status") == "cancelled":
            logger.info("Action cancelled by user")
        else:
            logger.error(f"Execution error: {result.get('error')}")

        return result

    # =========================================================
    # UNDO / REDO
    # =========================================================

    def undo(self) -> dict:
        """
        Отменяет последнее действие через MemoryManager.

        Returns:
            {"status": "success", "message": str} или {"status": "error", "message": str}
        """
        if not self.memory.can_undo():
            return {"status": "error", "message": "Нет действий для отмены"}

        # Получаем действие для undo
        undo_result = self.memory.undo()

        if undo_result["status"] != "success":
            return undo_result

        action = undo_result["action"]

        # 🔥 Здесь можно добавить фактический undo операции
        # (восстановление файла из backup и т.д.)
        # Пока просто помечаем как отменённое

        logger.info(f"Undo executed: {action['tool_name']}")

        # Сохраняем в thread
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

    def redo(self) -> dict:
        """
        Повторяет отменённое действие.
        """
        if not self.memory.can_redo():
            return {"status": "error", "message": "Нет действий для повтора"}

        redo_result = self.memory.redo()

        if redo_result["status"] != "success":
            return redo_result

        action = redo_result["action"]

        logger.info(f"Redo executed: {action['tool_name']}")

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

    def get_status(self) -> dict:
        """
        Возвращает статус агента для UI.
        """
        history_status = self.memory.get_history_status()

        return {
            "can_undo": history_status["can_undo"],
            "can_redo": history_status["can_redo"],
            "undo_count": history_status["undo_count"],
            "redo_count": history_status["redo_count"],
            "pending_selection": self.pending_options is not None,
            "entities": self.memory.get_entities()
        }
