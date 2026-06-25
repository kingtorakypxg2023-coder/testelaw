"""Interface comum dos provedores de Inteligência Artificial (Etapa 2).

Cada provedor (Claude, Gemini, OpenAI, mock) implementa apenas a extração bruta
(`_extrair`) devolvendo uma `AnaliseExtraida`. O cálculo determinístico da
**data fatal** acontece aqui na classe base (`analisar`), em código — a IA não
calcula datas, apenas extrai `prazo_dias` e datas de referência citadas.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from src.models import (
    AnaliseExtraida,
    AnalisePublicacao,
    Prazo,
    PrazoExtraido,
    Publicacao,
)
from src.utils.prazos import calcular_data_fatal


class IntelligenceError(Exception):
    """Erro durante a análise por IA (credencial, rede, contrato de saída)."""


class IntelligenceProvider(ABC):
    """Contrato dos provedores de extração de prazos por IA."""

    @abstractmethod
    def _extrair(self, publicacao: Publicacao) -> AnaliseExtraida:
        """Chama o modelo e devolve a extração estruturada bruta."""
        raise NotImplementedError

    def analisar(self, publicacao: Publicacao) -> AnalisePublicacao:
        """Analisa uma publicação e devolve o resultado com a data fatal calculada."""
        extraida = self._extrair(publicacao)
        prazos = [
            self._para_prazo(
                pe,
                publicacao.data_publicacao,
                extraida.cliente,
                extraida.parte_contraria,
            )
            for pe in extraida.prazos
        ]
        return AnalisePublicacao(
            id_externo=publicacao.id_externo,
            numero_processo=publicacao.numero_processo,
            cliente=extraida.cliente,
            parte_contraria=extraida.parte_contraria,
            resumo=extraida.resumo,
            possui_prazo=extraida.possui_prazo or bool(prazos),
            prazos=prazos,
        )

    def analisar_varias(
        self, publicacoes: list[Publicacao]
    ) -> list[AnalisePublicacao]:
        """Analisa várias publicações."""
        return [self.analisar(p) for p in publicacoes]

    @staticmethod
    def _para_prazo(
        extraido: PrazoExtraido,
        data_base: date | None,
        cliente: str | None = None,
        parte_contraria: str | None = None,
    ) -> Prazo:
        """Converte a extração da IA em `Prazo`, calculando a data fatal em código."""
        if extraido.prazo_dias is not None:
            data_fatal = calcular_data_fatal(data_base, extraido.prazo_dias)
        else:
            data_fatal = extraido.data_referencia
        return Prazo(
            tipo=extraido.tipo,
            descricao=extraido.descricao,
            cliente=cliente,
            parte_contraria=parte_contraria,
            prazo_dias=extraido.prazo_dias,
            data_referencia=extraido.data_referencia,
            data_fatal=data_fatal,
            urgente=extraido.urgente,
            observacoes=extraido.observacoes,
        )
