from loguru import logger


def log_critical_and_raise(e: Exception):
    logger.critical(e)
    raise e
