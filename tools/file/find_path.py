import os
from difflib import SequenceMatcher

from tools.base import BaseTool

from utils.logger import setup_logger

# -------------------------
# 🔥 CONFIG
# -------------------------
IGNORED_DIRS = {
    "venv", "__pycache__", ".git", "node_modules",
    "site-packages", "dist", "build"
}

MAX_RESULTS = 5
MAX_DEPTH = 5



def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

logger = setup_logger("Tool:find")


class FindTool(BaseTool):

    name = "find"
    description = "Ищет файл или папку"

    required_args = ["name"]
    optional_args = ["type", "start_path"]

    category = "file"
    risk_level = "low"

    def run(self, name, type="any", start_path=None, path=None):

        logger.info(f"FIND START: name={name}, type={type}, start_path={start_path}, selected={path}")

        # -------------------------
        # 🔥 SELECTED (multiple)
        # -------------------------
        if path:
            logger.info(f"FIND SELECTED: {path}")
            return self.success(
                data={"path": path},
                message=f"Выбран путь: {path}"
            )

        name = name.lower()

        if not start_path:
            start_path = "C:/"
            logger.debug(f"START PATH DEFAULTED: {start_path}")

        results = []
        scanned_dirs = 0
        scanned_items = 0

        for root, dirs, files in os.walk(start_path):

            scanned_dirs += 1

            depth = root[len(start_path):].count(os.sep)
            if depth > MAX_DEPTH:
                continue

            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

            if type == "folder":
                items = dirs
            elif type == "file":
                items = files
            else:
                items = dirs + files

            for item in items:
                scanned_items += 1

                full_path = os.path.join(root, item)
                item_lower = item.lower()

                # EXACT MATCH
                if item_lower == name:
                    logger.info(f"FIND EXACT MATCH: {full_path}")
                    return self.success(
                        data={"path": full_path},
                        message=f"Найдено: {full_path}"
                    )

                score = similarity(name, item_lower)

                if name in item_lower:
                    score += 0.3

                distance = root.count(os.sep)
                score += max(0, 1 - distance * 0.1)

                if score > 0.4:
                    logger.debug(f"MATCH: {full_path} | score={round(score, 2)}")
                    results.append((score, full_path))

        logger.debug(f"SCAN COMPLETE: dirs={scanned_dirs}, items={scanned_items}")

        if not results:
            logger.warning(f"FIND FAILED: {name} not found")
            return self.error(f"Не найдено: {name}")

        results.sort(key=lambda x: x[0], reverse=True)
        top = [p for _, p in results[:MAX_RESULTS]]

        logger.info(f"FIND RESULTS: {len(top)} candidates")

        # SINGLE
        if len(top) == 1:
            logger.info(f"FIND SINGLE RESULT: {top[0]}")
            return self.success(
                data={"path": top[0]},
                message=f"Найдено: {top[0]}"
            )

        # MULTIPLE
        logger.info(f"FIND MULTIPLE RESULTS: {top}")
        return self.need_clarification(
            options=top,
            message="Найдено несколько вариантов, выбери:"
        )