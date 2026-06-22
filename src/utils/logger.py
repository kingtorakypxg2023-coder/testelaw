"""Configuração centralizada de logging para a aplicação."""
from __future__ import annotations

import logging
import sys

from src.config.settings import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    """Cria/recupera um logger já configurado com o nível definido em settings.

    Args:
        name: Nome do logger (use `__name__` no módulo chamador).

    Returns:
        Instância de `logging.Logger` pronta para uso.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(settings.log_level.upper())
        logger.propagate = False
    return logger
