from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any

class BaseLLM(ABC):
    """
    Абстрактный базовый класс для всех реализаций LLM.
    Любая модель (Ollama, OpenAI, llama.cpp) должна наследовать этот класс
    и реализовать метод chat().
    """
    
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], 
             tools: Optional[List[Dict]] = None,
             **kwargs) -> Dict[str, Any]:
        """
        Отправляет сообщения модели.
        Параметры генерации (temperature, top_p и т.д.) передаются через kwargs.
        
        Параметры:
            messages: список сообщений, каждое содержит "role" и "content".
            tools: опциональный список описаний инструментов (для function calling).
        
        Возвращает:
            Словарь, который всегда содержит ключ "content" (текст ответа)
            и может содержать "tool_calls" (если модель вызвала инструмент).
        """
        pass