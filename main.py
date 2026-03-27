# main.py
import atexit
from agent_core.agent import Agent
from agent_core.logger import default_logger

agent = None

def save_metrics():
    """Сохраняет метрики анализатора перед выходом."""
    if agent and hasattr(agent, 'analyzer'):
        agent.analyzer.save_metrics()
        default_logger.info("Метрики анализатора сохранены.")
        stats = agent.analyzer.get_cache_stats()
        default_logger.info(f"Статистика кэша: хиты={stats['hits']}, промахи={stats['misses']}, размер={stats['size']}")

def main():
    global agent
    atexit.register(save_metrics)

    agent = Agent()
    default_logger.info("Агент запущен (консольный режим). Введите 'exit' для выхода.")

    while True:
        try:
            user_input = input("\nВы: ")
            if user_input.lower() == "exit":
                break
            response = agent.process(user_input)
            print(f"Агент: {response}")
        except KeyboardInterrupt:
            default_logger.info("Прерывание работы (Ctrl+C)")
            break
        except Exception as e:
            default_logger.exception("Необработанная ошибка")
            print(f"Ошибка: {e}")

if __name__ == "__main__":
    main()