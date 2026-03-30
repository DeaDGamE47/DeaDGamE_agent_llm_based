from utils.logger import setup_logger

logger = setup_logger("Agent")


class Agent:

    def __init__(self, interpreter, planner, router, executor, memory, context):
        self.interpreter = interpreter
        self.planner = planner
        self.router = router
        self.executor = executor
        self.memory = memory
        self.context = context

        self.pending_options = None
        self.pending_plan = None

    # =========================================================
    # MAIN
    # =========================================================
    def handle_input(self, user_input):
        logger.info(f"USER INPUT: {user_input}")

        # -------------------------
        # 🔥 ОБРАБОТКА ВЫБОРА
        # -------------------------
        if self.pending_options:

            if user_input.isdigit():
                idx = int(user_input) - 1

                if 0 <= idx < len(self.pending_options):
                    selected = self.pending_options[idx]
                    logger.debug(f"OPTION SELECTED: {selected}")

                    result = self.executor.execute(
                        self.pending_plan,
                        selected_option=selected
                    )

                    self.pending_options = None
                    self.pending_plan = None

                    # 🔥 NEW: Обновляем память после выполнения выбора
                    self._update_interpreter_memory(result, selected)

                    return result

            return "❌ Неверный выбор"

        # -------------------------
        # 🔥 PIPELINE
        # -------------------------
        interpreted = self.interpreter.interpret(user_input)

        interpreted = self.context.resolve(interpreted)

        plan = self.planner.build_plan(interpreted)

        if not plan:
            return "❌ План не построен"

        plan = self.router.route(plan)

        result = self.executor.execute(plan)

        # -------------------------
        # 🔥 MULTIPLE
        # -------------------------
        if result.get("status") == "need_clarification":
            self.pending_options = result["options"]
            self.pending_plan = plan

            return {
                "status": "need_clarification",
                "options": result["options"]
            }

        # 🔥 NEW: Обновляем память Interpreter после успешного выполнения
        self._update_interpreter_memory(result, None)

        # Обновляем общую память
        self.memory.update_entities(interpreted.get("entities", {}))

        return result

    def _update_interpreter_memory(self, result, selected_path=None):
        """
        Извлекает пути из результата и обновляет interpreter.last_folder/last_file.
        """
        if result.get("status") != "success":
            return

        data = result.get("data", {})

        # Если был выбор — используем selected_path
        if selected_path:
            # Определяем файл или папка
            if isinstance(selected_path, str):
                if selected_path.endswith(('/', '\\')) or '.' not in selected_path.split('/')[-1].split('\\')[-1]:
                    self.interpreter.last_folder = selected_path.rstrip('/\\')
                    logger.debug(f"AGENT MEMORY: last_folder = {self.interpreter.last_folder}")
                else:
                    self.interpreter.last_file = selected_path
                    self.interpreter.last_folder = selected_path.rsplit('/', 1)[0].rsplit('\\', 1)[0]
                    logger.debug(f"AGENT MEMORY: last_file = {self.interpreter.last_file}, last_folder = {self.interpreter.last_folder}")
            return

        # Извлекаем из data (может быть dict или строка)
        if isinstance(data, dict):
            # Проверяем common keys
            for key in ["path", "folder_path", "file_path"]:
                if key in data and data[key]:
                    path = data[key]
                    if isinstance(path, str):
                        if key == "folder_path" or (key == "path" and not path.endswith(('.txt', '.py', '.json', '.md', '.docx'))):
                            self.interpreter.last_folder = path.rstrip('/\\')
                            logger.debug(f"AGENT MEMORY: last_folder = {self.interpreter.last_folder}")
                        else:
                            self.interpreter.last_file = path
                            # Извлекаем папку из пути файла
                            folder = path.rsplit('/', 1)[0].rsplit('\\', 1)[0] if '/' in path or '\\' in path else ""
                            if folder:
                                self.interpreter.last_folder = folder
                            logger.debug(f"AGENT MEMORY: last_file = {self.interpreter.last_file}, last_folder = {self.interpreter.last_folder}")
                        break

        elif isinstance(data, str):
            # Простая строка — путь
            if data:
                # Проверяем по расширению
                ext = data.split('.')[-1].lower() if '.' in data else ''
                if ext in ['txt', 'py', 'json', 'md', 'docx', 'pdf']:
                    self.interpreter.last_file = data
                    folder = data.rsplit('/', 1)[0].rsplit('\\', 1)[0] if '/' in data or '\\' in data else ""
                    if folder:
                        self.interpreter.last_folder = folder
                    logger.debug(f"AGENT MEMORY: last_file = {data}, last_folder = {self.interpreter.last_folder}")
                else:
                    self.interpreter.last_folder = data.rstrip('/\\')
                    logger.debug(f"AGENT MEMORY: last_folder = {data}")