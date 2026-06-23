"""Interface (contrato) comum dos provedores de captura de publicações.

Cada fonte (Jusbrasil, Escavador, mock...) implementa `CaptureProvider`,
permitindo trocar/adicionar provedores sem alterar o restante do pipeline.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from src.models import AlvoMonitoramento, Publicacao


class CaptureError(Exception):
    """Erro durante a captura de publicações (rede, autenticação, contrato)."""


class CaptureProvider(ABC):
    """Contrato para provedores de captura de publicações de diários oficiais."""

    @abstractmethod
    def buscar(
        self,
        alvo: AlvoMonitoramento,
        *,
        data_inicio: date | None = None,
        data_fim: date | None = None,
    ) -> list[Publicacao]:
        """Busca publicações para um único alvo de monitoramento."""
        raise NotImplementedError

    def buscar_varios(
        self,
        alvos: list[AlvoMonitoramento],
        *,
        data_inicio: date | None = None,
        data_fim: date | None = None,
    ) -> list[Publicacao]:
        """Busca publicações para vários alvos, agregando os resultados."""
        resultados: list[Publicacao] = []
        for alvo in alvos:
            resultados.extend(
                self.buscar(alvo, data_inicio=data_inicio, data_fim=data_fim)
            )
        return resultados
