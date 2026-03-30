from utils.logger import setup_logger

logger = setup_logger("Executor")


class Executor:
    """
    ТУПОЙ исполнитель команд.
    """

    def __init__(self, tool_registry):
        self.tool_registry = tool_registry
        logger.info("Executor initialized (dumb mode)")

    def execute(self, plan, selected_option=None, context=None, start_step=0):
        """
        Выполняет план (с поддержкой continuation)
        """

        if context is None:
            context = {}

        logger.info(f"EXECUTION START: {len(plan)} steps | from step {start_step}")

        executed_steps = []

        for step_idx in range(start_step, len(plan)):
            step = plan[step_idx]
            tool_name = step.get("tool")

            tool = self.tool_registry.get_tool(tool_name)
            if not tool:
                return {
                    "status": "error",
                    "error": f"Tool not found: {tool_name}",
                    "failed_step": step_idx
                }

            # -------------------------
            # 🔥 RESOLVE ARGS
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
                return {
                    "status": "error",
                    "error": f"Validation failed: {validation_error}",
                    "tool": tool_name,
                    "failed_step": step_idx
                }

            # -------------------------
            # 🔥 RUN TOOL
            # -------------------------
            try:
                result = tool.run(**args)
            except Exception as e:
                logger.exception(f"Tool crash: {tool_name}")
                return {
                    "status": "error",
                    "error": str(e),
                    "tool": tool_name,
                    "failed_step": step_idx
                }

            logger.debug(f"Step {step_idx} result: {result}")

            # сохраняем шаг
            step_info = {
                "step_idx": step_idx,
                "tool": tool_name,
                "args": args,
                "result": result
            }
            executed_steps.append(step_info)

            # -------------------------
            # 🔥 NEED CLARIFICATION
            # -------------------------
            if result.get("status") in ["multiple", "need_clarification"]:
                logger.info(f"Need clarification at step {step_idx}")

                return {
                    "status": "need_clarification",
                    "options": result.get("options") or result.get("data") or [],
                    "message": result.get("message", "Выберите вариант:"),
                    "plan": plan,                     # 🔥 ВАЖНО
                    "context": context,               # 🔥 ВАЖНО
                    "next_step": step_idx             # 🔥 ВАЖНО
                }

            # -------------------------
            # 🔥 ERROR
            # -------------------------
            if result.get("status") != "success":
                return {
                    "status": "error",
                    "error": result.get("error"),
                    "tool": tool_name,
                    "failed_step": step_idx
                }

            # -------------------------
            # 🔥 SAVE TO CONTEXT (FIX!)
            # -------------------------
            if "output" in step:
                output_key = step["output"]
                data = result.get("data")

                # 🔥 НОРМАЛИЗАЦИЯ
                if isinstance(data, dict) and "path" in data:
                    context[output_key] = data["path"]
                else:
                    context[output_key] = data

                logger.debug(f"Context saved: {output_key} = {context[output_key]}")

        logger.info("EXECUTION FINISHED SUCCESSFULLY")

        return {
            "status": "success",
            "data": context,
            "executed_steps": executed_steps
        }

    # =========================================================

    def continue_execution(self, plan, context, selected_option, start_step):
        """
        Продолжение выполнения после выбора
        """
        return self.execute(
            plan=plan,
            selected_option=selected_option,
            context=context,
            start_step=start_step
        )

    # =========================================================

    def _resolve_args(self, args, context, selected_option):
        resolved = {}

        for k, v in args.items():

            if v == "__SELECTED__":
                resolved[k] = selected_option
                continue

            if isinstance(v, str) and v.startswith("$"):
                var_name = v[1:]
                resolved[k] = context.get(var_name)
                continue

            if isinstance(v, str) and v in context:
                resolved[k] = context[v]
                continue

            resolved[k] = v

        return resolved