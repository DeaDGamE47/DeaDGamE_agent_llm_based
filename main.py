import sys
import os

# чтобы корректно работали импорты
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.agent import Agent
from core.interpreter import Interpreter
from core.planner import Planner
from core.executor import Executor
from core.router import Router
from core.context import ContextResolver

from memory.manager import Memory
from llm.llm_manager import LLMManager
from tools.registry import ToolRegistry


def print_help():
    """Выводит справку по командам."""
    print("""
📋 Доступные команды:
   отмени, undo     — отменить последнее действие
   история, history — показать историю действий
   помощь, help     — показать эту справку
   выход, exit      — завершить работу
""")


def format_history(actions: list) -> str:
    """Форматирует историю для вывода."""
    if not actions:
        return "История пуста"
    
    lines = ["\n📜 Последние действия:"]
    for i, action in enumerate(actions, 1):
        tool = action.get("tool_name", "unknown")
        status = "✅" if action.get("result_status") == "success" else "❌"
        timestamp = action.get("timestamp", "")[11:19]  # только время
        lines.append(f"  {i}. [{timestamp}] {status} {tool}")
    
    return "\n".join(lines)


def main():
    print("🚀 Агент запущен\n")
    print("Введите 'помощь' для списка команд")

    # =========================================================
    # 🔧 INIT
    # =========================================================

    llm_manager = LLMManager()

    # tools
    registry = ToolRegistry()
    registry.auto_register()

    print(f"🔧 Загруженные tools: {registry.list_tools()}")

    # core
    interpreter = Interpreter(llm_manager)
    planner = Planner()
    router = Router()
    executor = Executor(tool_registry=registry)

    # memory + context
    memory = Memory()
    context = ContextResolver(memory)

    # agent
    agent = Agent(
        interpreter=interpreter,
        planner=planner,
        router=router,
        executor=executor,
        memory=memory,
        context=context
    )

    # =========================================================
    # 🔄 LOOP
    # =========================================================

    while True:
        try:
            user_input = input("\n>> ").strip()

            if not user_input:
                continue

            # -------------------------
            # 🔥 SYSTEM COMMANDS
            # -------------------------
            cmd = user_input.lower()

            if cmd in ["exit", "quit", "выход", "стоп"]:
                print("👋 Завершение работы")
                break

            if cmd in ["помощь", "help", "?"]:
                print_help()
                continue

            if cmd in ["отмени", "undo", "откат"]:
                # Прямой вызов undo через executor
                undo_result = executor.undo_last()
                
                if undo_result.get("status") == "success":
                    print(f"\n✅ {undo_result.get('data')}")
                else:
                    print(f"\n❌ Не удалось отменить: {undo_result.get('error')}")
                continue

            if cmd in ["история", "history", "лог"]:
                # Показываем последние 10 действий
                history = executor.get_history(limit=10)
                print(format_history(history))
                continue

            # -------------------------
            # 🔥 AGENT PROCESSING
            # -------------------------
            result = agent.handle_input(user_input)

            # -------------------------
            # 🔥 OUTPUT FORMAT
            # -------------------------
            if isinstance(result, dict):
                if result.get("status") == "need_clarification":
                    print("\n🤖 Выбери вариант:")
                    for i, option in enumerate(result.get("options", []), 1):
                        print(f"{i}. {option}")

                elif result.get("status") == "success":
                    data = result.get("data")
                    actions_count = result.get("actions_count", 0)
                    
                    # Форматируем вывод в зависимости от типа данных
                    if isinstance(data, dict):
                        # Множественный результат (контекст)
                        print(f"\n🤖 Выполнено действий: {actions_count}")
                        for key, value in data.items():
                            print(f"  • {key}: {value}")
                    else:
                        # Простой результат
                        print(f"\n🤖 {data}")
                    
                    # Подсказка про undo для write-операций
                    if actions_count > 0:
                        print(f"\n💡 Введите 'отмени' чтобы откатить")

                elif result.get("status") == "cancelled":
                    print(f"\n⚠️ {result.get('data')}")

                else:
                    print(f"\n❌ {result.get('error')}")

            else:
                print(f"\n🤖 {result}")

        except KeyboardInterrupt:
            print("\n👋 Прервано пользователем")
            break

        except Exception as e:
            print(f"\n❌ Ошибка: {e}")


if __name__ == "__main__":
    main()
