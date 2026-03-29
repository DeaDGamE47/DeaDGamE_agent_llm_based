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

        # -------------------------
        # 🔥 ОБРАБОТКА ВЫБОРА
        # -------------------------
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

                    self.pending_options = None
                    self.pending_plan = None

                    return result

            return "❌ Неверный выбор"

        # -------------------------
        # 🔥 PIPELINE
        # -------------------------
        interpreted = self.interpreter.interpret(user_input)

        interpreted = self.context.resolve(interpreted)

        plan = self.planner.build_plan(interpreted)

        if not plan:
            return "❌ План не построен"

        plan = self.router.route(plan)

        result = self.executor.execute(plan)

        # -------------------------
        # 🔥 MULTIPLE
        # -------------------------
        if result.get("status") == "need_clarification":
            self.pending_options = result["options"]
            self.pending_plan = plan

            return {
                "status": "need_clarification",
                "options": result["options"]
            }

        self.memory.update_entities(interpreted.get("entities", {}))

        return result