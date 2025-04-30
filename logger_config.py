import logging
from logging import handlers
from datetime import datetime
from pathlib import Path


# ── каталог для логов рядом с logger_config.py ────────────────────────────────
logs_dir = Path(__file__).resolve().parent / 'Logs'
logs_dir.mkdir(parents=True, exist_ok=True)        # создаём при необходимости
log_file = logs_dir / 'app.log'                    # <----- абсолютный путь

logger = logging.getLogger(__name__)
logger.setLevel("DEBUG")
console_handler = logging.StreamHandler()
console_handler.setLevel("INFO")
file_handler = handlers.TimedRotatingFileHandler(str(log_file), when='midnight', encoding="utf-8")
formatter = logging.Formatter("{asctime} - {filename} - {funcName} - {lineno} - {message}",
                              style="{",
                              datefmt="%Y-%m-%d %H:%M:%S", )

console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

logger.debug(f'Запуск Логгера {datetime.now()}!')
