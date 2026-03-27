# agent_core/logger.py
import logging
import os
from datetime import datetime

def setup_logger(name: str = "ai_agent", log_dir: str = "logs") -> logging.Logger:
    """
    Настраивает и возвращает логгер с указанным именем.
    Логи пишутся в файл и в консоль.
    """
    # Создаём папку для логов, если её нет
    os.makedirs(log_dir, exist_ok=True)

    # Имя файла лога с датой (например, ai_agent_2025-03-27.log)
    log_filename = os.path.join(log_dir, f"{name}_{datetime.now().strftime('%Y-%m-%d')}.log")

    # Создаём логгер
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Уровень логирования: DEBUG, INFO, WARNING, ERROR, CRITICAL

    # Формат сообщений: время, уровень, имя логгера, сообщение
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Обработчик для записи в файл
    file_handler = logging.FileHandler(log_filename, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)   # В консоль выводим только INFO и выше, чтобы не засорять
    console_handler.setFormatter(formatter)

    # Добавляем обработчики к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Создаём экземпляр логгера по умолчанию для использования в других модулях
default_logger = setup_logger()