"""Modelos de dados (contratos) compartilhados entre as etapas do pipeline.

Estes modelos Pydantic definem o "contrato" de dados que trafega entre os
três serviços do sistema:

    Etapa 1 (Captura)      ->  Publicacao
    Etapa 2 (Inteligência) ->  Publicacao (texto) -> AnalisePublicacao (JSON)
    Etapa 3 (Agenda)       ->  Prazo -> Evento no Google Calendar
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class FonteCaptura(str, Enum):
    """Origem da publicação capturada."""

    ESCAVADOR = "escavador"
    JUSBRASIL = "jusbrasil"
    OUTRA = "outra"


class Publicacao(BaseModel):
    """Publicação bruta capturada de um diário oficial (saída da Etapa 1)."""

    id_externo: str = Field(..., description="Identificador da publicação na fonte")
    fonte: FonteCaptura = Field(default=FonteCaptura.OUTRA)
    termo_monitorado: str | None = Field(
        default=None, description="Termo/nome que disparou a captura"
    )
    numero_processo: str | None = Field(default=None, description="Número do processo (CNJ)")
    diario: str | None = Field(default=None, description="Nome do diário oficial")
    data_publicacao: date | None = Field(default=None)
    conteudo: str = Field(..., description="Texto bruto integral da publicação")


class TipoPrazo(str, Enum):
    """Categorias de prazos/ações jurídicas reconhecidas."""

    RECURSO = "recurso"
    CONTESTACAO = "contestacao"
    MANIFESTACAO = "manifestacao"
    AUDIENCIA = "audiencia"
    PAGAMENTO = "pagamento"
    CUMPRIMENTO = "cumprimento"
    OUTRO = "outro"


class Prazo(BaseModel):
    """Prazo/ação jurídica extraído de uma publicação (saída da Etapa 2)."""

    tipo: TipoPrazo = Field(default=TipoPrazo.OUTRO)
    descricao: str = Field(..., description="Resumo objetivo da ação a ser tomada")
    prazo_dias: int | None = Field(
        default=None, description="Quantidade de dias do prazo, se informado na publicação"
    )
    data_fatal: date | None = Field(
        default=None, description="Data limite (fatal) calculada ou informada"
    )
    urgente: bool = Field(default=False)
    observacoes: str | None = Field(default=None)


class AnalisePublicacao(BaseModel):
    """Resultado estruturado da análise de IA sobre uma publicação (Etapa 2)."""

    id_externo: str = Field(..., description="Referência à publicação de origem")
    numero_processo: str | None = Field(default=None)
    resumo: str = Field(..., description="Resumo objetivo do teor da publicação")
    possui_prazo: bool = Field(default=False)
    prazos: list[Prazo] = Field(default_factory=list)
    gerado_em: datetime = Field(default_factory=datetime.now)
