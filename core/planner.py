from utils.logger import setup_logger

logger = setup_logger("Planner")


class Planner:

    def __init__(self):
        self.templates = {

            # -------------------------
            # OPEN
            # -------------------------
            "open": [
                {"tool": "find", "use": "folder", "output": "path"},
                {"tool": "open", "args": {"path": "path"}}
            ],

            # -------------------------
            # SHOW FOLDER
            # -------------------------
            "show_folder": [
                {"tool": "find", "use": "folder", "output": "path"},
                {"tool": "list", "args": {"path": "path"}}
            ],

            # -------------------------
            # DELETE
            # -------------------------
            "delete": [
                {"tool": "find", "use": "file", "output": "path"},
                {"tool": "delete", "args": {"path": "path"}}
            ],

            # -------------------------
            # CREATE FILE
            # -------------------------
            "create_file": [
                {"tool": "find", "use": "folder", "output": "folder_path"},
                {"tool": "join_path", "output": "path"},
                {"tool": "create_file", "args": {"path": "path"}}
            ],

            # -------------------------
            # WRITE FILE
            # -------------------------
            "write_file": [
                {"tool": "find", "use": "file", "output": "path"},
                {"tool": "write_file", "args": {"path": "path"}}
            ],

            # -------------------------
            # CREATE + WRITE
            # -------------------------
            "create_and_write_file": [
                {"tool": "find", "use": "folder", "output": "folder_path"},
                {"tool": "join_path", "output": "path"},
                {"tool": "create_file", "args": {"path": "path"}},
                {"tool": "write_file", "args": {"path": "path"}}
            ],
        }

    # =========================================================
    # MAIN
    # =========================================================
    def build_plan(self, interpreted):
        intent = interpreted.get("intent")
        entities = interpreted.get("entities", {})

        logger.debug(f"INTENT: {intent}")
        logger.debug(f"ENTITIES: {entities}")

        template = self.templates.get(intent)

        if not template:
            logger.warning(f"NO TEMPLATE: {intent}")
            return []

        return self._apply(template, entities)

    # =========================================================
    # APPLY RULES
    # =========================================================
    def _apply(self, plan, entities):
        result = []

        file_e = entities.get("file")
        folder_e = entities.get("folder")

        for step in plan:
            step = step.copy()

            # -------------------------
            # ENTITY RESOLUTION
            # -------------------------
            if "use" in step:
                use_type = step.pop("use")

                # 🔥 приоритет зависит от сценария
                if step.get("tool") == "find":

                    # если ищем папку (create_file)
                    if step.get("output") == "folder_path":
                        entity = folder_e
                        entity_type = "folder"

                    # если обычный find файла
                    elif file_e:
                        entity = file_e
                        entity_type = "file"

                    else:
                        entity = entities.get(use_type)
                        entity_type = use_type

                if not entity:
                    logger.warning(f"MISSING ENTITY: {use_type}")
                    continue

                step["args"] = {
                    "name": entity.get("name"),
                    "type": entity_type
                }

                # 🔥 КРИТИЧНО: поддержка выбора
                if step["tool"] == "find":
                    step["args"]["path"] = "__SELECTED__"

                if entity.get("start_path"):
                    step["args"]["start_path"] = entity["start_path"]

            # -------------------------
            # JOIN PATH FIX
            # -------------------------
            if step["tool"] == "join_path":
                step["args"] = {
                    "folder_path": "folder_path",
                    "file_name": file_e.get("name") if file_e else None
                }

            result.append(step)

        logger.debug(f"FINAL PLAN: {result}")
        return result