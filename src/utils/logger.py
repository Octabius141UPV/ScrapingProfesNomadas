import logging

def setup_logger(name: str = 'scraper', level: int = logging.INFO) -> logging.Logger:
    """
    Configura y devuelve un logger básico que imprime en consola.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger 