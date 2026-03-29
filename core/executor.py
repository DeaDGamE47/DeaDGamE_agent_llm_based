from utils.logger import setup_logger

logger = setup_logger("Executor")


class Executor:

    def __init__(self, tool_registry):
        self.tool_registry = tool_registry

    def execute(self, plan, selected_option=None):
        logger.info("EXECUTION START")

        context = {}

        for step in plan:
            tool_name = step.get("tool")

            tool = self.tool_registry.get_tool(tool_name)

            if not tool:
                return {"status": "error", "error": f"Tool not found: {tool_name}"}

            # -------------------------
            # 🔥 RESOLVE ARGS
            # -------------------------
            args = self._resolve_args(step.get("args", {}), context, selected_option)

            logger.debug(f"RUN TOOL: {tool_name} | ARGS: {args}")

            # -------------------------
            # 🔥 VALIDATION
            # -------------------------
            validation_error = tool.validate(args)
            if validation_error:
                return validation_error

            # -------------------------
            # 🔥 CONFIRMATION (META)
            # -------------------------
            if getattr(tool, "requires_confirmation", False):
                path = args.get("path", "")

                print(f"\n⚠️ Подтверждение действия")
                print(f"Tool: {tool.name}")
                print(f"Risk: {tool.risk_level}")
                if path:
                    print(f"Path: {path}")

                confirm = input("Введите 'yes' для подтверждения: ").strip().lower()

                if confirm not in ["yes", "y", "да"]:
                    return {
                        "status": "cancelled",
                        "data": "Операция отменена"
                    }

            # -------------------------
            # 🔥 RUN TOOL
            # -------------------------
            try:
                result = tool.run(**args)
            except Exception as e:
                logger.exception(f"TOOL ERROR: {tool_name}")
                return {"status": "error", "error": str(e)}

            logger.debug(f"RESULT: {result}")

            # -------------------------
            # 🔥 MULTIPLE
            # -------------------------
            if result.get("status") == "multiple":
                return {
                    "status": "need_clarification",
                    "options": result.get("data", [])
                }

            # -------------------------
            # 🔥 ERROR
            # -------------------------
            if result.get("status") != "success":
                return result

            # -------------------------
            # 🔥 SAVE CONTEXT
            # -------------------------
            if "output" in step:
                context[step["output"]] = result.get("data")

        logger.info("EXECUTION FINISHED")

        return {
            "status": "success",
            "data": context
        }

    # =========================================================
    # ARG RESOLUTION
    # =========================================================
    def _resolve_args(self, args, context, selected_option):
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