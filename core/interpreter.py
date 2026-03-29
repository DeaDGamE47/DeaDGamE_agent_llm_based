import json
import re

from utils.logger import setup_logger
from utils.file_type_map import FILE_TYPE_MAP

logger = setup_logger("Interpreter")


class Interpreter:

    def __init__(self, llm_manager):
        self.llm_manager = llm_manager

    # =========================================================
    # MAIN
    # =========================================================
    def interpret(self, user_input: str, thread_context=None):
        logger.info(f"INTERPRET INPUT: {user_input}")

        model = self.llm_manager.get_model("interpreter")

        prompt = self._build_prompt(user_input, thread_context)
        logger.debug(f"PROMPT: {prompt}")

        raw = model.generate(prompt)
        logger.debug(f"RAW RESPONSE: {raw}")

        parsed = self._safe_parse(raw)
        logger.debug(f"PARSED BEFORE NORMALIZE: {parsed}")

        if not parsed:
            return self._fallback(user_input)

        parsed = self._normalize(parsed, user_input)
        logger.debug(f"PARSED AFTER NORMALIZE: {parsed}")

        error = self._validate(parsed)
        if error:
            logger.warning(f"VALIDATION FAILED: {error}")
            return self._fallback(user_input)

        return parsed

    # =========================================================
    # PROMPT
    # =========================================================
    def _build_prompt(self, user_input, thread_context):
        return {
            "system": """
Ты извлекаешь intent и entities.
ВАЖНО:
- НЕ переводи слова пользователя
- СОХРАНЯЙ оригинальный язык (русский/английский)
- "тестис" ≠ "testis"
- возвращай текст КАК ЕСТЬ

Формат:
{
  "intent": "string",
  "entities": {}
}

ПРАВИЛА:

1. Используй:
   file.name
   folder.name

2. Контекст:
   "эта папка", "в этой папке" → folder.ref="last"
   "этот файл" → file.ref="last"

3. Тип файла:
   python → type="python"
   json → type="json"
   текстовый → type="txt"

НЕ придумывай лишние поля.
""",
            "user": user_input,
            "context": thread_context or ""
        }

    # =========================================================
    # PARSE
    # =========================================================
    def _safe_parse(self, text):
        if not text:
            return None

        try:
            return json.loads(text)
        except:
            try:
                start = text.find("{")
                end = text.rfind("}") + 1
                return json.loads(text[start:end])
            except:
                logger.error("JSON parse failed")
                return None

    # =========================================================
    # NORMALIZE (ЕДИНЫЙ СЛОЙ)
    # =========================================================
    def _normalize(self, parsed, user_input):

        parsed.pop("type", None)
        parsed.pop("meta", None)

        # -------------------------
        # INTENT NORMALIZATION
        # -------------------------
        intent_aliases = {
            "folder_open": "open",
            "open_folder": "open",
            "file_open": "open",
            "open_file": "open",
            "delete_file": "delete",
            "delete_folder": "delete",
            "remove": "delete",
            "create file": "create_file",
            "createfile": "create_file",
            "make_file": "create_file",
            "delete file": "delete",
            "delete folder": "delete",
            "remove file": "delete",
            "remove": "delete",
        }

        intent = parsed.get("intent")

        if intent in intent_aliases:
            logger.debug(f"INTENT NORMALIZED: {intent} → {intent_aliases[intent]}")
            parsed["intent"] = intent_aliases[intent]

        # -------------------------
        # ENTITY NORMALIZATION
        # -------------------------
        entities = parsed.get("entities", {})

        if not isinstance(entities, dict):
            entities = {}

        normalized = {}

        for key, value in entities.items():

            # folder.name → folder
            if "." in key:
                main, sub = key.split(".", 1)
                normalized.setdefault(main, {})[sub] = value
                continue

            # folder_name → folder
            if key in ["folder_name", "dir", "directory"]:
                normalized["folder"] = {"name": value}
                continue

            # file_name → file
            if key in ["file_name", "filename"]:
                normalized["file"] = {"name": value}
                continue

            # обычный случай
            if isinstance(value, dict):
                normalized[key] = value
            else:
                normalized[key] = {"name": str(value)}

        text = user_input.lower()

        # -------------------------
        # CONTEXT (ref)
        # -------------------------
        if any(x in text for x in ["эта папка", "в этой папке", "там", "здесь"]):
            normalized["folder"] = {"ref": "last"}
            logger.debug("FOLDER REF DETECTED")

        if any(x in text for x in ["этот файл", "его"]):
            normalized["file"] = {"ref": "last"}
            logger.debug("FILE REF DETECTED")

        # -------------------------
        # DRIVE DETECTION
        # -------------------------
        match = re.search(r'([a-zA-Z]):', user_input)

        if match:
            drive = match.group(1).upper() + ":/"
            if "folder" in normalized:
                normalized["folder"]["start_path"] = drive
                logger.debug(f"DRIVE DETECTED: {drive}")

        # -------------------------
        # FILE TYPE + EXTENSION
        # -------------------------
        file_entity = normalized.get("file")

        if file_entity:

            name = file_entity.get("name")
            file_type = file_entity.get("type")

            # определяем тип если LLM не дал
            if not file_type:
                for k in FILE_TYPE_MAP.keys():
                    if k in text:
                        file_type = k
                        file_entity["type"] = k
                        logger.debug(f"FILE TYPE DETECTED: {k}")
                        break

            # добавляем расширение
            if name:
                if "." not in name:
                    ext = FILE_TYPE_MAP.get(file_type, ".txt")
                    file_entity["name"] = name + ext
                    logger.debug(f"EXTENSION APPLIED: {file_entity['name']}")

        parsed["entities"] = normalized
        # -------------------------
# 🔥 FIX REF + NAME CONFLICT
# -------------------------
        file_entity = normalized.get("file")
        if file_entity:
            if file_entity.get("ref") and file_entity.get("name"):
                logger.debug("REMOVE REF FROM FILE (name present)")
                file_entity.pop("ref")

        folder_entity = normalized.get("folder")

        if folder_entity:
            if folder_entity.get("ref") and folder_entity.get("name"):
                logger.debug("REMOVE REF FROM FOLDER (name present)")
                folder_entity.pop("ref")
        # -------------------------
        # 🔥 FILE NAME FALLBACK
        # -------------------------
        file_entity = normalized.get("file")

        if file_entity and not file_entity.get("name"):


            # ищем "файл X"
            match = re.search(r'файл\s+([^\s]+)', user_input.lower())

            if match:
                name = match.group(1)

                # добавляем расширение если нет
                if "." not in name:
                    ext = FILE_TYPE_MAP.get(file_entity.get("type"), ".txt")
                    name = name + ext

                file_entity["name"] = name

                logger.debug(f"FILE NAME FALLBACK: {name}")
        return parsed

    # =========================================================
    # VALIDATE
    # =========================================================
    def _validate(self, parsed):
        if not isinstance(parsed, dict):
            return "Not dict"

        if "intent" not in parsed:
            return "No intent"

        if "entities" not in parsed:
            return "No entities"

        if not isinstance(parsed["entities"], dict):
            return "Entities not dict"

        return None 
    

    # =========================================================
    # FALLBACK
    # =========================================================
    def _fallback(self, user_input):
        logger.info("FALLBACK TO CHAT")

        return {
            "intent": "chat",
            "entities": {
                "message": user_input
            }
        }