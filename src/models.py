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

from pydantic import BaseModel, Field, model_validator


class FonteCaptura(str, Enum):
    """Origem da publicação capturada."""

    COMUNICA = "comunica"
    ESCAVADOR = "escavador"
    JUSBRASIL = "jusbrasil"
    OUTRA = "outra"


class TipoMonitoramento(str, Enum):
    """Critério usado para monitorar publicações."""

    TERMO = "termo"
    OAB = "oab"
    PROCESSO = "processo"


class AlvoMonitoramento(BaseModel):
    """Alvo a ser monitorado (entrada da Etapa 1).

    Pode ser um termo/nome livre, um número de OAB (com UF) ou um número de
    processo no padrão CNJ.
    """

    tipo: TipoMonitoramento
    valor: str = Field(..., description="Termo, número da OAB ou número do processo")
    uf: str | None = Field(default=None, description="UF da OAB (quando tipo=oab)")

    @property
    def rotulo(self) -> str:
        """Rótulo legível para logs e para o campo `termo_monitorado`."""
        if self.tipo is TipoMonitoramento.OAB:
            return f"OAB {self.valor}" + (f"/{self.uf}" if self.uf else "")
        if self.tipo is TipoMonitoramento.PROCESSO:
            return f"Processo {self.valor}"
        return self.valor


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
    cliente: str | None = Field(
        default=None, description="Autor do processo / parte representada (cliente)"
    )
    parte_contraria: str | None = Field(
        default=None, description="Parte contrária / réu (polo passivo)"
    )
    prazo_dias: int | None = Field(
        default=None, description="Quantidade de dias do prazo, se informado na publicação"
    )
    data_referencia: date | None = Field(
        default=None, description="Data explícita citada na publicação (ex.: audiência)"
    )
    data_fatal: date | None = Field(
        default=None, description="Data limite (fatal) CALCULADA em código (dias úteis - CPC)"
    )
    urgente: bool = Field(default=False)
    observacoes: str | None = Field(default=None)


class PrazoExtraido(BaseModel):
    """Prazo conforme extraído pela IA, ANTES do cálculo da data fatal.

    A IA preenche `prazo_dias` (quantidade de dias) e/ou `data_referencia`
    (data explícita citada). A `data_fatal` final é calculada em código.
    """

    tipo: TipoPrazo = Field(default=TipoPrazo.OUTRO)
    descricao: str = Field(..., description="Resumo objetivo da ação a ser tomada")
    prazo_dias: int | None = Field(default=None, description="Número de dias do prazo")
    data_referencia: date | None = Field(
        default=None, description="Data explícita citada (AAAA-MM-DD), ex.: audiência"
    )
    urgente: bool = Field(default=False)
    observacoes: str | None = Field(default=None)


class AnaliseExtraida(BaseModel):
    """Saída estruturada BRUTA da IA para uma publicação (schema enviado ao modelo)."""

    resumo: str = Field(..., description="Resumo objetivo do teor da publicação")
    cliente: str | None = Field(
        default=None, description="Nome do autor do processo / parte representada (cliente)"
    )
    parte_contraria: str | None = Field(
        default=None, description="Nome da parte contrária / réu (polo passivo)"
    )
    possui_prazo: bool = Field(default=False)
    prazos: list[PrazoExtraido] = Field(default_factory=list)


class AnalisePublicacao(BaseModel):
    """Resultado estruturado da análise de IA sobre uma publicação (Etapa 2)."""

    id_externo: str = Field(..., description="Referência à publicação de origem")
    numero_processo: str | None = Field(default=None)
    cliente: str | None = Field(default=None, description="Autor do processo / cliente")
    parte_contraria: str | None = Field(
        default=None, description="Parte contrária / réu (polo passivo)"
    )
    resumo: str = Field(..., description="Resumo objetivo do teor da publicação")
    possui_prazo: bool = Field(default=False)
    prazos: list[Prazo] = Field(default_factory=list)
    gerado_em: datetime = Field(default_factory=datetime.now)


class EventoAgenda(BaseModel):
    """Evento a ser criado na agenda a partir de um prazo (entrada da Etapa 3)."""

    titulo: str = Field(..., description="Título do evento/lembrete")
    descricao: str = Field(default="", description="Detalhes do prazo")
    data: date = Field(..., description="Data do evento (data fatal do prazo)")
    lembrete_dias_antes: int = Field(default=5, description="Antecedência do lembrete, em dias")
    chave_idempotencia: str = Field(
        ..., description="Chave estável para evitar eventos duplicados"
    )
    urgente: bool = Field(default=False)


class PrazoManual(BaseModel):
    """Prazo informado manualmente pelo usuário (entrada alternativa à captura).

    Deve conter `data_fatal` (data já conhecida) OU `prazo_dias` (o sistema
    calcula a data fatal a partir de `data_base`, padrão: hoje).
    """

    tipo: TipoPrazo = Field(default=TipoPrazo.OUTRO)
    descricao: str = Field(..., description="Descrição da ação/prazo")
    cliente: str | None = Field(default=None, description="Autor do processo / cliente")
    parte_contraria: str | None = Field(
        default=None, description="Parte contrária / réu (polo passivo)"
    )
    numero_processo: str | None = Field(default=None)
    data_fatal: date | None = Field(default=None, description="Data limite, se já conhecida")
    prazo_dias: int | None = Field(
        default=None, description="Prazo em dias (calcula a data fatal a partir de data_base)"
    )
    data_base: date | None = Field(
        default=None, description="Data inicial da contagem do prazo (padrão: hoje)"
    )
    dias_uteis: bool = Field(default=True, description="Contar em dias úteis (CPC) ou corridos")
    urgente: bool = Field(default=False)
    observacoes: str | None = Field(default=None)

    @model_validator(mode="after")
    def _exige_data_ou_prazo(self) -> "PrazoManual":
        if self.data_fatal is None and self.prazo_dias is None:
            raise ValueError(
                "Informe 'data_fatal' ou 'prazo_dias' para o prazo manual."
            )
        return self


class PrazoManualRegistro(BaseModel):
    """Registro persistido de um prazo (manual ou capturado), para a lista/CRUD."""

    id: str
    prazo: PrazoManual
    data_fatal: date
    evento_ref: str | None = Field(
        default=None, description="ID do evento criado na agenda"
    )
    origem: str = Field(default="manual", description="manual | captura")
    criado_em: datetime = Field(default_factory=datetime.now)
