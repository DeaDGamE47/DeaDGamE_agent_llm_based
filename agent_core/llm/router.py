# agent_core/router.py
from typing import Dict, Any
from ..logger import default_logger

class ModelRouter:
    def __init__(self, config: Dict[str, Any], analyzer):
        self.config = config
        self.analyzer = analyzer
        self.default_model = config.get("llm", {}).get("default", "qwen2.5:14b")
        self.coding_model = config.get("llm", {}).get("coding", self.default_model)

    def choose_model_and_temperature(self, user_input: str) -> tuple:
        """Возвращает (имя_модели, температура)."""
        # Получаем категорию от анализатора
        category = self.analyzer.analyze(user_input)
        category_name = category["name"]
        temperature = category["temperature"]

        # Если для категории указана конкретная модель, используем её, иначе ищем по имени
        if category.get("model"):
            model_name = category["model"]
        else:
            # fallback: для категорий "coding" используем coding_model, иначе default
            if category_name == "coding":
                model_name = self.coding_model
            else:
                model_name = self.default_model

        default_logger.info(f"Роутинг: категория={category_name}, модель={model_name}, temp={temperature}")
        return model_name, temperature