import ollama

from utils.logger import setup_logger

logger = setup_logger("LLMManager")


class OllamaModel:
    def __init__(self, model_name):
        self.model_name = model_name

    def generate(self, prompt: dict):
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": prompt.get("system", "")},
                    {"role": "user", "content": prompt.get("user", "")}
                ]
            )

            return response["message"]["content"]

        except Exception as e:
            logger.exception("LLM error")
            return None


class LLMManager:
    def __init__(self):
        self.models = {
            "interpreter": OllamaModel("llama3"),
            "chat": OllamaModel("llama3.1")  # 🔥 более мощная модель
        }

    def get_model(self, name):
        model = self.models.get(name)

        if not model:
            logger.error(f"Model not found: {name}")

        return model