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

        self.pending_options = None
        self.pending_plan = None

    # =========================================================
    # MAIN
    # =========================================================

    def handle_input(self, user_input):

        logger.info(f"USER INPUT: {user_input}")

        # 🔥 сохраняем сообщение пользователя
        self.memory.save_message("user", user_input)

        # =====================================================
        # ОБРАБОТКА ВЫБОРА (multiple results)
        # =====================================================

        if self.pending_options:

            if user_input.isdigit():
                idx = int(user_input) - 1

                if 0 <= idx < len(self.pending_options):
                    selected = self.pending_options[idx]

                    logger.debug(f"OPTION SELECTED: {selected}")

                    result = self.executor.execute(
                        self.pending_plan,
                        selected_option=selected
                    )

                    # сбрасываем pending
                    self.pending_options = None
                    self.pending_plan = None

                    # 🔥 сохраняем ответ агента
                    self.memory.save_message("agent", result)

                    return result

            return "❌ Неверный выбор"

        # =====================================================
        # PIPELINE
        # =====================================================

        # 🔥 (опционально позже сюда добавим RAG)
        thread_context = None

        interpreted = self.interpreter.interpret(
            user_input,
            thread_context=thread_context
        )

        logger.debug(f"INTERPRETED: {interpreted}")

        # 🔥 контекст (ref=last и т.д.)
        interpreted = self.context.resolve(interpreted)

        logger.debug(f"RESOLVED: {interpreted}")

        # 🔥 сохраняем entities в память
        self.memory.update_entities(interpreted.get("entities", {}))

        # -------------------------
        # PLAN
        # -------------------------

        plan = self.planner.build_plan(interpreted)

        if not plan:
            return "❌ План не построен"

        logger.debug(f"PLAN: {plan}")

        # -------------------------
        # ROUTER
        # -------------------------

        plan = self.router.route(plan)

        # -------------------------
        # EXECUTION
        # -------------------------

        result = self.executor.execute(plan)

        # =====================================================
        # NEED CLARIFICATION
        # =====================================================

        if result.get("status") == "need_clarification":

            self.pending_options = result.get("options", [])
            self.pending_plan = plan

            logger.info(f"WAITING USER CHOICE: {self.pending_options}")

            return {
                "status": "need_clarification",
                "options": self.pending_options
            }

        # =====================================================
        # SUCCESS / FINAL
        # =====================================================

        # 🔥 сохраняем ответ агента
        self.memory.save_message("agent", result)

        return result