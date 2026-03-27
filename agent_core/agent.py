# agent_core/analyzer.py
import json
import hashlib
import time
from typing import Dict, Any, List, Optional
from collections import defaultdict
from .llm.factory import LLMFactory
from .logger import default_logger

class CategoryRouter:
    """
    Анализирует запрос с помощью LLM и выбирает подходящую категорию из конфига.
    Поддерживает кэширование результатов и сбор метрик.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.analyzer_config = config.get("analyzer", {})
        self.enabled = self.analyzer_config.get("enabled", True)
        self.analyzer_model = self.analyzer_config.get("model", "llama3.2:1b")
        self.categories = self.analyzer_config.get("categories", [])

        # Кэш: ключ = хеш запроса, значение = результат анализа (словарь)
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_hits = 0
        self.cache_misses = 0

        # Метрики: сколько запросов попало в каждую категорию
        self.metrics: Dict[str, int] = defaultdict(int)

        if not self.categories:
            default_logger.warning("Категории для анализатора не заданы, будет использоваться fallback-логика")
            self.enabled = False

        # Если анализатор включен, создаём LLM
        if self.enabled:
            self.llm = LLMFactory.get_llm(self.analyzer_model)
            default_logger.info(f"Анализатор инициализирован с моделью {self.analyzer_model}, категории: {[c['name'] for c in self.categories]}")
        else:
            default_logger.info("Анализатор отключён, будет использоваться fallback-логика")

    def _get_cache_key(self, query: str) -> str:
        """Генерирует ключ кэша на основе запроса (хеш)."""
        return hashlib.md5(query.encode('utf-8')).hexdigest()

    def _save_metrics(self):
        """Сохраняет метрики в файл (опционально, можно вызывать при завершении или периодически)."""
        metrics_file = "data/analyzer_metrics.json"
        try:
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(dict(self.metrics), f, indent=2, ensure_ascii=False)
            default_logger.debug(f"Метрики сохранены в {metrics_file}")
        except Exception as e:
            default_logger.error(f"Не удалось сохранить метрики: {e}")

    def _update_metrics(self, category_name: str):
        """Увеличивает счётчик для категории."""
        self.metrics[category_name] += 1
        # Можно также сохранять метрики периодически, но пока будем просто обновлять счётчики

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

    def _get_fallback_category(self) -> Optional[Dict[str, Any]]:
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
            self._update_metrics(fallback["name"])
            return {
                "name": fallback["name"],
                "temperature": fallback.get("temperature", 0.7),
                "model": fallback.get("model")  # может быть None
            }

        # Проверяем кэш
        cache_key = self._get_cache_key(query)
        if cache_key in self.cache:
            self.cache_hits += 1
            default_logger.debug(f"Анализатор: cache hit для запроса '{query[:50]}...'")
            result = self.cache[cache_key]
            self._update_metrics(result["name"])
            return result

        self.cache_misses += 1
        default_logger.debug(f"Анализатор: cache miss для запроса '{query[:50]}...'")

        system_prompt = self._build_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]

        try:
            start_time = time.time()
            response = self.llm.chat(messages, temperature=0.0)  # детерминированный ответ
            elapsed = time.time() - start_time
            content = response.get("content", "")
            # Извлекаем JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            result = json.loads(content.strip())
            category_name = result.get("category")
            default_logger.info(f"Анализатор выбрал категорию: {category_name} (за {elapsed:.2f}с)")

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
                result_dict = {
                    "name": selected["name"],
                    "temperature": selected.get("temperature", 0.7),
                    "model": selected.get("model")
                }
            else:
                # Абсолютный fallback
                result_dict = {"name": "default", "temperature": 0.7, "model": None}

            # Сохраняем в кэш
            self.cache[cache_key] = result_dict
            self._update_metrics(result_dict["name"])

            # Логируем статистику кэша
            default_logger.debug(f"Кэш анализатора: hits={self.cache_hits}, misses={self.cache_misses}, size={len(self.cache)}")
            return result_dict

        except Exception as e:
            default_logger.error(f"Ошибка при анализе запроса: {e}")
            fallback = self._get_fallback_category()
            if fallback:
                result_dict = {
                    "name": fallback["name"],
                    "temperature": fallback.get("temperature", 0.7),
                    "model": fallback.get("model")
                }
            else:
                result_dict = {"name": "default", "temperature": 0.7, "model": None}
            self._update_metrics(result_dict["name"])
            return result_dict

    def get_metrics(self) -> Dict[str, int]:
        """Возвращает текущие метрики."""
        return dict(self.metrics)

    def get_cache_stats(self) -> Dict[str, int]:
        """Возвращает статистику кэша."""
        return {"hits": self.cache_hits, "misses": self.cache_misses, "size": len(self.cache)}

    def save_metrics(self):
        """Сохраняет метрики в файл."""
        self._save_metrics()