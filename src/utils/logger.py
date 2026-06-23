"""Configuração centralizada de logging.

Os handlers ficam no logger *raiz*, e cada módulo usa `get_logger(__name__)`
com propagação ativa — assim a GUI pode anexar seu próprio handler ao raiz e
capturar tudo. Em modo janela (executável sem console), `sys.stdout` é `None`;
nesse caso nenhum handler de stream é adicionado (a GUI cuida da exibição).
"""
from __future__ import annotations

import logging
import sys

from src.config.settings import settings

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

_root_configurado = False


def _configurar_root() -> None:
    global _root_configurado
    if _root_configurado:
        return
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    if sys.stdout is not None:  # em app de janela (windowed) não há stdout
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(handler)
    _root_configurado = True


def get_logger(name: str) -> logging.Logger:
    """Retorna um logger que propaga para o raiz já configurado."""
    _configurar_root()
    return logging.getLogger(name)
