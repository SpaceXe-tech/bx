import logging
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler(
            "log.txt",
            maxBytes=5 * 1024 * 1024,  # 5 MB per file
            backupCount=3,  # Keep up to 3 backup files
            encoding='utf-8'
        ),
        logging.StreamHandler(),
    ],
)

logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)

def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
