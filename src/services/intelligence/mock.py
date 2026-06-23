"""Provedor de IA *mock* para desenvolvimento e testes.

Extrai prazos por heurística (regex) sobre o texto, sem chamar nenhuma API.
Permite rodar e testar todo o pipeline (incluindo o cálculo de data fatal)
sem credenciais e sem consumir cota.
"""
from __future__ import annotations

import re

from src.models import AnaliseExtraida, PrazoExtraido, Publicacao, TipoPrazo
from src.services.intelligence.base import IntelligenceProvider
from src.utils.dates import parse_date
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Número de dias seguido (opcionalmente) de "(por extenso)" e da palavra "dias".
_RE_DIAS = re.compile(r"(\d{1,3})\s*(?:\([^)]*\))?\s*dias", re.IGNORECASE)
# Data no formato DD/MM/AAAA.
_RE_DATA = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")

# Palavras-chave -> tipo de prazo (ordem importa: mais específico primeiro).
_PALAVRAS_TIPO: list[tuple[tuple[str, ...], TipoPrazo]] = [
    (("contesta",), TipoPrazo.CONTESTACAO),
    (("recurso", "apela", "embargos"), TipoPrazo.RECURSO),
    (("audiênc", "audienc"), TipoPrazo.AUDIENCIA),
    (("manifest",), TipoPrazo.MANIFESTACAO),
    (("pagamento", "custas"), TipoPrazo.PAGAMENTO),
    (("cumprimento de sentença", "cumpra-se o"), TipoPrazo.CUMPRIMENTO),
]


class MockIntelligenceProvider(IntelligenceProvider):
    """Extrai prazos de forma determinística por heurística (sem chamar IA)."""

    def _extrair(self, publicacao: Publicacao) -> AnaliseExtraida:
        texto = publicacao.conteudo
        texto_lower = texto.lower()
        logger.info("[MOCK-IA] Analisando publicação %s", publicacao.id_externo)

        tipo = TipoPrazo.OUTRO
        for chaves, candidato in _PALAVRAS_TIPO:
            if any(chave in texto_lower for chave in chaves):
                tipo = candidato
                break

        prazo_dias: int | None = None
        if (m := _RE_DIAS.search(texto)) is not None:
            prazo_dias = int(m.group(1))

        data_referencia = None
        if tipo is TipoPrazo.AUDIENCIA and (md := _RE_DATA.search(texto)) is not None:
            data_referencia = parse_date(md.group(1))

        prazos: list[PrazoExtraido] = []
        if prazo_dias is not None or data_referencia is not None:
            prazos.append(
                PrazoExtraido(
                    tipo=tipo,
                    descricao=f"[MOCK] Ação identificada: {tipo.value}.",
                    prazo_dias=prazo_dias,
                    data_referencia=data_referencia,
                    urgente=(prazo_dias is not None and prazo_dias <= 15),
                )
            )

        resumo = "[MOCK] " + " ".join(texto.split())[:140]
        return AnaliseExtraida(resumo=resumo, possui_prazo=bool(prazos), prazos=prazos)
