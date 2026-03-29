import os
from difflib import SequenceMatcher

from tools.base import BaseTool


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


class FindTool(BaseTool):

    name = "find"
    description = "Ищет файл или папку"

    required_args = ["name"]
    optional_args = ["type", "start_path"]

    category = "file"
    risk_level = "low"

    # =========================================================
    # MAIN
    # =========================================================
    def run(self, name, type="any", start_path=None, path=None):

        # -------------------------
        # 🔥 SELECTED (multiple)
        # -------------------------
        if path:
            return {"status": "success", "data": path}

        name = name.lower()

        # -------------------------
        # 🔥 START PATH
        # -------------------------
        if not start_path:
            start_path = "C:/"

        results = []

        # -------------------------
        # 🔥 WALK
        # -------------------------
        for root, dirs, files in os.walk(start_path):

            # 🔥 depth limit
            depth = root[len(start_path):].count(os.sep)
            if depth > MAX_DEPTH:
                continue

            # 🔥 ignore мусор
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

            items = []

            if type == "folder":
                items = dirs
            elif type == "file":
                items = files
            else:
                items = dirs + files

            for item in items:
                full_path = os.path.join(root, item)
                item_lower = item.lower()

                # -------------------------
                # 🔥 EXACT MATCH (instant return)
                # -------------------------
                if item_lower == name:
                    return {"status": "success", "data": full_path}

                # -------------------------
                # 🔥 SCORING
                # -------------------------
                score = similarity(name, item_lower)

                # бонус за вхождение
                if name in item_lower:
                    score += 0.3

                # бонус за близость к start_path
                distance = root.count(os.sep)
                score += max(0, 1 - distance * 0.1)

                if score > 0.4:
                    results.append((score, full_path))

        # -------------------------
        # 🔥 NO RESULTS
        # -------------------------
        if not results:
            return {"status": "error", "error": f"Не найдено: {name}"}

        # -------------------------
        # 🔥 SORT
        # -------------------------
        results.sort(key=lambda x: x[0], reverse=True)

        top = [p for _, p in results[:MAX_RESULTS]]

        # -------------------------
        # 🔥 SINGLE
        # -------------------------
        if len(top) == 1:
            return {"status": "success", "data": top[0]}

        # -------------------------
        # 🔥 MULTIPLE
        # -------------------------
        return {"status": "multiple", "data": top}