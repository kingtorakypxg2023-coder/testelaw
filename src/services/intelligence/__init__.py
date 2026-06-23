"""Etapa 2 - INTELIGÊNCIA ARTIFICIAL.

Envio do texto bruto das publicações para um modelo de linguagem
(Claude / Gemini / OpenAI) e extração de prazos e ações em JSON estruturado.
A **data fatal** é calculada em código (dias úteis - CPC), não pela IA.
Saída: objetos `AnalisePublicacao`.

Uso típico::

    from src.services.intelligence import get_intelligence_provider

    ia = get_intelligence_provider()            # conforme AI_PROVIDER
    analises = ia.analisar_varias(publicacoes)
"""
from src.services.intelligence.base import IntelligenceError, IntelligenceProvider
from src.services.intelligence.factory import get_intelligence_provider

__all__ = [
    "IntelligenceError",
    "IntelligenceProvider",
    "get_intelligence_provider",
]
