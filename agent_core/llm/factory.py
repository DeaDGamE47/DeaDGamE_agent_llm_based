# agent_core/llm/factory.py
from .ollama_llm import OllamaLLM
from ..logger import default_logger

class LLMFactory:
    """
    Фабрика для создания и кэширования экземпляров LLM.
    """
    _instances = {}   # словарь для хранения созданных объектов

    @classmethod
    def get_llm(cls, model_name: str, **kwargs) -> object:
        """
        Возвращает экземпляр LLM для указанной модели.
        Если экземпляр уже был создан, возвращает его из кэша.
        """
        if model_name not in cls._instances:
            default_logger.info(f"Создание нового экземпляра LLM для модели {model_name}")
            # В текущей реализации все модели запускаются через Ollama.
            # В будущем здесь можно добавить логику выбора класса по префиксу
            cls._instances[model_name] = OllamaLLM(model_name, **kwargs)
        else:
            default_logger.debug(f"Возврат существующего экземпляра LLM для модели {model_name}")
        return cls._instances[model_name]