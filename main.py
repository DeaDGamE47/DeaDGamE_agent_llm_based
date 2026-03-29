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
from llm.manager import LLMManager
from tools.registry import ToolRegistry


def main():
    print("🚀 Агент запущен\n")

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

            if user_input.lower() in ["exit", "quit", "выход", "стоп"]:
                print("👋 Завершение работы")
                break

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
                    print(f"\n🤖 {result.get('data')}")

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