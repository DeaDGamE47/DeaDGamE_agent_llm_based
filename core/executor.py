from utils.logger import setup_logger

logger = setup_logger("Executor")


class Executor:
    """
    ТУПОЙ исполнитель команд.

    НЕ управляет памятью, историей или контекстом.
    Только: валидация → исполнение → возврат результата (с undo_data если есть).

    Вся память управляется MemoryManager на уровне Agent.
    """

    def __init__(self, tool_registry):
        """
        Args:
            tool_registry: ToolRegistry с зарегистрированными инструментами
        """
        self.tool_registry = tool_registry
        logger.info("Executor initialized (dumb mode)")

    def execute(self, plan, selected_option=None):
        """
        Выполняет план шаг за шагом.

        Args:
            plan: Список шагов [{"tool": str, "args": dict, "output": str}, ...]
            selected_option: Выбранный вариант (для need_clarification)

        Returns:
            dict: {"status": "success", "data": {...}, "executed_steps": [...]}
               или {"status": "error", "error": str}
               или {"status": "need_clarification", "options": [...]}
               или {"status": "cancelled", "data": str}
        """
        logger.info(f"EXECUTION START: {len(plan)} steps")

        context = {}  # Локальный контекст для передачи данных между шагами
        executed_steps = []

        for step_idx, step in enumerate(plan):
            tool_name = step.get("tool")

            tool = self.tool_registry.get_tool(tool_name)
            if not tool:
                logger.error(f"Tool not found: {tool_name}")
                return {
                    "status": "error", 
                    "error": f"Tool not found: {tool_name}",
                    "failed_step": step_idx
                }

            # -------------------------
            # 🔥 RESOLVE ARGS (подстановка переменных)
            # -------------------------
            args = self._resolve_args(
                step.get("args", {}), 
                context, 
                selected_option
            )

            logger.debug(f"Step {step_idx}: {tool_name} | args: {args}")

            # -------------------------
            # 🔥 VALIDATION
            # -------------------------
            validation_error = tool.validate(args)
            if validation_error:
                logger.error(f"Validation failed for {tool_name}: {validation_error}")
                return {
                    "status": "error",
                    "error": f"Validation failed: {validation_error}",
                    "tool": tool_name,
                    "failed_step": step_idx
                }

            # -------------------------
            # 🔥 CONFIRMATION (META) — интерактивный ввод
            # -------------------------
            if getattr(tool, "requires_confirmation", False):
                path = args.get("path", "")

                print(f"\n⚠️  Подтверждение действия")
                print(f"   Tool: {tool.name}")
                print(f"   Risk: {tool.risk_level}")
                if path:
                    print(f"   Path: {path}")

                confirm = input("   Введите 'yes' для подтверждения: ").strip().lower()

                if confirm not in ["yes", "y", "да"]:
                    logger.info(f"Action cancelled by user: {tool_name}")
                    return {
                        "status": "cancelled",
                        "data": "Операция отменена пользователем",
                        "cancelled_step": step_idx
                    }

            # -------------------------
            # 🔥 RUN TOOL
            # -------------------------
            try:
                result = tool.run(**args)
            except Exception as e:
                logger.exception(f"Tool execution failed: {tool_name}")
                return {
                    "status": "error",
                    "error": str(e),
                    "tool": tool_name,
                    "failed_step": step_idx
                }

            logger.debug(f"Step {step_idx} result: {result}")

            # Сохраняем информацию о выполненном шаге
            step_info = {
                "step_idx": step_idx,
                "tool": tool_name,
                "args": args,
                "result": result
            }
            executed_steps.append(step_info)

            # -------------------------
            # 🔥 MULTIPLE RESULTS (need clarification)
            # -------------------------
            if result.get("status") == "multiple" or result.get("status") == "need_clarification":
                logger.info(f"Need clarification at step {step_idx}")
                return {
                    "status": "need_clarification",
                    "options": result.get("data", result.get("options", [])),
                    "message": result.get("message", "Выберите вариант:"),
                    "completed_steps": executed_steps[:-1],  # Все кроме текущего
                    "pending_step": step_idx,
                    "pending_tool": tool_name,
                    "pending_args": args
                }

            # -------------------------
            # 🔥 ERROR HANDLING
            # -------------------------
            if result.get("status") != "success":
                logger.error(f"Tool returned error: {tool_name} | {result.get('error')}")
                return {
                    "status": "error",
                    "error": result.get("error", "Unknown error"),
                    "tool": tool_name,
                    "failed_step": step_idx,
                    "completed_steps": executed_steps[:-1]
                }

            # -------------------------
            # 🔥 SAVE TO CONTEXT (для следующих шагов)
            # -------------------------
            if "output" in step:
                output_key = step["output"]
                context[output_key] = result.get("data")
                logger.debug(f"Context saved: {output_key} = {context[output_key]}")

        logger.info("EXECUTION FINISHED SUCCESSFULLY")

        return {
            "status": "success",
            "data": context,
            "executed_steps": executed_steps
        }

    def _resolve_args(self, args, context, selected_option):
        """
        Разрешает аргументы:
        - __SELECTED__ → selected_option
        - $var → context[var]
        - Обычные значения остаются как есть
        """
        resolved = {}

        for k, v in args.items():
            # Специальный маркер для выбранного варианта
            if v == "__SELECTED__":
                resolved[k] = selected_option
                continue

            # Переменные из контекста ($var)
            if isinstance(v, str) and v.startswith("$"):
                var_name = v[1:]
                if var_name in context:
                    resolved[k] = context[var_name]
                    continue
                else:
                    logger.warning(f"Context variable not found: {var_name}")

            # Прямая ссылка на контекст (для обратной совместимости)
            if isinstance(v, str) and v in context:
                resolved[k] = context[v]
                continue

            resolved[k] = v

        return resolved

    def validate_plan(self, plan):
        """
        Предварительная валидация плана (без выполнения).

        Returns:
            {"valid": True} или {"valid": False, "error": str, "step": int}
        """
        for idx, step in enumerate(plan):
            tool_name = step.get("tool")
            tool = self.tool_registry.get_tool(tool_name)

            if not tool:
                return {
                    "valid": False,
                    "error": f"Tool not found: {tool_name}",
                    "step": idx
                }

            args = step.get("args", {})
            validation = tool.validate(args)
            if validation:
                return {
                    "valid": False,
                    "error": validation,
                    "step": idx,
                    "tool": tool_name
                }

        return {"valid": True}
