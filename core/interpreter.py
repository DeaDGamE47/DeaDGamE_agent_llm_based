import json
import re
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ValidationError

from utils.logger import setup_logger
from utils.file_type_map import FILE_TYPE_MAP

logger = setup_logger("Interpreter")


# =========================================================
# PYDANTIC SCHEMAS
# =========================================================
class FileEntity(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    ref: Optional[str] = None  # "last" для контекстных ссылок


class FolderEntity(BaseModel):
    name: Optional[str] = None
    ref: Optional[str] = None
    start_path: Optional[str] = None  # для дисков (C:/)


class InterpretationResult(BaseModel):
    """
    Строгая схема ответа от LLM.
    Все дополнительные поля игнорируются (extra='ignore').
    """
    intent: str = Field(..., description="Намерение пользователя")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Извлеченные сущности")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Уверенность модели")
    
    class Config:
        extra = "ignore"  # Игнорируем лишние поля от LLM


class Interpreter:

    def __init__(self, llm_manager):
        self.llm_manager = llm_manager

    # =========================================================
    # MAIN
    # =========================================================
    def interpret(self, user_input: str, thread_context=None) -> Dict[str, Any]:
        """
        Основной метод интерпретации.
        Возвращает dict (для обратной совместимости) или вызывает fallback.
        """
        logger.info(f"INTERPRET INPUT: {user_input}")

        model = self.llm_manager.get_model("interpreter")
        if not model:
            logger.error("Model not available")
            return self._fallback(user_input)

        prompt = self._build_prompt(user_input, thread_context)
        logger.debug(f"PROMPT: {prompt}")

        # 🔥 NEW: Retry logic на уровне LLM
        raw = None
        for attempt in range(3):
            raw = model.generate(prompt)
            if raw:
                break
            logger.warning(f"LLM attempt {attempt + 1} failed, retrying...")
        
        if not raw:
            logger.error("LLM failed after 3 attempts")
            return self._fallback(user_input)

        logger.debug(f"RAW RESPONSE: {raw}")

        # 🔥 NEW: Pydantic валидация
        parsed = self._parse_and_validate(raw, user_input)
        
        if not parsed:
            return self._fallback(user_input)

        # Нормализация (сохраняем существующую логику)
        normalized = self._normalize(parsed, user_input)
        logger.debug(f"NORMALIZED: {normalized}")

        return normalized

    # =========================================================
    # PROMPT
    # =========================================================
    def _build_prompt(self, user_input, thread_context):
        return {
            "system": """Ты извлекаешь intent и entities из запроса пользователя.

ВАЖНЫЕ ПРАВИЛА:
1. НЕ переводи слова пользователя - сохраняй оригинальный язык
2. "тестис" ≠ "testis" - сохраняй текст КАК ЕСТЬ
3. Используй строгий JSON формат без markdown

ФОРМАТ ОТВЕТА (только JSON):
{
    "intent": "string",
    "entities": {
        "file": {"name": "string", "type": "string", "ref": "last"},
        "folder": {"name": "string", "ref": "last", "start_path": "C:/"}
    }
}

ПРАВИЛА ENTITIES:
- file.name: имя файла с расширением
- file.type: python|json|txt|docx|etc
- file.ref: "last" только для ссылок типа "этот файл"
- folder.name: имя папки
- folder.ref: "last" для "эта папка", "в этой папке"
- folder.start_path: диск (C:/, D:/)

INTENT ALIASES:
- open, folder_open, open_folder, file_open → "open"
- delete, delete_file, remove, remove_file → "delete"
- create_file, createfile, make_file → "create_file"
- show_folder, list_folder → "show_folder"
- write_file → "write_file"
- create_and_write_file → "create_and_write_file"

НЕ придумывай лишние поля. Если не уверен - используй intent "chat".""",
            "user": user_input,
            "context": thread_context or ""
        }

    # =========================================================
    # PARSE & VALIDATE (PYDANTIC)
    # =========================================================
    def _parse_and_validate(self, raw_text: str, user_input: str) -> Optional[InterpretationResult]:
        """
        Извлекает JSON из ответа LLM и валидирует через Pydantic.
        Возвращает InterpretationResult или None при ошибке.
        """
        if not raw_text:
            return None

        # Пытаемся распарсить JSON
        parsed_data = None
        
        # Попытка 1: Прямой парсинг
        try:
            parsed_data = json.loads(raw_text)
        except json.JSONDecodeError:
            # Попытка 2: Извлечь JSON из markdown (```json ... ```)
            try:
                # Ищем между фигурными скобками
                start = raw_text.find("{")
                end = raw_text.rfind("}") + 1
                if start != -1 and end > start:
                    parsed_data = json.loads(raw_text[start:end])
                else:
                    # Попытка 3: Поиск в markdown блоках
                    import re
                    json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', raw_text, re.DOTALL)
                    if json_match:
                        parsed_data = json.loads(json_match.group(1))
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"JSON extraction failed: {e}")
                return None

        if not parsed_data:
            return None

        # Валидация через Pydantic
        try:
            result = InterpretationResult.model_validate(parsed_data)
            logger.debug(f"Pydantic validation passed: intent={result.intent}")
            return result
        except ValidationError as e:
            logger.warning(f"Pydantic validation failed: {e}")
            # Пробуем исправить common issues
            fixed_data = self._attempt_fix(parsed_data)
            if fixed_data:
                try:
                    return InterpretationResult.model_validate(fixed_data)
                except ValidationError:
                    pass
            return None

    def _attempt_fix(self, data: dict) -> Optional[dict]:
        """
        Попытка исправить common issues в ответе LLM.
        """
        if not isinstance(data, dict):
            return None
        
        # Если нет entities, но есть другие поля
        if "entities" not in data:
            data["entities"] = {}
        
        # Если entities не dict
        if not isinstance(data.get("entities"), dict):
            data["entities"] = {}
        
        # Если нет intent
        if "intent" not in data:
            return None
            
        return data

    # =========================================================
    # NORMALIZE (СОХРАНЯЕМ СУЩЕСТВУЮЩУЮ ЛОГИКУ)
    # =========================================================
    def _normalize(self, parsed: InterpretationResult, user_input: str) -> Dict[str, Any]:
        """
        Нормализация entities и intent.
        Возвращает dict для обратной совместимости с остальной системой.
        """
        result = {
            "intent": parsed.intent,
            "entities": parsed.entities,
            "confidence": parsed.confidence
        }

        # Intent aliases
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
        }

        if result["intent"] in intent_aliases:
            old_intent = result["intent"]
            result["intent"] = intent_aliases[old_intent]
            logger.debug(f"INTENT NORMALIZED: {old_intent} → {result['intent']}")

        # Entity normalization
        entities = result.get("entities", {})
        if not isinstance(entities, dict):
            entities = {}
            result["entities"] = entities

        normalized = {}
        
        for key, value in entities.items():
            # folder.name → folder
            if "." in key:
                main, sub = key.split(".", 1)
                normalized.setdefault(main, {})[sub] = value
                continue

            # folder_name → folder
            if key in ["folder_name", "dir", "directory"]:
                normalized["folder"] = {"name": value} if isinstance(value, str) else value
                continue

            # file_name → file
            if key in ["file_name", "filename"]:
                normalized["file"] = {"name": value} if isinstance(value, str) else value
                continue

            # Обычный случай
            if isinstance(value, dict):
                normalized[key] = value
            else:
                normalized[key] = {"name": str(value)}

        text = user_input.lower()

        # Context detection (ref)
        if any(x in text for x in ["эта папка", "в этой папке", "там", "здесь"]):
            normalized.setdefault("folder", {})["ref"] = "last"
            logger.debug("FOLDER REF DETECTED")

        if any(x in text for x in ["этот файл", "его"]):
            normalized.setdefault("file", {})["ref"] = "last"
            logger.debug("FILE REF DETECTED")

        # Drive detection
        match = re.search(r'([a-zA-Z]):', user_input)
        if match:
            drive = match.group(1).upper() + ":/"
            if "folder" in normalized:
                normalized["folder"]["start_path"] = drive
                logger.debug(f"DRIVE DETECTED: {drive}")

        # File type + extension handling
        file_entity = normalized.get("file")
        if file_entity:
            name = file_entity.get("name")
            file_type = file_entity.get("type")

            # Определяем тип если LLM не дал
            if not file_type:
                for k in FILE_TYPE_MAP.keys():
                    if k in text:
                        file_type = k
                        file_entity["type"] = k
                        logger.debug(f"FILE TYPE DETECTED: {k}")
                        break

            # Добавляем расширение
            if name and "." not in name:
                ext = FILE_TYPE_MAP.get(file_type, ".txt")
                file_entity["name"] = name + ext
                logger.debug(f"EXTENSION APPLIED: {file_entity['name']}")

        # Fix ref + name conflict
        file_entity = normalized.get("file")
        if file_entity and file_entity.get("ref") and file_entity.get("name"):
            logger.debug("REMOVE REF FROM FILE (name present)")
            file_entity.pop("ref", None)

        folder_entity = normalized.get("folder")
        if folder_entity and folder_entity.get("ref") and folder_entity.get("name"):
            logger.debug("REMOVE REF FROM FOLDER (name present)")
            folder_entity.pop("ref", None)

        # File name fallback (поиск "файл X")
        file_entity = normalized.get("file")
        if file_entity and not file_entity.get("name"):
            match = re.search(r'файл\s+([^\s]+)', user_input.lower())
            if match:
                name = match.group(1)
                if "." not in name:
                    ext = FILE_TYPE_MAP.get(file_entity.get("type"), ".txt")
                    name = name + ext
                file_entity["name"] = name
                logger.debug(f"FILE NAME FALLBACK: {name}")

        result["entities"] = normalized
        return result

    # =========================================================
    # FALLBACK
    # =========================================================
    def _fallback(self, user_input: str) -> Dict[str, Any]:
        """Fallback в chat mode при любой ошибке."""
        logger.info("FALLBACK TO CHAT")
        return {
            "intent": "chat",
            "entities": {
                "message": user_input
            },
            "confidence": 0.0
        }
