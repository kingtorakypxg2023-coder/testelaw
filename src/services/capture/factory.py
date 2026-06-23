"""Fábrica de provedores de captura.

Seleciona a implementação de `CaptureProvider` conforme a configuração
`CAPTURE_PROVIDER` (ou o nome passado explicitamente). Os imports são
preguiçosos para que o provedor `mock` funcione sem exigir credenciais.
"""
from __future__ import annotations

from src.config.settings import settings
from src.services.capture.base import CaptureProvider
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_capture_provider(nome: str | None = None) -> CaptureProvider:
    """Retorna a instância do provedor de captura solicitado."""
    nome = (nome or settings.capture_provider).strip().lower()
    logger.debug("Selecionando provedor de captura: %s", nome)

    if nome in ("mock", "fake", "stub"):
        from src.services.capture.mock import MockCaptureProvider

        return MockCaptureProvider()
    if nome == "jusbrasil":
        from src.services.capture.jusbrasil import JusbrasilClient

        return JusbrasilClient()
    if nome == "escavador":
        raise NotImplementedError(
            "Provedor 'escavador' ainda não implementado (planejado no roadmap)."
        )

    raise ValueError(f"Provedor de captura desconhecido: {nome!r}")
