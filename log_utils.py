import os
import logging

def setup_logger(name, log_file):
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

    file_handler = logging.FileHandler(os.path.join("logs", log_file), encoding='utf-8')
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.handlers.clear()  # Avoid duplicate handlers
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger
