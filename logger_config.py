import logging
from logging import handlers
from datetime import datetime


# def show_only_debug(record):
#     return record.levelname == "DEBUG"


logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")
console_handler = logging.StreamHandler()
console_handler.setLevel("INFO")
file_handler = handlers.TimedRotatingFileHandler("Logs/app.log", when='midnight', encoding="utf-8")

formatter = logging.Formatter("{asctime} - {filename} - {funcName} - {lineno} - {message}",
                              style="{",
                              datefmt="%Y-%m-%d %H:%M:%S", )

console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

logger.debug(f'Запуск Логгера {datetime.now()}!')
