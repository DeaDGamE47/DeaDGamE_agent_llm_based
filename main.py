import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.agent import Agent
from core.interpreter import Interpreter
from core.planner import Planner
from core.executor import Executor
from core.router import Router
from core.context import ContextResolver

from memory.memory_manager import MemoryManager
from llm.llm_manager import LLMManager
from tools.registry import ToolRegistry

DEBUG = False


def print_help():
    print("""
📋 Команды:

 помощь / help — справка
 выход / exit — выход

 undo / отмени — откат последнего действия
 redo / повтори — повтор отменённого действия
 history — история действий (undo/redo)
 status — статус агента

🧪 DEBUG:

 mem — runtime memory
 thread — текущий диалог
 state — dump памяти
 last — last_file / last_folder
 debug on/off — включить debug
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

    # 🔥 MEMORY — создаём раньше всех
    memory = MemoryManager()

    interpreter = Interpreter(llm_manager)
    planner = Planner()  
    router = Router()

    # 🔥 EXECUTOR — тупой, только tool_registry
    executor = Executor(tool_registry=registry)

    context = ContextResolver(memory)

    # 🔥 AGENT — управляет всей памятью и undo/redo
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
            # UNDO / REDO
            # =================================================

            if cmd in ["undo", "отмени"]:
                result = agent.undo()
                if result["status"] == "success":
                    print(f"\n🤖 {result['message']}")
                else:
                    print(f"\n⚠️ {result['message']}")
                continue

            if cmd in ["redo", "повтори"]:
                result = agent.redo()
                if result["status"] == "success":
                    print(f"\n🤖 {result['message']}")
                else:
                    print(f"\n⚠️ {result['message']}")
                continue

            # =================================================
            # STATUS / HISTORY
            # =================================================

            if cmd in ["status", "статус"]:
                status = agent.get_status()
                print("\n📊 Статус агента:")
                print(f"   Undo доступно: {status['can_undo']} ({status['undo_count']})")
                print(f"   Redo доступно: {status['can_redo']} ({status['redo_count']})")
                print(f"   Ожидание выбора: {status['pending_selection']}")
                print(f"   Entities: {status['entities']}")
                continue

            if cmd in ["history", "история"]:
                history_status = memory.get_history_status()
                print("\n📜 История действий:")
                print(f"   Undo: {history_status['undo_count']} действий")
                print(f"   Redo: {history_status['redo_count']} действий")
                if history_status['last_actions']:
                    print("   Последние действия:")
                    for i, action in enumerate(reversed(history_status['last_actions']), 1):
                        print(f"      {i}. {action['tool_name']}")
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
                    print(f"  {msg['role']}: {str(msg['content'])[:100]}...")
                continue

            if cmd == "last":
                print("\n📂 LAST:")
                print(f"   file: {memory.get_last_file()}")
                print(f"   folder: {memory.get_last_folder()}")
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
                        print(f"   {i}. {option}")

                elif result.get("status") == "success":
                    print("\n🤖 OK")
                    data = result.get("data")
                    if data:
                        for key, value in data.items():
                            print(f"   {key}: {value}")

                elif result.get("status") == "cancelled":
                    print("\n⚠️ Отменено")

                elif result.get("status") == "undo":
                    print(f"\n↩️ {result.get('message')}")

                elif result.get("status") == "redo":
                    print(f"\n↪️ {result.get('message')}")

                else:
                    print("\n❌", result.get("error", "Неизвестная ошибка"))

            else:
                print("\n🤖", result)

        except KeyboardInterrupt:
            print("\n👋 Выход")
            break

        except Exception as e:
            print("\n❌ ERROR:", e)
            if DEBUG:
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    main()
