import logging
import sys


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure structured console logging for YAXIN AI without leaking PII."""
    logger = logging.getLogger("yaxin_ai")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


logger = setup_logging()

