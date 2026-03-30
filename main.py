import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.agent import Agent
from core.interpreter import Interpreter
from core.planner import Planner
from core.executor import Executor
from core.router import Router
from core.context import ContextResolver

from memory.manager import MemoryManager
from llm.llm_manager import LLMManager
from tools.registry import ToolRegistry


DEBUG = False


def print_help():
    print("""
📋 Команды:

  помощь / help         — справка
  выход / exit          — выход

  undo / отмени         — откат действия
  history               — история действий

🧪 DEBUG:

  mem                   — runtime memory
  thread                — текущий диалог
  state                 — dump памяти
  last                  — last_file / last_folder
  debug on/off          — включить debug
""")


def main():

    global DEBUG

    print("🚀 Агент запущен\n")

    # =========================================================
    # INIT
    # =========================================================

    llm_manager = LLMManager()

    registry = ToolRegistry()
    registry.auto_register()

    print(f"🔧 tools: {registry.list_tools()}")

    # 🔥 MEMORY СОЗДАЁМ РАНЬШЕ
    memory = MemoryManager()

    interpreter = Interpreter(llm_manager)
    planner = Planner(memory)  # ✅ ФИКС
    router = Router()

    executor = Executor(
        tool_registry=registry,
        memory_manager=memory
    )

    context = ContextResolver(memory)

    agent = Agent(
        interpreter=interpreter,
        planner=planner,
        router=router,
        executor=executor,
        memory=memory,
        context=context
    )

    # =========================================================
    # LOOP
    # =========================================================

    while True:
        try:
            user_input = input("\n>> ").strip()

            if not user_input:
                continue

            cmd = user_input.lower()

            # =================================================
            # SYSTEM
            # =================================================

            if cmd in ["exit", "quit", "выход", "стоп", "пока"]:
                print("👋 Пока")
                break

            if cmd in ["help", "помощь", "?"]:
                print_help()
                continue

            # =================================================
            # DEBUG
            # =================================================

            if cmd == "debug on":
                DEBUG = True
                print("🧪 DEBUG ON")
                continue

            if cmd == "debug off":
                DEBUG = False
                print("🧪 DEBUG OFF")
                continue

            if cmd == "mem":
                print("\n🧠 MEMORY STATE:")
                print(memory.state)
                continue

            if cmd == "state":
                print("\n🧠 FULL STATE:")
                print(memory.dump_state())
                continue

            if cmd == "thread":
                print("\n🧵 THREAD:")
                for msg in memory.get_thread():
                    print(f"{msg['role']}: {msg['content']}")
                continue

            if cmd == "last":
                print("\n📂 LAST:")
                print("file:", memory.get_last_file())
                print("folder:", memory.get_last_folder())
                continue

            # =================================================
            # ACTIONS
            # =================================================

            if cmd in ["undo", "отмени"]:
                result = executor.undo_last()
                print(result)
                continue

            if cmd in ["history"]:
                if executor.history:
                    history = executor.history.get_recent_actions(10)
                    print(history)
                else:
                    print("История отключена")
                continue

            # =================================================
            # AGENT
            # =================================================

            result = agent.handle_input(user_input)

            if DEBUG:
                print("\n🧪 RAW RESULT:", result)

            # -------------------------
            # OUTPUT
            # -------------------------

            if isinstance(result, dict):

                if result.get("status") == "need_clarification":
                    print("\n🤖 Выбери вариант:")
                    for i, option in enumerate(result.get("options", []), 1):
                        print(f"{i}. {option}")

                elif result.get("status") == "success":
                    print("\n🤖 OK")
                    print(result.get("data"))

                elif result.get("status") == "cancelled":
                    print("\n⚠️ Отменено")

                else:
                    print("\n❌", result.get("error"))

            else:
                print("\n🤖", result)

        except KeyboardInterrupt:
            print("\n👋 Выход")
            break

        except Exception as e:
            print("\n❌ ERROR:", e)


if __name__ == "__main__":
    main() 