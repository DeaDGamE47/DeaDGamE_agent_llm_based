# agent_core/analyzer.py
import json
from typing import Dict, Any, List
from .llm.factory import LLMFactory
from .logger import default_logger

class CategoryRouter:
    """
    Анализирует запрос с помощью LLM и выбирает подходящую категорию из конфига.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.analyzer_config = config.get("analyzer", {})
        self.enabled = self.analyzer_config.get("enabled", True)
        self.analyzer_model = self.analyzer_config.get("model", "llama3.2:1b")
        self.categories = self.analyzer_config.get("categories", [])

        if not self.categories:
            default_logger.warning("Категории для анализатора не заданы, будет использоваться fallback-логика")
            self.enabled = False

        # Если анализатор включен, создаём LLM
        if self.enabled:
            self.llm = LLMFactory.get_llm(self.analyzer_model)
            default_logger.info(f"Анализатор инициализирован с моделью {self.analyzer_model}, категории: {[c['name'] for c in self.categories]}")
        else:
            default_logger.info("Анализатор отключён, будет использоваться fallback-логика")

    def _build_system_prompt(self) -> str:
        """Динамически строит системный промпт на основе конфигурации категорий."""
        categories_desc = "\n".join([
            f"- {cat['name']}: {cat['description']}" for cat in self.categories
        ])
        return f"""Ты — классификатор запросов. Определи, к какой из следующих категорий относится запрос пользователя.

Категории:
{categories_desc}

Ответь строго в формате JSON без пояснений:
{{
    "category": "название_категории"
}}

Выбери только одну категорию из списка. Если запрос не подходит ни под одну категорию, выбери категорию "default" (она должна быть в списке)."""

    def _get_fallback_category(self) -> Dict[str, Any]:
        """Возвращает категорию по умолчанию (первую в списке, или default, или None)."""
        # Ищем категорию с именем "default"
        for cat in self.categories:
            if cat.get("name") == "default":
                return cat
        # Если нет, берём первую
        return self.categories[0] if self.categories else None

    def analyze(self, query: str) -> Dict[str, Any]:
        """
        Возвращает словарь с выбранной категорией, содержащий поля:
        - name
        - temperature
        - model (может быть не задана, тогда нужно использовать глобальную)
        """
        if not self.enabled:
            fallback = self._get_fallback_category()
            if not fallback:
                default_logger.error("Нет доступных категорий для fallback")
                return {"name": "default", "temperature": 0.7, "model": None}
            return {
                "name": fallback["name"],
                "temperature": fallback.get("temperature", 0.7),
                "model": fallback.get("model")  # может быть None
            }

        system_prompt = self._build_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]

        try:
            response = self.llm.chat(messages, temperature=0.0)  # детерминированный ответ
            content = response.get("content", "")
            # Извлекаем JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            result = json.loads(content.strip())
            category_name = result.get("category")
            default_logger.info(f"Анализатор выбрал категорию: {category_name}")

            # Ищем категорию по имени
            selected = None
            for cat in self.categories:
                if cat["name"] == category_name:
                    selected = cat
                    break
            if not selected:
                default_logger.warning(f"Категория {category_name} не найдена в конфиге, используется fallback")
                selected = self._get_fallback_category()

            if selected:
                return {
                    "name": selected["name"],
                    "temperature": selected.get("temperature", 0.7),
                    "model": selected.get("model")  # может быть None
                }
            else:
                # Абсолютный fallback
                return {"name": "default", "temperature": 0.7, "model": None}
        except Exception as e:
            default_logger.error(f"Ошибка при анализе запроса: {e}")
            fallback = self._get_fallback_category()
            if fallback:
                return {
                    "name": fallback["name"],
                    "temperature": fallback.get("temperature", 0.7),
                    "model": fallback.get("model")
                }
            return {"name": "default", "temperature": 0.7, "model": None}