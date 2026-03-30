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
        # 🔥 NEW: Хранение последнего контекста для разрешения ref
        self.last_folder: Optional[str] = None
        self.last_file: Optional[str] = None

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

        # 🔥 NEW: Добавляем контекст в промпт если есть сохранённые пути
        enriched_context = self._build_context_string()
        
        prompt = self._build_prompt(user_input, thread_context, enriched_context)
        logger.debug(f"PROMPT: {prompt}")

        # Retry logic на уровне LLM
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

        # Pydantic валидация
        parsed = self._parse_and_validate(raw, user_input)
        
        if not parsed:
            return self._fallback(user_input)

        # Нормализация с разрешением контекстных ссылок
        normalized = self._normalize(parsed, user_input)
        logger.debug(f"NORMALIZED: {normalized}")

        # 🔥 NEW: Обновляем last_* после успешной интерпретации
        self._update_memory(normalized)

        return normalized

    def _build_context_string(self) -> str:
        """Строит строку контекста из сохранённых путей."""
        parts = []
        if self.last_folder:
            parts.append(f'Последняя папка: "{self.last_folder}"')
        if self.last_file:
            parts.append(f'Последний файл: "{self.last_file}"')
        return "\n".join(parts) if parts else ""

    def _update_memory(self, normalized: Dict):
        """Обновляет память последних использованных путей."""
        folder = normalized.get("folder", {})
        if folder.get("name") and not folder.get("ref"):
            self.last_folder = folder["name"]
            logger.debug(f"MEMORY: last_folder = {self.last_folder}")
        
        file = normalized.get("file", {})
        if file.get("name") and not file.get("ref"):
            self.last_file = file["name"]
            logger.debug(f"MEMORY: last_file = {self.last_file}")

    # =========================================================
    # PROMPT
    # =========================================================
    def _build_prompt(self, user_input, thread_context, enriched_context=""):
        context_section = ""
        if enriched_context:
            context_section = f"\nКОНТЕКСТ (используй при разрешении ссылок):\n{enriched_context}\n"
        
        if thread_context:
            context_section += f"\nТЕКУЩИЙ КОНТЕКСТ:\n{thread_context}\n"

        return {
            "system": f"""Ты извлекаешь intent и entities из запроса пользователя.

ВАЖНЫЕ ПРАВИЛА:
1. НЕ переводи слова пользователя - сохраняй оригинальный язык
2. "тестис" ≠ "testis" - сохраняй текст КАК ЕСТЬ
3. Используй строгий JSON формат без markdown

КОНТЕКСТНЫЕ ССЫЛКИ (КРИТИЧНО):
- "эта папка", "в этой папке", "там", "сюда" → folder: {{ "ref": "last" }} (БЕЗ name!)
- "этот файл", "его", "в него" → file: {{ "ref": "last" }} (БЕЗ name!)
- Если пользователь говорит "создай файл X в этой папке":
  - file: {{ "name": "X", "type": "..." }}
  - folder: {{ "ref": "last" }} (только ref, без name!)

ФОРМАТ ОТВЕТА (только JSON):
{{
    "intent": "string",
    "entities": {{
        "file": {{"name": "string", "type": "string", "ref": "last"}},
        "folder": {{"name": "string", "ref": "last", "start_path": "C:/"}}
    }}
}}

ПРАВИЛА ENTITIES:
- file.name: имя файла с расширением (только если явно назван)
- file.type: python|json|txt|docx|etc
- file.ref: "last" только для ссылок типа "этот файл"
- folder.name: имя папки (только если явно названа)
- folder.ref: "last" для "эта папка", "в этой папке", "там"
- folder.start_path: диск (C:/, D:/)

INTENT ALIASES:
- open, folder_open, open_folder, file_open → "open"
- delete, delete_file, remove, remove_file → "delete"
- create_file, createfile, make_file → "create_file"
- show_folder, list_folder → "show_folder"
- write_file → "write_file"
- create_and_write_file → "create_and_write_file"

НЕ придумывай лишние поля. Если не уверен - используй intent "chat".{context_section}""",
            "user": user_input
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
    # NORMALIZE (СОХРАНЯЕМ СУЩЕСТВУЮЩУЮ ЛОГИКУ + FIX REF)
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

        # 🔥 NEW: Разрешение контекстных ссылок через память
        folder_entity = normalized.get("folder", {})
        
        # Если LLM дала ref="last", подставляем реальный путь из памяти
        if folder_entity.get("ref") == "last" and self.last_folder:
            folder_entity["name"] = self.last_folder
            folder_entity.pop("ref", None)
            logger.debug(f"RESOLVED folder ref → {self.last_folder}")

        # Если не определена папка, но есть контекстные слова
        elif any(x in text for x in ["эта папка", "в этой папке", "там", "сюда", "здесь"]):
            if self.last_folder and not folder_entity.get("name"):
                normalized["folder"] = {"name": self.last_folder}
                logger.debug(f"FOLDER FROM MEMORY: {self.last_folder}")

        # Аналогично для файлов
        file_entity = normalized.get("file", {})
        if file_entity.get("ref") == "last" and self.last_file:
            file_entity["name"] = self.last_file
            file_entity.pop("ref", None)
            logger.debug(f"RESOLVED file ref → {self.last_file}")

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
