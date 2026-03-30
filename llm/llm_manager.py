import time
import ollama
from typing import Optional, Dict, Any

from utils.logger import setup_logger

logger = setup_logger("LLMManager")


class LLMError(Exception):
    """Базовое исключение для LLM ошибок."""
    pass


class OllamaConnectionError(LLMError):
    """Ollama не запущена или недоступна."""
    pass


class OllamaModel:
    def __init__(self, model_name: str, max_retries: int = 3, base_delay: float = 1.0):
        self.model_name = model_name
        self.max_retries = max_retries
        self.base_delay = base_delay  # секунды между попытками
        
        # Проверяем доступность модели при инициализации
        self._check_availability()

    def _check_availability(self) -> bool:
        """Проверяет, доступна ли Ollama и существует ли модель."""
        try:
            # Пробуем получить список моделей
            ollama.list()
            logger.info(f"Ollama connection OK, model: {self.model_name}")
            return True
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            logger.info("Make sure Ollama is running: ollama serve")
            return False

    def generate(self, prompt: Dict[str, str]) -> Optional[str]:
        """
        Генерация с retry logic и exponential backoff.
        
        Args:
            prompt: {"system": "...", "user": "..."}
            
        Returns:
            Текст ответа или None при ошибке
        """
        messages = [
            {"role": "system", "content": prompt.get("system", "")},
            {"role": "user", "content": prompt.get("user", "")}
        ]

        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Ollama call attempt {attempt + 1}/{self.max_retries}")
                
                response = ollama.chat(
                    model=self.model_name,
                    messages=messages,
                    options={
                        "temperature": 0.3,  # Низкая температура для стабильности JSON
                        "num_predict": 500,   # Ограничиваем длину ответа
                    }
                )
                
                content = response.get("message", {}).get("content")
                
                if content:
                    logger.debug(f"Ollama response received, length: {len(content)}")
                    return content.strip()
                else:
                    logger.warning("Empty response from Ollama")
                    
            except ollama.ResponseError as e:
                last_error = e
                logger.warning(f"Ollama response error (attempt {attempt + 1}): {e}")
                
                # Если модель не найдена - не retry, сразу ошибка
                if "not found" in str(e).lower():
                    logger.error(f"Model '{self.model_name}' not found. Run: ollama pull {self.model_name}")
                    return None
                    
            except Exception as e:
                last_error = e
                logger.warning(f"Ollama error (attempt {attempt + 1}): {e}")
                
                # Проверяем, запущена ли Ollama
                if "connection" in str(e).lower():
                    logger.error("Cannot connect to Ollama. Is 'ollama serve' running?")
                    # Не retry при connection error
                    return None

            # Exponential backoff перед следующей попыткой
            if attempt < self.max_retries - 1:
                delay = self.base_delay * (2 ** attempt)  # 1s, 2s, 4s
                logger.info(f"Retrying in {delay}s...")
                time.sleep(delay)

        # Все попытки исчерпаны
        logger.error(f"All {self.max_retries} attempts failed. Last error: {last_error}")
        return None

    def is_available(self) -> bool:
        """Проверяет доступность модели без генерации."""
        try:
            ollama.show(self.model_name)
            return True
        except:
            return False


class LLMManager:
    def __init__(self):
        self.models: Dict[str, OllamaModel] = {}
        
        # Инициализируем модели с обработкой ошибок
        try:
            self.models["interpreter"] = OllamaModel("llama3")
            logger.info("Interpreter model (llama3) initialized")
        except Exception as e:
            logger.error(f"Failed to init interpreter model: {e}")
            self.models["interpreter"] = None
            
        try:
            self.models["chat"] = OllamaModel("llama3.1")
            logger.info("Chat model (llama3.1) initialized")
        except Exception as e:
            logger.error(f"Failed to init chat model: {e}")
            self.models["chat"] = None

    def get_model(self, name: str) -> Optional[OllamaModel]:
        """
        Получает модель по имени.
        
        Returns:
            OllamaModel или None если модель не инициализирована
        """
        model = self.models.get(name)
        
        if not model:
            logger.error(f"Model '{name}' not found in registry")
            return None
            
        # Дополнительная проверка доступности
        if not model.is_available():
            logger.error(f"Model '{name}' is not available (Ollama down?)")
            return None
            
        return model

    def list_available_models(self) -> Dict[str, bool]:
        """Возвращает статус всех моделей."""
        return {
            name: (model.is_available() if model else False)
            for name, model in self.models.items()
        }

    def health_check(self) -> bool:
        """Проверяет, работает ли хотя бы одна модель."""
        return any(
            model and model.is_available()
            for model in self.models.values()
        )
