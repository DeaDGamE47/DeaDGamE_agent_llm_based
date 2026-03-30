import json
import re
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ValidationError

from utils.logger import setup_logger
from utils.file_type_map import FILE_TYPE_MAP


logger = setup_logger("Interpreter")


# =========================================================
# PYDANTIC SCHEMAS
# =========================================================

class InterpretationResult(BaseModel):
    intent: str = Field(..., description="Намерение пользователя")
    entities: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    class Config:
        extra = "ignore"


# =========================================================
# INTERPRETER (STATELESS)
# =========================================================

class Interpreter:

    def __init__(self, llm_manager):
        self.llm_manager = llm_manager

    # =========================================================
    # MAIN
    # =========================================================

    def interpret(self, user_input: str, thread_context=None) -> Dict[str, Any]:

        logger.info(f"INTERPRET INPUT: {user_input}")

        model = self.llm_manager.get_model("interpreter")
        if not model:
            logger.error("Model not available")
            return self._fallback(user_input)

        prompt = self._build_prompt(user_input, thread_context)
        logger.debug(f"PROMPT: {prompt}")

        raw = None
        for attempt in range(3):
            raw = model.generate(prompt)
            if raw:
                break
            logger.warning(f"LLM attempt {attempt + 1} failed")

        if not raw:
            logger.error("LLM failed after retries")
            return self._fallback(user_input)

        logger.debug(f"RAW RESPONSE: {raw}")

        parsed = self._parse_and_validate(raw)
        if not parsed:
            return self._fallback(user_input)

        normalized = self._normalize(parsed, user_input)

        return normalized

    # =========================================================
    # PROMPT
    # =========================================================

    def _build_prompt(self, user_input, thread_context):

        context_section = ""
        if thread_context:
            context_section = f"\nТЕКУЩИЙ КОНТЕКСТ:\n{thread_context}\n"

        return {
            "system": f"""Ты извлекаешь intent и entities из запроса пользователя.

ВАЖНЫЕ ПРАВИЛА:

1. НЕ переводи слова пользователя
2. Сохраняй текст как есть
3. Только JSON (без markdown)

КОНТЕКСТ:

- если пользователь говорит "эта папка", "там" → folder: {{}}
- если "этот файл", "его" → file: {{}}

НЕ используй ref вообще

ФОРМАТ:

{{
    "intent": "string",
    "entities": {{
        "file": {{"name": "string", "type": "string"}},
        "folder": {{"name": "string"}}
    }}
}}

Если не уверен → intent = "chat"

{context_section}""",
            "user": user_input
        }

    # =========================================================
    # PARSE
    # =========================================================

    def _parse_and_validate(self, raw_text: str) -> Optional[InterpretationResult]:

        if not raw_text:
            return None

        parsed_data = None

        try:
            parsed_data = json.loads(raw_text)
        except:
            try:
                start = raw_text.find("{")
                end = raw_text.rfind("}") + 1
                parsed_data = json.loads(raw_text[start:end])
            except:
                return None

        if not parsed_data:
            return None

        try:
            return InterpretationResult.model_validate(parsed_data)
        except ValidationError:
            return None

    # =========================================================
    # NORMALIZE
    # =========================================================

    def _normalize(self, parsed: InterpretationResult, user_input: str) -> Dict[str, Any]:

        result = {
            "intent": parsed.intent,
            "entities": parsed.entities,
            "confidence": parsed.confidence
        }

        # intent aliases
        

        entities = result.get("entities", {})
        if not isinstance(entities, dict):
            entities = {}

        normalized = {}

        for key, value in entities.items():

            if isinstance(value, dict):
                normalized[key] = value
            else:
                normalized[key] = {"name": str(value)}

        text = user_input.lower()

        # =========================================================
        # 🔥 FILE TYPE DETECT
        # =========================================================

        file_entity = normalized.get("file")
        if file_entity:

            name = file_entity.get("name")
            file_type = file_entity.get("type")

            if not file_type:
                for k in FILE_TYPE_MAP.keys():
                    if k in text:
                        file_entity["type"] = k
                        break

            if name and "." not in name:
                ext = FILE_TYPE_MAP.get(file_entity.get("type"), ".txt")
                file_entity["name"] = name + ext

        result["entities"] = normalized
        return result

    # =========================================================
    # FALLBACK
    # =========================================================

    def _fallback(self, user_input: str) -> Dict[str, Any]:

        logger.info("FALLBACK")

        return {
            "intent": "chat",
            "entities": {
                "message": user_input
            },
            "confidence": 0.0
        }