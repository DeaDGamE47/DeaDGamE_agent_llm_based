from utils.logger import setup_logger

logger = setup_logger("Router")


class Router:

    def __init__(self):
        pass

    def route(self, plan):
        logger.debug("ROUTING START")

        routed = []

        for step in plan:
            step = step.copy()

            tool = step.get("tool")

            # -------------------------
            # 🔥 RULES
            # -------------------------
            if tool in ["create_file", "write_file"]:
                step["model"] = "code"

            elif tool in ["find", "open", "delete"]:
                step["model"] = "fast"

            else:
                step["model"] = "default"

            logger.debug(f"ROUTE: {tool} → {step['model']}")

            routed.append(step)

        return routed