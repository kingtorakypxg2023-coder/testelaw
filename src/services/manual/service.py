"""Inclusão e gestão de prazos manuais (entrada alternativa à captura/IA).

O usuário informa um prazo diretamente; o sistema calcula a data fatal (quando
informado em dias) e cria o evento na agenda, reutilizando o fluxo da Etapa 3.
Os prazos manuais são persistidos (CRUD) com o ID do evento na agenda.
"""
from __future__ import annotations

import hashlib
from datetime import date

from src.config.settings import settings
from src.models import (
    AnalisePublicacao,
    EventoAgenda,
    Prazo,
    PrazoManual,
    PrazoManualRegistro,
)
from src.services.agenda import AgendaError, get_agenda_provider, montar_eventos
from src.services.agenda.base import AgendaProvider
from src.services.manual.repository import ManualPrazoRepository, get_manual_repository
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


def _resolver_agenda(agenda: AgendaProvider | None) -> AgendaProvider:
    if agenda is not None:
        return agenda
    try:
        return get_agenda_provider()
    except AgendaError as exc:
        logger.warning(
            "Agenda '%s' indisponível (%s). Usando provedor 'mock'.",
            settings.agenda_provider,
            exc,
        )
        return get_agenda_provider("mock")


def _criar_evento(
    prazo_manual: PrazoManual,
    lembrete_dias: int | None,
    agenda: AgendaProvider | None,
) -> tuple[EventoAgenda, str | None]:
    analise = construir_analise_manual(prazo_manual)
    lembrete = settings.deadline_reminder_days if lembrete_dias is None else lembrete_dias
    eventos = montar_eventos([analise], lembrete)
    evento = eventos[0]
    refs = _resolver_agenda(agenda).criar_eventos([evento])
    return evento, (refs[0] if refs else None)


def registrar_prazo_manual(
    prazo_manual: PrazoManual,
    *,
    lembrete_dias: int | None = None,
    agenda: AgendaProvider | None = None,
) -> EventoAgenda:
    """Cria o evento de agenda para um prazo manual e o devolve (sem persistir)."""
    evento, _ref = _criar_evento(prazo_manual, lembrete_dias, agenda)
    return evento


def adicionar_prazo_manual(
    prazo_manual: PrazoManual,
    *,
    lembrete_dias: int | None = None,
    agenda: AgendaProvider | None = None,
    repository: ManualPrazoRepository | None = None,
) -> PrazoManualRegistro:
    """Cria o evento e persiste o prazo manual (CRUD), devolvendo o registro."""
    repository = repository or get_manual_repository()
    evento, ref = _criar_evento(prazo_manual, lembrete_dias, agenda)
    id_ = repository.adicionar(prazo_manual, evento.data, ref)
    registro = repository.obter(id_)
    assert registro is not None  # acabou de ser inserido
    return registro


def listar_prazos_manuais(
    repository: ManualPrazoRepository | None = None,
) -> list[PrazoManualRegistro]:
    """Lista os prazos manuais cadastrados."""
    return (repository or get_manual_repository()).listar()


def remover_prazo_manual(
    id_: str,
    *,
    repository: ManualPrazoRepository | None = None,
    agenda: AgendaProvider | None = None,
) -> bool:
    """Remove um prazo (manual ou capturado) e o evento na agenda, se houver."""
    repository = repository or get_manual_repository()
    registro = repository.obter(id_)
    if registro is None:
        return False
    if registro.evento_ref:
        try:
            _resolver_agenda(agenda).remover_evento(registro.evento_ref)
        except AgendaError as exc:
            logger.warning("Não foi possível remover o evento na agenda (%s).", exc)
    return repository.remover(id_)


def salvar_prazos_capturados(
    analises: list[AnalisePublicacao],
    repository: ManualPrazoRepository | None = None,
) -> int:
    """Persiste os prazos extraídos das publicações (origem=captura), sem duplicar.

    Faz com que os prazos capturados apareçam na mesma lista dos manuais.
    Retorna a quantidade de prazos novos registrados.
    """
    repository = repository or get_manual_repository()
    novos = 0
    for analise in analises:
        for prazo in analise.prazos:
            if prazo.data_fatal is None:
                continue
            chave = (
                f"{analise.id_externo}:{prazo.tipo.value}:{prazo.data_fatal.isoformat()}"
            )
            if repository.existe_chave(chave):
                continue
            registro = PrazoManual(
                tipo=prazo.tipo,
                descricao=prazo.descricao,
                numero_processo=analise.numero_processo,
                data_fatal=prazo.data_fatal,
                prazo_dias=prazo.prazo_dias,
                urgente=prazo.urgente,
                observacoes=prazo.observacoes,
            )
            repository.adicionar(
                registro, prazo.data_fatal, evento_ref=None, origem="captura", chave=chave
            )
            novos += 1
    return novos
