import logging
import os
from datetime import datetime

LOG_DIR = "logs"


def _cleanup_old_logs():
    files = [
        os.path.join(LOG_DIR, f)
        for f in os.listdir(LOG_DIR)
        if f.endswith(".txt")
    ]

    files.sort(key=os.path.getctime)

    while len(files) > 5:
        old_file = files.pop(0)
        try:
            os.remove(old_file)
        except Exception:
            pass


def setup_logger(name: str):
    os.makedirs(LOG_DIR, exist_ok=True)

    # 🔥 один файл на запуск (глобальный)
    if not hasattr(setup_logger, "log_file"):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        setup_logger.log_file = os.path.join(LOG_DIR, f"run_{timestamp}.txt")

        _cleanup_old_logs()

    log_file = setup_logger.log_file

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # -------------------------
    # 🔥 УДАЛЯЕМ старые handlers
    # -------------------------
    if logger.hasHandlers():
        logger.handlers.clear()

    # -------------------------
    # 📄 FILE HANDLER
    # -------------------------
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    # -------------------------
    # 🖥️ CONSOLE HANDLER
    # -------------------------
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger