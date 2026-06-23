"""Fábrica de provedores de Inteligência Artificial.

Seleciona o provedor conforme `AI_PROVIDER` (ou o nome passado). Imports
preguiçosos para que o `mock` funcione sem exigir SDKs/credenciais.
"""
from __future__ import annotations

from src.config.settings import settings
from src.services.intelligence.base import IntelligenceProvider
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_intelligence_provider(nome: str | None = None) -> IntelligenceProvider:
    """Retorna a instância do provedor de IA solicitado."""
    nome = (nome or settings.ai_provider).strip().lower()
    logger.debug("Selecionando provedor de IA: %s", nome)

    if nome in ("mock", "fake", "stub"):
        from src.services.intelligence.mock import MockIntelligenceProvider

        return MockIntelligenceProvider()
    if nome in ("claude", "anthropic"):
        from src.services.intelligence.claude import ClaudeProvider

        return ClaudeProvider()
    if nome in ("gemini", "google"):
        from src.services.intelligence.gemini import GeminiProvider

        return GeminiProvider()
    if nome == "openai":
        from src.services.intelligence.openai import OpenAIProvider

        return OpenAIProvider()

    raise ValueError(f"Provedor de IA desconhecido: {nome!r}")
