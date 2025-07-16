import logging
import os
from datetime import datetime

def setup_logging(log_dir='logs', level=logging.INFO):
    os.makedirs(log_dir, exist_ok=True)

    # Generate filename with current date
    date_str = datetime.now().strftime('%Y-%m-%d')
    log_filename = f"app-{date_str}.log"
    full_log_path = os.path.join(log_dir, log_filename)

    logger = logging.getLogger()
    logger.setLevel(level)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    # File handler with dated filename
    file_handler = logging.FileHandler(full_log_path, mode='a', encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)  # Keep full logs in file

    # Avoid adding duplicate handlers
    if not logger.handlers:
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
