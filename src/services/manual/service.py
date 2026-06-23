"""Inclusão de prazos manuais (entrada alternativa à captura/IA).

O usuário informa um prazo diretamente; o sistema calcula a data fatal (quando
informado em dias) e cria o evento na agenda, reutilizando o mesmo fluxo da
Etapa 3. Uma chave de idempotência derivada do conteúdo evita duplicar o evento
caso o mesmo prazo seja registrado mais de uma vez.
"""
from __future__ import annotations

import hashlib
from datetime import date

from src.config.settings import settings
from src.models import AnalisePublicacao, EventoAgenda, Prazo, PrazoManual
from src.services.agenda import AgendaError, get_agenda_provider, montar_eventos
from src.services.agenda.base import AgendaProvider
from src.utils.logger import get_logger
from src.utils.prazos import calcular_data_fatal

logger = get_logger(__name__)


def _id_externo(
    numero_processo: str | None, descricao: str, tipo: str, data_fatal: date
) -> str:
    base = f"{numero_processo}|{descricao}|{tipo}|{data_fatal.isoformat()}"
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]
    return f"manual-{digest}"


def construir_analise_manual(prazo_manual: PrazoManual) -> AnalisePublicacao:
    """Converte um `PrazoManual` em `AnalisePublicacao`, calculando a data fatal."""
    if prazo_manual.data_fatal is not None:
        data_fatal = prazo_manual.data_fatal
    else:
        data_base = prazo_manual.data_base or date.today()
        data_fatal = calcular_data_fatal(
            data_base, prazo_manual.prazo_dias, dias_uteis=prazo_manual.dias_uteis
        )
    if data_fatal is None:  # proteção; o validador do modelo já garante os dados
        raise ValueError("Não foi possível determinar a data fatal do prazo manual.")

    prazo = Prazo(
        tipo=prazo_manual.tipo,
        descricao=prazo_manual.descricao,
        prazo_dias=prazo_manual.prazo_dias,
        data_referencia=prazo_manual.data_fatal,
        data_fatal=data_fatal,
        urgente=prazo_manual.urgente,
        observacoes=prazo_manual.observacoes,
    )
    return AnalisePublicacao(
        id_externo=_id_externo(
            prazo_manual.numero_processo,
            prazo_manual.descricao,
            prazo_manual.tipo.value,
            data_fatal,
        ),
        numero_processo=prazo_manual.numero_processo,
        resumo=prazo_manual.descricao,
        possui_prazo=True,
        prazos=[prazo],
    )


def registrar_prazo_manual(
    prazo_manual: PrazoManual,
    *,
    lembrete_dias: int | None = None,
    agenda: AgendaProvider | None = None,
) -> EventoAgenda:
    """Cria o evento de agenda para um prazo manual e o devolve."""
    analise = construir_analise_manual(prazo_manual)
    lembrete = settings.deadline_reminder_days if lembrete_dias is None else lembrete_dias
    eventos = montar_eventos([analise], lembrete)
    if not eventos:  # pragma: no cover - data_fatal sempre presente aqui
        raise ValueError("Prazo manual sem data fatal; nada a agendar.")

    if agenda is None:
        try:
            agenda = get_agenda_provider()
        except AgendaError as exc:
            logger.warning(
                "Agenda '%s' indisponível (%s). Usando provedor 'mock'.",
                settings.agenda_provider,
                exc,
            )
            agenda = get_agenda_provider("mock")

    agenda.criar_eventos(eventos)
    return eventos[0]
