import requests
from typing import List, Dict, Optional, Any
from .base import BaseLLM
from ..logger import default_logger  # <-- относительный импорт логгера

class OllamaLLM(BaseLLM):
    """
    Реализация LLM через локальный сервер Ollama.
    """
    def __init__(self, model: str, base_url: str = "http://localhost:11434"):
        self.model = model          # имя модели (например, "qwen2.5:14b")
        self.base_url = base_url    # адрес сервера Ollama
        default_logger.info(f"Инициализация OllamaLLM для модели {model} (URL: {base_url})")

    def chat(self, messages: List[Dict[str, str]], 
             tools: Optional[List[Dict]] = None,
             **kwargs) -> Dict[str, Any]:
        # Извлекаем temperature из kwargs, по умолчанию 0.7
        temperature = kwargs.get("temperature", 0.7)

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        if tools:
            payload["tools"] = tools   # если есть инструменты, добавляем их

        try:
            url = f"{self.base_url}/api/chat"
            default_logger.debug(f"Отправка запроса к Ollama: {url}, модель: {self.model}")
            # Отправляем POST-запрос к Ollama
            response = requests.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()   # вызовет исключение при HTTP-ошибке
            data = response.json()        # парсим JSON-ответ
            default_logger.debug(f"Получен ответ от Ollama: {data}")
            # В ответе Ollama: {"message": {"content": "...", "tool_calls": [...]}}
            return data["message"]        # возвращаем именно словарь сообщения
        except Exception as e:
            # В случае ошибки возвращаем сообщение об ошибке как обычный текст
            error_msg = f"Ошибка при обращении к LLM: {e}"
            default_logger.error(error_msg)
            return {"content": error_msg}